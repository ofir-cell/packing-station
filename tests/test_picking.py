"""Workstream C (P0): picking item toggle flips state and is auth-gated."""
import uuid


def _item(appmod, sid):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'tiktok-api','L','tiktok')", (sid, "pending"))
    cur = c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) VALUES(?,?,'S1','Lip',1,0)", (sid, "O" + sid))
    iid = cur.lastrowid; c.commit(); c.close()
    return iid


def test_pick_toggle_flips_and_persists(appmod, admin):
    sid = "pk-" + uuid.uuid4().hex[:6]; iid = _item(appmod, sid)
    r1 = admin.post(f"/api/pick/item/{iid}/toggle", headers=admin.csrf)
    assert r1.status_code == 200
    c = appmod.sdb(appmod.DEFAULT_ORG)
    p1 = c.execute("SELECT COALESCE(picked,0) FROM shipment_items WHERE id=?", (iid,)).fetchone()[0]; c.close()
    assert p1 == 1
    admin.post(f"/api/pick/item/{iid}/toggle", headers=admin.csrf)   # toggle back
    c = appmod.sdb(appmod.DEFAULT_ORG)
    p2 = c.execute("SELECT COALESCE(picked,0) FROM shipment_items WHERE id=?", (iid,)).fetchone()[0]; c.close()
    assert p2 == 0


def test_pick_toggle_requires_auth(client):
    assert client.post("/api/pick/item/1/toggle").status_code != 200
