"""Cycle-31 (regression): cancellations are matched DIRECTLY against the orders CSV you
upload — not only against the API. Upload a To-Ship orders CSV, then a cancellations CSV
for the same order; the cancellation is matched by Order ID and the item shows up in Table
Cleanup (gating picking), exactly like Whatnot. Guards the real warehouse flow."""
import io
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


_HDR = ["Order ID", "Tracking ID", "Package ID", "Seller SKU", "Product Name", "Quantity", "Order Status", "Zipcode"]


def _csv(rows):
    out = ",".join(_HDR) + "\n"
    for r in rows:
        out += ",".join(str(r.get(h, "")) for h in _HDR) + "\n"
    return out.encode()


def _post_csv(client, hdr, content, label, kind=None):
    data = {"file": (io.BytesIO(content), "f.csv"), "label": label}
    if kind:
        data["kind"] = kind
    return client.post("/api/shipments/import", data=data, headers=hdr, content_type="multipart/form-data").get_json()


def test_cancel_csv_matches_uploaded_orders_csv_and_shows_in_cleanup(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "TT CSV " + uuid.uuid4().hex[:5]
    oid = "O" + uuid.uuid4().hex[:8]
    # 1) the orders (To-Ship) CSV — creates the line, NOT from the API
    r1 = _post_csv(client, hdr, _csv([{"Order ID": oid, "Tracking ID": "TRK" + oid, "Package ID": "PKG" + oid,
                                       "Seller SKU": "940", "Product Name": "Gucci Lipstick Part 1",
                                       "Quantity": "1", "Order Status": "Awaiting shipment", "Zipcode": "10001"}]), label)
    assert r1["ok"] and r1["format"] == "tiktok" and r1["shipments_new"] == 1
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("""SELECT i.cancelled, s.import_batch FROM shipment_items i JOIN shipments s ON s.shipment_id=i.shipment_id
                       WHERE i.order_id=?""", (oid,)).fetchone(); c.close()
    assert row and row["cancelled"] == 0 and not row["import_batch"].startswith("tiktok-api")   # came from the CSV, not the API

    # 2) the cancellations CSV for the SAME order — matched by Order ID against the uploaded orders
    r2 = _post_csv(client, hdr, _csv([{"Order ID": oid, "Tracking ID": "TRK" + oid, "Package ID": "PKG" + oid,
                                       "Seller SKU": "940", "Product Name": "Gucci Lipstick Part 1",
                                       "Quantity": "1", "Order Status": "Canceled", "Zipcode": "10001"}]), label, kind="tiktok_cancel")
    assert r2["ok"] and r2["format"] == "cancellation" and r2["orders_matched_existing"] == 1

    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT cancelled FROM shipment_items WHERE order_id=?", (oid,)).fetchone()["cancelled"] == 1
    c.close()

    # 3) it surfaces in Table Cleanup (gates picking) — the comparison is against the uploaded orders
    sid = "PKG" + oid
    r3 = client.get("/api/pick/" + sid).get_json()
    assert r3["cleanup"]["has_cancellations"] is True
    assert r3["cleanup_blocked"] is True
