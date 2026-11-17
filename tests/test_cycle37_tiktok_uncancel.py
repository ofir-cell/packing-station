"""Cycle-37: a TikTok API order that TikTok REINSTATES (cancelled → active again) must not
stay stuck 'cancelled' in the warehouse. The sync rebuilt the items as active but kept the
shipment status 'cancelled' (sticky), so picking showed DO NOT PACK while TikTok Seller Center
showed 'awaiting shipment'. Fix: when TikTok reports the order active, clear the stale local
cancellation (restore floor progress) and log it. A genuine cancellation still cancels."""
import uuid


def test_reinstated_tiktok_order_is_uncancelled(appmod):
    A = appmod
    oid = "5776728811117761822"          # the real order from the floor
    sid = "TT-" + oid
    c = A.sdb(A.DEFAULT_ORG)
    # Local state: an API-owned order sitting 'cancelled' (a cancel TikTok later reversed).
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code) "
              "VALUES(?,'cancelled','tiktok','tiktok-api','Peachy Wednesday 11/11',?)",
              (sid, "9218490390475003607263"))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,cancelled,cancel_reason) "
              "VALUES(?,?,'465','$1 Perfumes & Beauty 11/10 Part 1',1,1,'was cancelled')", (sid, oid))
    c.commit()

    # TikTok now reports the order ACTIVE (awaiting shipment) — not cancelled.
    order = {"id": oid, "status": "AWAITING_SHIPMENT",
             "line_items": [{"seller_sku": "465", "product_name": "$1 Perfumes & Beauty 11/10 Part 1",
                             "quantity": 1, "sale_price": "52.00"}]}
    A._tt_apply_order(c, order, label="Peachy Wednesday 11/11")

    row = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    assert row["status"] != "cancelled"                       # no longer stuck
    assert row["status"] in ("pending", "picked", "packed")   # back in the flow
    it = c.execute("SELECT cancelled FROM shipment_items WHERE shipment_id=? AND order_id=?", (sid, oid)).fetchone()
    assert it["cancelled"] == 0                                # the line is active again
    n = c.execute("SELECT COUNT(*) n FROM order_events WHERE shipment_id=? AND action='uncancelled'",
                  (sid,)).fetchone()["n"]
    assert n >= 1                                              # audit trail of the correction
    c.close()


def test_genuine_tiktok_cancellation_still_cancels(appmod):
    A = appmod
    oid = "9" + uuid.uuid4().hex[:12]
    sid = "TT-" + oid
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
              "VALUES(?,'pending','tiktok','tiktok-api','L')", (sid,))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,'1','X',1)", (sid, oid))
    c.commit()
    order = {"id": oid, "status": "CANCELLED",
             "line_items": [{"seller_sku": "1", "product_name": "X", "quantity": 1}]}
    A._tt_apply_order(c, order, label="L")
    assert c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()["status"] == "cancelled"
    c.close()


def test_packed_progress_not_reset_when_active(appmod):
    """A normal active order that was already packed keeps 'packed' — the un-cancel only
    touches orders that were actually stuck on 'cancelled'."""
    A = appmod
    oid = "8" + uuid.uuid4().hex[:12]
    sid = "TT-" + oid
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,packed_at) "
              "VALUES(?,'packed','tiktok','tiktok-api','L',CURRENT_TIMESTAMP)", (sid,))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked,picked_at) "
              "VALUES(?,?,'2','Y',1,1,CURRENT_TIMESTAMP)", (sid, oid))
    c.commit()
    order = {"id": oid, "status": "AWAITING_SHIPMENT",
             "line_items": [{"seller_sku": "2", "product_name": "Y", "quantity": 1}]}
    A._tt_apply_order(c, order, label="L")
    assert c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()["status"] == "packed"
    c.close()
