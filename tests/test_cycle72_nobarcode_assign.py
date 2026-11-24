"""Cycle-72: After-Live Cleanup — give a no-barcode photographed sticker a name + price.
/api/live/sticker-assign finds/creates the catalog product, binds the sticker, and records the
sale ONCE (stock deducted exactly once; it wasn't deducted before because it was never matched).
The product is the shared catalog entity, so the name/price applies everywhere it's used."""
import io
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _sold(A, label, sticker, name, qty=1, rev=10.0):
    c = A.sdb(A.DEFAULT_ORG)
    for _ in range(qty):
        sid = "S" + uuid.uuid4().hex[:10]
        c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
                  "VALUES(?,'packed','tiktok','tiktok-api',?)", (sid, label))
        c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) "
                  "VALUES(?,?,?,?,1,?)", (sid, "O" + sid, sticker, name, rev))
    c.commit(); c.close()


def test_photo_then_assign_name_price_records_once(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "HERA Live " + uuid.uuid4().hex[:5]
    _sold(A, label, "77", "Mystery Serum Part 1", qty=3, rev=9.0)   # sold 3, no barcode
    # worker photographs the sticker (photo-only)
    data = {"show": label, "sticker": "77", "part": "1", "file": (io.BytesIO(b"\xff\xd8\xffjpg"), "p.jpg")}
    client.post("/api/live/sticker-photo", data=data, headers=hdr, content_type="multipart/form-data")

    # it shows up as a no-barcode photo gap (has_photo, missing product)
    g = client.get("/api/live/gaps?show=" + label).get_json()
    row = [x for x in g["gaps"] if x["sticker"] == "77"][0]
    assert row["has_photo"] is True and "product" in row["missing"]

    # assign name + OUR COST from the cleanup screen (sale price comes from the CSV later)
    r = client.post("/api/live/sticker-assign",
                    json={"show": label, "sticker": "77", "part": 1, "qty": 3,
                          "name": "Glow Serum", "cost": 4.0}, headers=hdr).get_json()
    assert r["ok"] is True and r["qty"] == 3 and r["cost"] == 4.0
    sku = r["sku"]

    c = A.sdb(A.DEFAULT_ORG)
    # product created with our cost, sticker bound, stock deducted exactly once (3 units -> on_hand -3)
    p = c.execute("SELECT name, on_hand, avg_cost FROM products WHERE sku=?", (sku,)).fetchone()
    assert p["name"] == "Glow Serum" and p["on_hand"] == -3 and p["avg_cost"] == 4.0
    moves = c.execute("SELECT COALESCE(SUM(qty),0) s, COUNT(*) n FROM stock_moves WHERE sku=?", (sku,)).fetchone()
    assert moves["s"] == -3 and moves["n"] == 1          # deducted once
    ls = c.execute("SELECT SUM(qty) q, MAX(unit_cost) uc FROM live_sales WHERE product_sku=?", (sku,)).fetchone()
    assert ls["q"] == 3 and ls["uc"] == 4.0              # our cost recorded; sale price filled by CSV
    c.close()

    # no longer a product-gap
    g2 = client.get("/api/live/gaps?show=" + label).get_json()
    assert not any(x["sticker"] == "77" and "product" in x["missing"] for x in g2["gaps"])

    # assigning again is rejected (don't double-deduct)
    r2 = client.post("/api/live/sticker-assign",
                     json={"show": label, "sticker": "77", "part": 1, "qty": 3, "name": "X"}, headers=hdr).get_json()
    assert r2["ok"] is False


def test_assign_reuses_existing_product_by_name(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "HERA Live " + uuid.uuid4().hex[:5]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,target_price,on_hand) VALUES('EXIST1','Rose Balm',8,5)")
    c.commit(); c.close()
    _sold(A, label, "90", "No BC Part 1", qty=1, rev=8.0)
    r = client.post("/api/live/sticker-assign",
                    json={"show": label, "sticker": "90", "part": 1, "qty": 1, "name": "rose balm"},
                    headers=hdr).get_json()
    assert r["ok"] is True and r["sku"] == "EXIST1"      # matched existing by name (case-insensitive)
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT on_hand FROM products WHERE sku='EXIST1'").fetchone()["on_hand"] == 4
    c.close()
