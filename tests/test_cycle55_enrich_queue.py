"""Cycle-55: background product-enrichment drainer. A scanned-in product is created instantly
(info_status='') and sits in a queue; a background loop drains it slowly across the day via the
existing throttled scanit lookup. This tests the queue-selection logic and the kill-switch — not
the live thread (which just calls _scanit_start_lookup on the picked SKUs)."""
import uuid


def _mkprod(A, sku, info_status="", name="New product • x", retail=0, notes="",
            days_old=0):
    from datetime import datetime, timedelta
    ts = (datetime.now() - timedelta(days=days_old)).isoformat(timespec="seconds")
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("""INSERT INTO products(sku,name,barcode,on_hand,avg_cost,retail_price,product_notes,
                 info_status,updated_at,created_at) VALUES(?,?,?,0,0,?,?,?,?,?)""",
              (sku, name, sku, retail, notes, info_status, ts, ts))
    c.commit(); c.close()


def test_queue_picks_unenriched_skips_done(appmod, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "anthropic_client", object())   # enrichment gate needs a client present
    stub = "Q" + uuid.uuid4().hex[:6]
    done = "D" + uuid.uuid4().hex[:6]
    _mkprod(A, stub, info_status="")                                   # fresh scan → queued
    _mkprod(A, done, info_status="done", name="Real Name", retail=20)  # already enriched
    picks = A._enrich_pick_candidates(A.DEFAULT_ORG, 10)
    assert stub in picks
    assert done not in picks


def test_queue_respects_age_window(appmod, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "anthropic_client", object())
    monkeypatch.setattr(A, "ENRICH_MAX_AGE_DAYS", 30)
    recent = "R" + uuid.uuid4().hex[:6]
    old = "O" + uuid.uuid4().hex[:6]
    _mkprod(A, recent, days_old=1)
    _mkprod(A, old, days_old=90)     # older than the window → not drained (keeps token cost bounded)
    picks = A._enrich_pick_candidates(A.DEFAULT_ORG, 10)
    assert recent in picks
    assert old not in picks


def test_kill_switch(appmod, monkeypatch):
    A = appmod
    monkeypatch.setenv("BARCODE_ENRICH_QUEUE", "0")
    assert A._enrich_queue_on() is False
    monkeypatch.setenv("BARCODE_ENRICH_QUEUE", "1")
    assert A._enrich_queue_on() is True
