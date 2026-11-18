"""Cycle-55/56: background enrichment drainer. A scanned-in product is created instantly
(bc_status='') and queued; a background loop drains it slowly and fills NAME/IMAGE/MSRP from the
online barcode databases (no AI). This tests the queue-selection logic and the kill-switch — not
the live thread."""
import uuid


def _mkprod(A, sku, name="New product • x", image_url="", bc_status="", barcode=None, days_old=0):
    from datetime import datetime, timedelta
    ts = (datetime.now() - timedelta(days=days_old)).isoformat(timespec="seconds")
    bc = barcode if barcode is not None else ("0" + uuid.uuid4().hex[:11])
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("""INSERT INTO products(sku,name,barcode,on_hand,avg_cost,image_url,bc_status,
                 updated_at,created_at) VALUES(?,?,?,0,0,?,?,?,?)""",
              (sku, name, bc, image_url, bc_status, ts, ts))
    c.commit(); c.close()
    return bc


def test_queue_picks_incomplete_skips_complete(appmod):
    A = appmod
    stub = "Q" + uuid.uuid4().hex[:6]
    good = "G" + uuid.uuid4().hex[:6]
    noimg = "N" + uuid.uuid4().hex[:6]
    _mkprod(A, stub, name="New product • 123")                               # stub name → wants
    _mkprod(A, good, name="Real Lipstick", image_url="https://x/y.jpg",
            bc_status="done")                                               # already enriched → skip
    _mkprod(A, noimg, name="Real Serum", image_url="")                       # has name but no image → wants
    picks = A._enrich_pick_candidates(A.DEFAULT_ORG, 20)
    assert stub in picks
    assert noimg in picks
    assert good not in picks


def test_queue_skips_non_upc_and_old(appmod):
    A = appmod
    monkey = "M" + uuid.uuid4().hex[:6]
    old = "O" + uuid.uuid4().hex[:6]
    _mkprod(A, monkey, barcode="SHORT")      # not a real UPC (less than 8 digits) → never looked up
    _mkprod(A, old, days_old=90)             # older than the window → not drained
    picks = A._enrich_pick_candidates(A.DEFAULT_ORG, 20)
    assert monkey not in picks
    assert old not in picks


def test_barcode_enrich_fills_blanks_only(appmod, monkeypatch):
    A = appmod
    sku = "P" + uuid.uuid4().hex[:6]
    code = _mkprod(A, sku, name="New product • " + "123", image_url="")
    monkeypatch.setattr(A, "_barcode_lookup_online",
                        lambda c: {"code": code, "name": "Dior Sauvage EDT 100ml", "brand": "Dior",
                                   "category": "Fragrance", "image": "https://img/x.jpg",
                                   "price": 155.0, "source": "UPCitemdb"})
    A._barcode_enrich_one(A.DEFAULT_ORG, sku)
    c = A.sdb(A.DEFAULT_ORG)
    r = c.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    assert r["name"] == "Dior Sauvage EDT 100ml"        # stub name replaced
    assert r["image_url"] == "https://img/x.jpg"        # blank image filled
    assert round(r["retail_price"], 2) == 155.0         # MSRP filled (was 0)
    assert r["bc_status"] == "done"


def test_barcode_enrich_never_overwrites_real_values(appmod, monkeypatch):
    A = appmod
    sku = "R" + uuid.uuid4().hex[:6]
    _mkprod(A, sku, name="My Hand-Typed Name", image_url="https://mine/real.jpg")
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE products SET retail_price=99, msrp_source='manual' WHERE sku=?", (sku,)); c.commit(); c.close()
    monkeypatch.setattr(A, "_barcode_lookup_online",
                        lambda c: {"name": "Other Name", "image": "https://db/other.jpg",
                                   "price": 20.0, "source": "x"})
    A._barcode_enrich_one(A.DEFAULT_ORG, sku)
    c = A.sdb(A.DEFAULT_ORG)
    r = c.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    assert r["name"] == "My Hand-Typed Name"            # real name kept
    assert r["image_url"] == "https://mine/real.jpg"    # real image kept
    assert round(r["retail_price"], 2) == 99.0          # manual price kept


def test_kill_switch(appmod, monkeypatch):
    A = appmod
    monkeypatch.setenv("BARCODE_ENRICH_QUEUE", "0")
    assert A._enrich_queue_on() is False
    monkeypatch.setenv("BARCODE_ENRICH_QUEUE", "1")
    assert A._enrich_queue_on() is True
