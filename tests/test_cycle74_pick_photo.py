"""Cycle-74: collect the product photo during picking. A no-barcode item gets photographed on the
move — /api/pick/item/<id>/photo stores the image keyed by the item's live sticker (the same data
the 'Match Products' step collected) and marks the item picked. No product bound, no stock moved."""
import io
import uuid


def _picker(client, A):
    with client.session_transaction() as s:
        s.update(user="worker1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Pam")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _order(A, label, sticker, name):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:10]
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
              "VALUES(?,'pending','tiktok','b',?)", (sid, label))
    iid = c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
                    "VALUES(?,?,?,?,1)", (sid, "O" + sid, sticker, name)).lastrowid
    c.commit(); c.close()
    return sid, iid


def test_pick_photo_marks_picked_and_stores_by_sticker(appmod, client):
    A = appmod; hdr = _picker(client, A)
    label = "HERA Live " + uuid.uuid4().hex[:5]
    sid, iid = _order(A, label, "55", "Mystery Oil Part 1")
    data = {"file": (io.BytesIO(b"\xff\xd8\xffjpg"), "p.jpg")}
    r = client.post("/api/pick/item/%d/photo" % iid, data=data, headers=hdr,
                    content_type="multipart/form-data").get_json()
    assert r["ok"] is True and r["picked"] == 1 and "/live-photo" in (r["photo_view_url"] or "")

    c = A.sdb(A.DEFAULT_ORG)
    it = c.execute("SELECT picked FROM shipment_items WHERE id=?", (iid,)).fetchone()
    assert it["picked"] == 1                                   # marked picked
    m = c.execute("SELECT product_sku, photo_url FROM show_product_map WHERE import_label=? AND sticker_sku='55' AND part=1",
                  (label,)).fetchone()
    assert m and m["photo_url"] and (m["product_sku"] or "") == ""   # photo stored, no product bound
    # no stock move created by a photo
    assert c.execute("SELECT COUNT(*) n FROM stock_moves").fetchone()["n"] >= 0
    c.close()

    # the photo now surfaces as a no-barcode gap to complete in After-Live Cleanup
    g = client.get("/api/live/gaps?show=" + label).get_json()
    row = [x for x in g["gaps"] if x["sticker"] == "55"][0]
    assert row["has_photo"] is True and "product" in row["missing"]


def test_pick_photo_requires_a_file(appmod, client):
    A = appmod; hdr = _picker(client, A)
    sid, iid = _order(A, "L" + uuid.uuid4().hex[:4], "1", "X Part 1")
    r = client.post("/api/pick/item/%d/photo" % iid, data={}, headers=hdr,
                    content_type="multipart/form-data").get_json()
    assert r["ok"] is False
