"""CSV import: a cancelled line cancels ONLY that product — never the sold products in the
same order (they used to show up on the cleanup screen and the box flipped to cancelled)."""
import io, uuid

TT_HDR = ["Order ID", "Order Status", "Cancel Reason", "Package ID", "Tracking ID", "Seller SKU", "Product Name",
          "Quantity", "Buyer Username", "Recipient", "Address Line 1", "City", "State", "Zipcode", "Created Time"]


def _csv(rows):
    out = io.StringIO(); out.write(",".join(TT_HDR) + "\n")
    for r in rows: out.write(",".join('"%s"' % r.get(h, "") for h in TT_HDR) + "\n")
    return out.getvalue().encode()


def _row(t, oid, pkg, sku, status="To ship", reason=""):
    return {"Order ID": oid + t, "Order Status": status, "Cancel Reason": reason, "Package ID": pkg + t,
            "Tracking ID": "9400" + t + pkg, "Seller SKU": sku, "Product Name": "Peach Live Part 1", "Quantity": "1",
            "Buyer Username": "amy" + t, "Recipient": "Amy", "Address Line 1": "1 Main", "City": "Miami", "State": "FL",
            "Zipcode": "33101", "Created Time": "10/29/2026 19:00:00"}


def _as(client, A):
    with client.session_transaction() as s:
        s.clear(); s.update(user="admin", role="admin", roles=["admin"], name="admin", org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _imp(client, hdr, rows, label, kind=None, force=False):
    data = {"file": (io.BytesIO(_csv(rows)), "show.csv"), "label": label}
    if kind: data["kind"] = kind
    if force: data["force"] = "1"
    return client.post("/api/shipments/import", headers=hdr, content_type="multipart/form-data", data=data).get_json()


def _lines(A, pkg):
    c = A.sdb(A.DEFAULT_ORG)
    st = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (pkg,)).fetchone()
    ls = {r["sku"]: r["cancelled"] for r in c.execute("SELECT sku, COALESCE(cancelled,0) cancelled FROM shipment_items WHERE shipment_id=?", (pkg,))}
    c.close()
    return (st["status"] if st else None), ls


def _cleanup_skus(A, label):
    with A.app.test_request_context():
        from flask import session
        session["org"] = A.DEFAULT_ORG
        return sorted(g["sku"] for g in A._cleanup_groups(label))


def test_partial_cancel_in_a_to_ship_file_cancels_only_that_product(appmod, client):
    A = appmod; hdr = _as(client, A); t = uuid.uuid4().hex[:6]; label = "CSV Live " + t
    d = _imp(client, hdr, [_row(t, "O1", "P1", "940"), _row(t, "O1", "P1", "212"),
                           _row(t, "O1", "P1", "57", status="Cancelled", reason="Buyer changed mind")], label)
    assert d["ok"]
    status, ls = _lines(A, "P1" + t)
    assert ls == {"940": 0, "212": 0, "57": 1} and status == "pending"     # sold stay, cancelled one is listed
    assert _cleanup_skus(A, label) == ["57"]                                # take #57 off the table, nothing else


def test_whole_order_cancelled_still_cancels_the_box(appmod, client):
    A = appmod; hdr = _as(client, A); t = uuid.uuid4().hex[:6]; label = "CSV Live " + t
    _imp(client, hdr, [_row(t, "O1", "P1", "940"), _row(t, "O1", "P1", "212")], label)
    _imp(client, hdr, [_row(t, "O1", "P1", "940", "Cancelled", "x"), _row(t, "O1", "P1", "212", "Cancelled", "x")],
         label, kind="tiktok_cancel")
    status, ls = _lines(A, "P1" + t)
    assert ls == {"940": 1, "212": 1} and status == "cancelled"


def test_cancellations_file_with_one_product_cancels_only_that_product(appmod, client):
    A = appmod; hdr = _as(client, A); t = uuid.uuid4().hex[:6]; label = "CSV Live " + t
    _imp(client, hdr, [_row(t, "O1", "P1", "940"), _row(t, "O1", "P1", "212")], label)
    _imp(client, hdr, [_row(t, "O1", "P1", "212", "Cancelled", "x")], label, kind="tiktok_cancel")
    status, ls = _lines(A, "P1" + t)
    assert ls == {"940": 0, "212": 1} and status == "pending"


def test_reuploading_repairs_orders_the_old_bug_cancelled(appmod, client):
    """Simulate the old damage (every line cancelled, box flipped), then re-upload the files."""
    A = appmod; hdr = _as(client, A); t = uuid.uuid4().hex[:6]; label = "CSV Live " + t
    rows = [_row(t, "O1", "P1", "940"), _row(t, "O1", "P1", "212"), _row(t, "O1", "P1", "57", "Cancelled", "x")]
    _imp(client, hdr, rows, label)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipment_items SET cancelled=1 WHERE shipment_id=?", ("P1" + t,))
    c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", ("P1" + t,))
    c.commit(); c.close()
    assert _imp(client, hdr, rows, label, force=True)["ok"]                  # same To-Ship file, "import anyway"
    status, ls = _lines(A, "P1" + t)
    assert ls == {"940": 0, "212": 0, "57": 1} and status == "pending"
    # and via a cancellations file
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipment_items SET cancelled=1 WHERE shipment_id=?", ("P1" + t,))
    c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", ("P1" + t,))
    c.commit(); c.close()
    _imp(client, hdr, [_row(t, "O1", "P1", "57", "Cancelled", "x")], label, kind="tiktok_cancel", force=True)
    status, ls = _lines(A, "P1" + t)
    assert ls == {"940": 0, "212": 0, "57": 1} and status == "pending"


def test_repair_keeps_picking_progress(appmod, client):
    A = appmod; hdr = _as(client, A); t = uuid.uuid4().hex[:6]; label = "CSV Live " + t
    rows = [_row(t, "O1", "P1", "940"), _row(t, "O1", "P1", "57", "Cancelled", "x")]
    _imp(client, hdr, rows, label)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipment_items SET picked=1, picked_at='2026-10-30T09:00:00', cancelled=1 WHERE shipment_id=? AND sku='940'", ("P1" + t,))
    c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", ("P1" + t,))
    c.commit(); c.close()
    _imp(client, hdr, rows, label, force=True)
    status, ls = _lines(A, "P1" + t)
    assert ls["940"] == 0 and status == "picked"


def test_cancel_row_without_a_product_cancels_the_whole_order(appmod, client):
    A = appmod; hdr = _as(client, A); t = uuid.uuid4().hex[:6]; label = "CSV Live " + t
    _imp(client, hdr, [_row(t, "O1", "P1", "940"), _row(t, "O1", "P1", "212")], label)
    c = A.sdb(A.DEFAULT_ORG)
    A._apply_cancel_rows(c, [{"order_id": "O1" + t, "quantity": 2, "cancel_reason": "buyer"}], "whatnot", label, "b")
    c.commit(); c.close()
    status, ls = _lines(A, "P1" + t)
    assert ls == {"940": 1, "212": 1} and status == "cancelled"
