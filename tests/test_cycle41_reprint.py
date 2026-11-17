"""Cycle-41: reprint-by-sticker. /api/reprint resolves (show, sticker, part) to the TikTok
package(s) so the label can be re-fetched and printed. This test covers the RESOLUTION logic
(sticker+part → the right package, part disambiguation, combined-package dedup, not-found).
The actual TikTok document fetch needs live credentials and is verified on-device."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _order(A, label, pkg, sku, part, buyer="Jane", trk=None, cancelled=0):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR IGNORE INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code,buyer_name) "
              "VALUES(?,'pending','tiktok','tiktok-api',?,?,?)", (pkg, label, trk or ("TRK" + pkg), buyer))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,cancelled) "
              "VALUES(?,?,?,?,1,?)", (pkg, "O" + pkg + sku, sku, "BEAUTY " + label + " PART " + str(part), cancelled))
    c.commit(); c.close()


def test_resolves_sticker_and_part_to_package(appmod, client):
    A = appmod; hdr = _admin(client, A)
    lbl = "SIVAN " + uuid.uuid4().hex[:5]
    _order(A, lbl, "PKG-A", "584", 1, buyer="Buyer One")
    _order(A, lbl, "PKG-B", "584", 2, buyer="Buyer Two")   # same sticker, different part = different package
    # part 1 → PKG-A only
    r = client.post("/api/reprint", json={"show": lbl, "sticker": "584", "part": 1}, headers=hdr).get_json()
    pids = [p["package_id"] for p in r["packages"]]
    assert pids == ["PKG-A"]
    assert r["packages"][0]["buyer"] == "Buyer One"
    # default BOTH maps to TikTok's combined document type (one PDF with label + slip)
    kinds = [d["type"] for d in r["packages"][0]["docs"]]
    assert kinds == ["SHIPPING_LABEL_AND_PACKING_SLIP"]
    # part 2 → PKG-B only
    r2 = client.post("/api/reprint", json={"show": lbl, "sticker": "584", "part": 2}, headers=hdr).get_json()
    assert [p["package_id"] for p in r2["packages"]] == ["PKG-B"]


def test_combined_package_dedup(appmod, client):
    """Two stickers sharing one package (combined order) return that package once."""
    A = appmod; hdr = _admin(client, A)
    lbl = "SIVAN " + uuid.uuid4().hex[:5]
    # sticker 510 appears twice under the SAME package (combined) in part 2
    _order(A, lbl, "PKG-C", "510", 2)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES('PKG-C','O-extra','510','BEAUTY " + lbl + " PART 2',1)")
    c.commit(); c.close()
    r = client.post("/api/reprint", json={"show": lbl, "sticker": "510", "part": 2}, headers=hdr).get_json()
    assert len(r["packages"]) == 1 and r["packages"][0]["package_id"] == "PKG-C"


def test_not_found_for_missing_sticker(appmod, client):
    A = appmod; hdr = _admin(client, A)
    lbl = "SIVAN " + uuid.uuid4().hex[:5]
    _order(A, lbl, "PKG-D", "999", 1)
    r = client.post("/api/reprint", json={"show": lbl, "sticker": "123", "part": 1}, headers=hdr).get_json()
    assert r["ok"] is False and r.get("not_found") is True


def test_cancelled_line_excluded(appmod, client):
    A = appmod; hdr = _admin(client, A)
    lbl = "SIVAN " + uuid.uuid4().hex[:5]
    _order(A, lbl, "PKG-E", "77", 1, cancelled=1)
    r = client.post("/api/reprint", json={"show": lbl, "sticker": "77", "part": 1}, headers=hdr).get_json()
    assert r.get("not_found") is True        # cancelled items aren't reprinted
