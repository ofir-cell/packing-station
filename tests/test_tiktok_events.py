"""Regression: duplicate and out-of-order TikTok events are handled safely.
Drives the REAL _tt_apply_order path."""
import uuid


def _order(sid, status="AWAITING_SHIPMENT", delivery_time=None):
    o = {"id": "O" + sid, "status": status, "packages": [{"id": sid}],
         "line_items": [{"id": "L", "seller_sku": "S1", "sku_id": "S1", "product_name": "Lip",
                         "sale_price": "5", "package_id": sid}],
         "recipient_address": {"full_address": "1 Main"}}
    if delivery_time:
        o["delivery_time"] = delivery_time
    return o


def test_duplicate_event_is_idempotent(appmod, sdb):
    c = sdb(); tag = uuid.uuid4().hex[:5]; sid = f"dup-{tag}"
    appmod._tt_apply_order(c, _order(sid), label="L"); c.commit()
    appmod._tt_apply_order(c, _order(sid), label="L"); c.commit()   # same event again
    n_ship = c.execute("SELECT COUNT(*) FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0]
    n_item = c.execute("SELECT COUNT(*) FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()[0]
    c.close()
    assert n_ship == 1, f"duplicate must not create a 2nd shipment, got {n_ship}"
    assert n_item == 1, f"duplicate must not duplicate items, got {n_item}"


def test_out_of_order_event_does_not_revert_progress(appmod, sdb):
    c = sdb(); tag = uuid.uuid4().hex[:5]; sid = f"ooo-{tag}"
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) "
              "VALUES(?,'packed','tiktok-api','L','tiktok')", (sid,))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,'S1','Lip',1)", (sid, "O" + sid))
    c.commit()
    appmod._tt_apply_order(c, _order(sid, "AWAITING_SHIPMENT"), label="L"); c.commit()  # stale/out-of-order
    st = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0]
    c.close()
    assert st == "packed", f"out-of-order event must not revert packed→pending, got {st}"


def test_delivered_not_downgraded_by_later_event(appmod, sdb):
    c = sdb(); tag = uuid.uuid4().hex[:5]; sid = f"dlv-{tag}"
    appmod._tt_apply_order(c, _order(sid, "DELIVERED", delivery_time=1700000000), label="L"); c.commit()
    d1 = c.execute("SELECT delivery_status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0]
    appmod._tt_apply_order(c, _order(sid, "IN_TRANSIT"), label="L"); c.commit()   # out-of-order older status
    d2 = c.execute("SELECT delivery_status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0]
    c.close()
    assert d1 == "DELIVERED", f"first should be DELIVERED, got {d1}"
    assert d2 == "DELIVERED", f"must not downgrade DELIVERED→IN_TRANSIT, got {d2}"
