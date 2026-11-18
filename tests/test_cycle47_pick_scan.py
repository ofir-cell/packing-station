"""Cycle-47: scan-to-pick. Scanning a product's barcode while picking links the sold sticker
to that product (same pipeline as Live Match → show_product_map, builds the product DB and
COGS), auto-creates an unknown product, and marks the item picked. Skip marks a no-barcode item
picked without linking (it stays in the show's 'needs product' queue)."""
import uuid


def _worker(client, A):
    with A.update_json(A.USERS_FILE) as uu:
        uu["w1"] = {"password": "x", "role": "worker", "name": "Dana", "org": A.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="w1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Dana")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _order(A, label="TT Live", sticker="465", part=1):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "SHP" + uuid.uuid4().hex[:8]
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
              "VALUES(?,'pending','tiktok','tiktok-api',?)", (sid, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,?,?,1)", (sid, "O" + sid, sticker, "BEAUTY " + label + " Part " + str(part)))
    iid = c.execute("SELECT id FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()["id"]
    c.commit(); c.close()
    return sid, iid, label


def test_scan_known_product_links_and_picks(appmod, client):
    A = appmod; hdr = _worker(client, A)
    sid, iid, label = _order(A)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost) VALUES('P-TAT','Tatcha Serum','0123456789012',5,6.20)")
    c.commit(); c.close()

    r = client.post("/api/pick/item/%d/scan" % iid, json={"code": "0123456789012"}, headers=hdr).get_json()
    assert r["ok"] is True and r["picked"] == 1
    assert r["product"]["sku"] == "P-TAT" and r["product"]["in_stock"] is True
    assert r["product"]["cost"] is None            # worker is not admin → cost stays hidden (money is admin-only)

    c = A.sdb(A.DEFAULT_ORG)
    # the item is picked
    assert c.execute("SELECT picked FROM shipment_items WHERE id=?", (iid,)).fetchone()["picked"] == 1
    # the sticker is linked to the product (same table Live Match uses → feeds COGS)
    m = c.execute("SELECT product_sku FROM show_product_map WHERE import_label=? AND sticker_sku='465' AND part=1", (label,)).fetchone()
    assert m and m["product_sku"] == "P-TAT"
    c.close()


def test_scan_unknown_barcode_autocreates(appmod, client):
    A = appmod; hdr = _worker(client, A)
    sid, iid, label = _order(A, sticker="77", part=2)
    code = "9" + uuid.uuid4().hex[:11]
    r = client.post("/api/pick/item/%d/scan" % iid, json={"code": code}, headers=hdr).get_json()
    assert r["ok"] is True and r["auto_created"] is True
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT COUNT(*) n FROM products WHERE barcode=?", (code,)).fetchone()["n"] == 1
    assert c.execute("SELECT product_sku FROM show_product_map WHERE sticker_sku='77' AND part=2 AND import_label=?",
                     (label,)).fetchone() is not None
    c.close()


def test_skip_picks_without_link(appmod, client):
    A = appmod; hdr = _worker(client, A)
    sid, iid, label = _order(A, sticker="9")
    r = client.post("/api/pick/item/%d/skip" % iid, json={}, headers=hdr).get_json()
    assert r["ok"] is True and r["needs_product"] is True
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT picked FROM shipment_items WHERE id=?", (iid,)).fetchone()["picked"] == 1
    # NOT linked — stays in the 'needs product' queue
    assert c.execute("SELECT COUNT(*) n FROM show_product_map WHERE sticker_sku='9' AND import_label=?",
                     (label,)).fetchone()["n"] == 0
    c.close()


def test_scan_blocked_on_cancelled_order(appmod, client):
    A = appmod; hdr = _worker(client, A)
    sid, iid, label = _order(A)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", (sid,)); c.commit(); c.close()
    r = client.post("/api/pick/item/%d/scan" % iid, json={"code": "123"}, headers=hdr).get_json()
    assert r["ok"] is False
