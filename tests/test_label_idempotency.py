"""R4: shipping-label purchase is idempotent and concurrency-safe. Carrier is mocked."""
import uuid, threading


def _ok_label(counter):
    def _fake(rate_id, idem_key=None):
        counter.append(idem_key or True)   # record each real carrier call
        return {"postage_label": {"label_url": "https://x/label.pdf"}, "tracking_code": "TRK1",
                "selected_rate": {"rate": 5.0, "carrier": "usps", "service": "priority"}}
    return _fake


def test_double_buy_charges_once(appmod, monkeypatch):
    calls = []
    monkeypatch.setattr(appmod, "_ship_buy", _ok_label(calls))
    rid = "rate-" + uuid.uuid4().hex[:6]; sid = "S-" + uuid.uuid4().hex[:6]
    r1 = appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid, who="t")
    r2 = appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid, who="t")   # repeat/double-click
    assert r1["ok"] and r2["ok"]
    assert len(calls) == 1, f"carrier must be called once, got {len(calls)}"
    assert r2.get("idempotent") is True and r2["tracking"] == r1["tracking"]


def test_in_progress_blocks_second(appmod, monkeypatch):
    calls = []
    monkeypatch.setattr(appmod, "_ship_buy", _ok_label(calls))
    rid = "rate-" + uuid.uuid4().hex[:6]; sid = "S-" + uuid.uuid4().hex[:6]
    c = appmod.sdb(appmod.DEFAULT_ORG); appmod._label_claim_ensure(c)
    c.execute("INSERT INTO label_purchases(rate_id,shipment_id,status,created_at,updated_at) VALUES(?,?,'purchasing','n','n')", (rid, sid))
    c.commit(); c.close()
    res = appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid)
    assert res["ok"] is False and res.get("in_progress") is True
    assert len(calls) == 0, "must not call carrier while a purchase is in progress"


def test_error_then_retry_succeeds(appmod, monkeypatch):
    state = {"n": 0}; seen = []
    def flaky(rate_id, idem_key=None):
        seen.append(idem_key); state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError("carrier 503")
        return {"postage_label": {"label_url": "L"}, "tracking_code": "T2",
                "selected_rate": {"rate": 3.0, "carrier": "usps", "service": "ground"}}
    monkeypatch.setattr(appmod, "_ship_buy", flaky)
    rid = "rate-" + uuid.uuid4().hex[:6]; sid = "S-" + uuid.uuid4().hex[:6]
    r1 = appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid)
    assert r1["ok"] is False                       # first attempt errored
    r2 = appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid)
    assert r2["ok"] is True and r2["tracking"] == "T2"   # retry allowed after error
    assert seen[0] == seen[1] and seen[0], "same idempotency key reused across the retry"


def test_purchase_recorded_authoritatively(appmod, monkeypatch):
    trk = "TRK-" + uuid.uuid4().hex[:8]
    def fake(rate_id, idem_key=None):
        return {"postage_label": {"label_url": "L"}, "tracking_code": trk,
                "selected_rate": {"rate": 5.0, "carrier": "usps", "service": "priority"}}
    monkeypatch.setattr(appmod, "_ship_buy", fake)
    rid = "rate-" + uuid.uuid4().hex[:6]; sid = "S-" + uuid.uuid4().hex[:6]
    appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid)
    c = appmod.sdb(appmod.DEFAULT_ORG)
    row = c.execute("SELECT status,tracking FROM label_purchases WHERE rate_id=?", (rid,)).fetchone()
    inb = c.execute("SELECT COUNT(*) FROM inbound_shipments WHERE tracking=?", (trk,)).fetchone()[0]
    c.close()
    assert row["status"] == "bought" and row["tracking"] == trk   # authoritative record exists
    assert inb == 1


def test_concurrent_buys_single_charge(appmod, monkeypatch):
    lock = threading.Lock(); calls = []
    def fake(rate_id, idem_key=None):
        with lock: calls.append(1)
        return {"postage_label": {"label_url": "L"}, "tracking_code": "T",
                "selected_rate": {"rate": 5.0, "carrier": "usps", "service": "priority"}}
    monkeypatch.setattr(appmod, "_ship_buy", fake)
    rid = "rate-" + uuid.uuid4().hex[:6]; sid = "S-" + uuid.uuid4().hex[:6]
    def worker(): appmod._buy_label_idempotent(appmod.DEFAULT_ORG, sid, rid)
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(calls) == 1, f"8 concurrent buys of one rate must charge once, got {len(calls)}"
