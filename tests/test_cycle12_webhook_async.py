"""Cycle 12: the TikTok order webhook must ack immediately and fetch the order in the
background, and the "live is selling" signal must be visible to every worker.

Production evidence (Oct 29 2026): a burst of ~200 order pushes took 21-36s each
because the order fetch ran inline, holding all 4 gunicorn workers so packing stations
waited (502s / 30s p95). See the Packing Station review doc, section 1.
"""
import hashlib, hmac, json, os, threading, time, uuid


def _sign(A, body):
    return hmac.new(A.TIKTOK_APP_SECRET.encode(), A.TIKTOK_APP_KEY.encode() + body, hashlib.sha256).hexdigest()


def _push(A, client, order_id, shop_id="SHOP-ASYNC"):
    body = json.dumps({"type": 1, "shop_id": shop_id,
                       "data": {"order_id": order_id, "order_status": "AWAITING_SHIPMENT"}}).encode()
    return client.post("/api/tiktok/webhook", data=body, headers={"Authorization": _sign(A, body)})


def _wait_drained(A, timeout=5):
    end = time.time() + timeout
    while time.time() < end:
        if A._tt_ingest_q.unfinished_tasks == 0:
            return True
        time.sleep(0.02)
    return False


def test_webhook_acks_before_order_fetch(appmod, client, monkeypatch):
    A = appmod
    gate, calls = threading.Event(), []

    def slow_fetch(org, shop_id, order_id):
        gate.wait(10)                      # stands in for a slow TikTok round-trip
        calls.append(order_id)

    monkeypatch.setattr(A, "_tt_ingest_order", slow_fetch)
    monkeypatch.setattr(A, "_tt_org_for_shop", lambda s: A.DEFAULT_ORG)
    oid = "O-" + uuid.uuid4().hex[:8]
    t = time.time()
    r = _push(A, client, oid)
    took = time.time() - t
    assert r.status_code == 200 and r.get_json()["code"] == 0
    assert took < 1.0, "webhook waited on the order fetch (%.2fs)" % took
    assert calls == []                     # fetch has not run yet: it is queued
    gate.set()
    assert _wait_drained(A)
    assert calls == [oid]                  # ...and it does run, in the background


def test_duplicate_pushes_collapse_while_waiting(appmod, client, monkeypatch):
    A = appmod
    gate, calls = threading.Event(), []

    def fetch(org, shop_id, order_id):
        if order_id.startswith("BLOCK"):
            gate.wait(10)
        calls.append(order_id)

    monkeypatch.setattr(A, "_tt_ingest_order", fetch)
    monkeypatch.setattr(A, "_tt_org_for_shop", lambda s: A.DEFAULT_ORG)
    blocker = "BLOCK-" + uuid.uuid4().hex[:6]
    dup = "DUP-" + uuid.uuid4().hex[:6]
    _push(A, client, blocker)              # occupies the ingest thread
    time.sleep(0.1)
    for _ in range(5):                     # TikTok often re-sends the same order
        assert _push(A, client, dup).status_code == 200
    gate.set()
    assert _wait_drained(A)
    assert calls.count(dup) == 1
    assert calls.count(blocker) == 1


def test_fetch_error_does_not_kill_ingest_thread(appmod, client, monkeypatch):
    A = appmod
    calls = []

    def flaky(org, shop_id, order_id):
        calls.append(order_id)
        if order_id.startswith("BAD"):
            raise RuntimeError("TikTok 500")

    monkeypatch.setattr(A, "_tt_ingest_order", flaky)
    monkeypatch.setattr(A, "_tt_org_for_shop", lambda s: A.DEFAULT_ORG)
    bad, good = "BAD-" + uuid.uuid4().hex[:6], "GOOD-" + uuid.uuid4().hex[:6]
    _push(A, client, bad)
    _push(A, client, good)
    assert _wait_drained(A)
    assert calls[-2:] == [bad, good]


def test_live_signal_is_shared_across_workers(appmod, client, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_tt_ingest_order", lambda *a: None)
    monkeypatch.setattr(A, "_tt_org_for_shop", lambda s: A.DEFAULT_ORG)
    try: os.remove(A._TT_LIVE_MARK)
    except FileNotFoundError: pass
    _push(A, client, "LIVE-" + uuid.uuid4().hex[:6])
    _wait_drained(A)
    # Simulate the sweep running in a DIFFERENT worker: its own global never saw the push.
    monkeypatch.setattr(A, "_tt_last_event", 0)
    assert time.time() - A._tt_last_live_event() < 5


def test_unsigned_push_still_rejected_and_not_queued(appmod, client, monkeypatch):
    A = appmod
    calls = []
    monkeypatch.setattr(A, "_tt_ingest_order", lambda o, s, i: calls.append(i))
    before = A._tt_ingest_q.unfinished_tasks
    body = json.dumps({"type": 1, "shop_id": "X", "data": {"order_id": "EVIL"}}).encode()
    r = client.post("/api/tiktok/webhook", data=body)
    assert r.status_code == 401
    assert _wait_drained(A)
    assert "EVIL" not in calls and A._tt_ingest_q.unfinished_tasks <= before
