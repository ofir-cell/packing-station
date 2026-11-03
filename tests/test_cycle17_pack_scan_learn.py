"""Cycle-17: learn-on-pack-scan. When a packer scans a barcode that isn't in the catalog,
bind it to the expected item's product (pull name/image, create the product if needed) and
count it packed — so the same barcode is recognized normally next time."""
import uuid


def _as_admin(client, appmod):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=appmod.DEFAULT_ORG, name="Packer", station_name="A1")
    client.set_cookie("csrf_token", "tok")
    client.csrf = {"X-CSRF-Token": "tok"}
    return client


def _order(appmod, sku, label, sticker="101", linked=True, barcode=None):
    """One TikTok-API order with a single item on `sticker`, under its own `label` so tests
    don't cross-contaminate. If linked, catalog product `sku` (name+image) is bound to the
    sticker — optionally already carrying a barcode."""
    sid = "box-" + uuid.uuid4().hex[:6]; trk = "9400" + uuid.uuid4().hex[:10]
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform) "
              "VALUES(?,?,'pending','tiktok-api',?,'tiktok')", (sid, trk, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,pack_scanned_qty) "
              "VALUES(?,?,?,?,1,0)", (sid, "O" + sid, sticker, "Glow Serum"))
    if linked:
        if barcode is not None:
            c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,image_url,updated_at) "
                      "VALUES(?,'Glow Serum',?, 'http://img/serum.jpg', datetime('now'))", (sku, barcode))
        else:
            c.execute("INSERT OR IGNORE INTO products(sku,name,image_url,updated_at) "
                      "VALUES(?,'Glow Serum','http://img/serum.jpg', datetime('now'))", (sku,))
        c.execute("INSERT OR REPLACE INTO show_product_map(import_label,sticker_sku,part,product_sku) "
                  "VALUES(?,?,0,?)", (label, sticker, sku))
    iid = c.execute("SELECT id FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()["id"]
    c.commit(); c.close()
    return sid, trk, iid


def _barcode_of(appmod, sku):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    r = c.execute("SELECT barcode FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    return r["barcode"] if r else None


def _u():
    return "SKU" + uuid.uuid4().hex[:8], "L" + uuid.uuid4().hex[:6]


def test_unknown_barcode_is_learned_onto_expected_item(appmod, client):
    _as_admin(client, appmod); sku, label = _u()
    sid, trk, iid = _order(appmod, sku, label, barcode=None)
    r = client.post("/api/pack/scan", json={"tracking": trk, "code": "0123456789012",
                                            "expected_item_id": iid, "station": "A1"},
                    headers=client.csrf).get_json()
    assert r["ok"] and r["result"] == "learned"
    assert r["product"] == "Glow Serum"                 # pulled the name
    assert _barcode_of(appmod, sku) == "0123456789012"  # barcode now learned onto the product
    c = appmod.sdb(appmod.DEFAULT_ORG)
    assert c.execute("SELECT pack_scanned_qty FROM shipment_items WHERE id=?", (iid,)).fetchone()[0] == 1
    assert c.execute("SELECT result FROM pack_scans WHERE shipment_id=? ORDER BY id DESC", (sid,)).fetchone()[0] == "learned"
    c.close()


def test_relearned_barcode_is_recognized_next_time(appmod, client):
    _as_admin(client, appmod); sku, label = _u()
    sid, trk, iid = _order(appmod, sku, label, barcode=None)
    client.post("/api/pack/scan", json={"tracking": trk, "code": "5555555555555", "expected_item_id": iid}, headers=client.csrf)
    # a second order for the SAME product (same sku, same label binding): the now-known barcode = normal 'ok'
    sid2, trk2, iid2 = _order(appmod, sku, label, barcode=None)
    r = client.post("/api/pack/scan", json={"tracking": trk2, "code": "5555555555555", "expected_item_id": iid2},
                    headers=client.csrf).get_json()
    assert r["ok"] and r["result"] == "ok"              # recognized, not re-learned


def test_known_different_barcode_is_wrong_not_relearned(appmod, client):
    _as_admin(client, appmod); sku, label = _u()
    sid, trk, iid = _order(appmod, sku, label, barcode="1111111111111")
    r = client.post("/api/pack/scan", json={"tracking": trk, "code": "9999999999999", "expected_item_id": iid},
                    headers=client.csrf).get_json()
    assert r["ok"] and r["result"] == "wrong"           # product already has a barcode -> genuine mismatch
    assert _barcode_of(appmod, sku) == "1111111111111"  # not clobbered


def test_label_looking_code_is_not_learned(appmod, client):
    _as_admin(client, appmod); sku, label = _u()
    sid, trk, iid = _order(appmod, sku, label, barcode=None)
    r = client.post("/api/pack/scan", json={"tracking": trk, "code": "9405511899223197428490",
                                            "expected_item_id": iid}, headers=client.csrf).get_json()
    assert r["result"] in ("next_label", "wrong")       # a tracking-shaped code never becomes a product
    assert _barcode_of(appmod, sku) is None
