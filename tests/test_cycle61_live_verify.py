"""Cycle-61: the Live Mode → Picking verification loop.
- A sticker already matched to a product (in Live Mode) makes the picker's scan VERIFIED: scanning a
  different product warns (mismatch) but can be overridden; scanning the right one passes.
- 'Gaps by sticker' lists a show's sold stickers that still need a product / cost / photo.
"""
import io
import uuid


def _worker(client, A, role="worker"):
    with A.update_json(A.USERS_FILE) as uu:
        uu["w1"] = {"password": "x", "role": role, "name": "Dana", "org": A.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="w1", role=role, roles=[role], org=A.DEFAULT_ORG, name="Dana")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _order(A, label, sticker="465", part=1):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "SHP" + uuid.uuid4().hex[:8]
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
              "VALUES(?,'pending','tiktok','tiktok-api',?)", (sid, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,?,?,1)", (sid, "O" + sid, sticker, "BEAUTY " + label + " Part " + str(part)))
    iid = c.execute("SELECT id FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()["id"]
    c.commit(); c.close()
    return iid


def _products(A):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR IGNORE INTO products(sku,name,barcode,on_hand,avg_cost) VALUES('P-A','Serum A','1111111111111',5,3)")
    c.execute("INSERT OR IGNORE INTO products(sku,name,barcode,on_hand,avg_cost) VALUES('P-B','Lotion B','2222222222222',5,4)")
    c.commit(); c.close()


def test_scan_mismatch_warns_then_override(appmod, client):
    A = appmod; hdr = _worker(client, A); _products(A)
    label = "LIVE " + uuid.uuid4().hex[:4]
    iid = _order(A, label, sticker="465", part=1)
    # Live Mode already matched sticker 465/part1 to product A
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,?,?)",
              (label, "465", 1, "P-A")); c.commit(); c.close()

    # scanning the WRONG product (B) → mismatch warning, NOT picked
    r = client.post("/api/pick/item/%d/scan" % iid, json={"code": "2222222222222"}, headers=hdr).get_json()
    assert r["ok"] is False and r["mismatch"] is True
    assert r["expected"]["sku"] == "P-A" and r["scanned"]["sku"] == "P-B"
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT picked FROM shipment_items WHERE id=?", (iid,)).fetchone()["picked"] == 0
    c.close()

    # override → picks anyway (the mapping may have been wrong)
    r2 = client.post("/api/pick/item/%d/scan" % iid, json={"code": "2222222222222", "override": True}, headers=hdr).get_json()
    assert r2["ok"] is True and r2["picked"] == 1


def test_scan_right_product_passes(appmod, client):
    A = appmod; hdr = _worker(client, A); _products(A)
    label = "LIVE " + uuid.uuid4().hex[:4]
    iid = _order(A, label, sticker="77", part=1)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,?,?)",
              (label, "77", 1, "P-A")); c.commit(); c.close()
    r = client.post("/api/pick/item/%d/scan" % iid, json={"code": "1111111111111"}, headers=hdr).get_json()
    assert r["ok"] is True and r["picked"] == 1          # expected product → verified, no warning


def test_gaps_by_sticker(appmod, client):
    A = appmod; hdr = _worker(client, A, role="admin")
    label = "LIVE " + uuid.uuid4().hex[:4]
    _order(A, label, sticker="300", part=1)              # sold, never matched → a gap
    g = client.get("/api/live/gaps?show=" + label).get_json()
    assert g["ok"] is True
    row = next((x for x in g["gaps"] if x["sticker"] == "300"), None)
    assert row and "product" in row["missing"] and "photo" in row["missing"]


def test_sticker_photo_upload(appmod, client):
    A = appmod; hdr = _worker(client, A)
    label = "LIVE " + uuid.uuid4().hex[:4]
    _order(A, label, sticker="88", part=2)
    data = {"show": label, "sticker": "88", "part": "2",
            "file": (io.BytesIO(b"\xff\xd8\xff\xe0jpegbytes"), "p.jpg")}
    r = client.post("/api/live/sticker-photo", data=data, headers=hdr, content_type="multipart/form-data").get_json()
    assert r["ok"] is True and "/live-photo" in r["photo_view_url"]
    c = A.sdb(A.DEFAULT_ORG)
    m = c.execute("SELECT photo_url FROM show_product_map WHERE import_label=? AND sticker_sku='88' AND part=2", (label,)).fetchone()
    c.close()
    assert m and m["photo_url"]                          # photo stored against the sticker
