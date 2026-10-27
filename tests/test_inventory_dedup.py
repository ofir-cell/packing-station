"""Regression: stock is deducted EXACTLY ONCE across regroup and repeat TikTok sync.
Drives the REAL paths: _deplete_stock_for, _tt_apply_order, and /api/tiktok/regroup."""
import uuid


def _seed_packed_with_stock(A, c, sid, label, on_hand=100, prod="PROD1", sticker="S1", qty=1):
    c.execute("INSERT OR REPLACE INTO products(sku,name,on_hand) VALUES(?,?,?)", (prod, "Lip Product", on_hand))
    c.execute("INSERT OR REPLACE INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,?,?)",
              (label, sticker, 0, prod))
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) "
              "VALUES(?,?,'tiktok-api',?,'tiktok')", (sid, "packed", label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,?)",
              (sid, "O" + sid, sticker, "Lip", qty))


def _oh(c, prod="PROD1"):
    return c.execute("SELECT on_hand FROM products WHERE sku=?", (prod,)).fetchone()[0]


def _order(sid, status="AWAITING_SHIPMENT"):
    return {"id": "O" + sid, "status": status, "packages": [{"id": sid}],
            "line_items": [{"id": "L", "seller_sku": "S1", "sku_id": "S1", "product_name": "Lip",
                            "sale_price": "5", "package_id": sid}],
            "recipient_address": {"full_address": "1 Main"}}


def test_deplete_is_idempotent(appmod, sdb):
    c = sdb(); tag = uuid.uuid4().hex[:5]; sid = f"dp-{tag}"; label = f"Show {tag}"
    _seed_packed_with_stock(appmod, c, sid, label); c.commit()
    appmod._deplete_stock_for(c, sid); c.commit(); first = _oh(c)
    appmod._deplete_stock_for(c, sid); c.commit(); second = _oh(c)   # repeat
    c.close()
    assert first == 99, f"first deplete should take 1 off 100, got {first}"
    assert second == 99, f"repeat deplete must NOT deduct again, got {second}"


def test_resync_after_deplete_does_not_double_deduct(appmod, sdb):
    c = sdb(); tag = uuid.uuid4().hex[:5]; sid = f"rs-{tag}"; label = f"Show {tag}"
    _seed_packed_with_stock(appmod, c, sid, label); c.commit()
    appmod._deplete_stock_for(c, sid); c.commit()
    appmod._tt_apply_order(c, _order(sid), label=label); c.commit()   # repeat TikTok sync
    oh = _oh(c)
    dep = c.execute("SELECT depleted_qty,depleted_sku FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()
    c.close()
    assert oh == 99, f"re-sync must not re-deduct, got {oh}"
    assert (dep[0], dep[1]) == (1, "PROD1"), f"depletion markers must carry over, got {tuple(dep)}"


def test_regroup_does_not_double_deduct(appmod, admin, sdb, monkeypatch):
    tag = uuid.uuid4().hex[:5]; sid = f"rg-{tag}"; label = f"Show {tag}"
    c = sdb(); _seed_packed_with_stock(appmod, c, sid, label); c.commit(); c.close()
    c = sdb(); appmod._deplete_stock_for(c, sid); c.commit(); c.close()
    monkeypatch.setattr(appmod, "_tt_pull_core", lambda org, days=30: {"ok": True, "shows": []})
    r = admin.post("/api/tiktok/regroup", json={"days": 45}, headers=admin.csrf)
    assert r.status_code == 200 and r.get_json()["ok"]
    c = sdb(); oh = _oh(c); c.close()
    assert oh == 99, f"regroup (relabel) must not re-deduct, got {oh}"
