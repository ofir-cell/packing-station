"""Cycle-19 (stage B): a bundle sticker expands at PACKING into one scannable row per
component, so the packer must scan every barcode; the box is 'complete' only when all are in."""
import uuid


def _as(client, A):
    with client.session_transaction() as s:
        s.update(user="worker1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Pam", station_name="S1")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _prod(A, sku, barcode):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,20,1)", (sku, "P-" + sku, barcode))
    c.commit(); c.close()


def _kit(A, label, sticker, comps):
    c = A.sdb(A.DEFAULT_ORG); A._kit_ensure(c)
    for csku, q in comps:
        c.execute("INSERT OR REPLACE INTO show_kit(import_label,sticker_sku,part,component_sku,qty) VALUES(?,?,0,?,?)",
                  (label, sticker, csku, q))
    c.execute("INSERT INTO settings(key,value) VALUES('pack_scan_items','1') ON CONFLICT(key) DO UPDATE SET value='1'")
    c.commit(); c.close()


def _order(A, label, sticker):
    sid = "box-" + uuid.uuid4().hex[:6]; trk = "9400" + uuid.uuid4().hex[:10]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform) "
              "VALUES(?,?,'pending','tiktok-api',?,'tiktok')", (sid, trk, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,1)",
              (sid, "O" + sid, sticker, "Bundle Deal"))
    c.commit(); c.close()
    return sid, trk


def test_bundle_expands_and_requires_all_components(appmod, client):
    A = appmod; hdr = _as(client, A); lab = "L" + uuid.uuid4().hex[:6]
    a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a, "BCA" + lab); _prod(A, b, "BCB" + lab)
    _kit(A, lab, "50", [(a, 1), (b, 1)])
    sid, trk = _order(A, lab, "50")

    begin = client.post("/api/pack/begin", headers=hdr, json={"tracking": trk}).get_json()
    assert begin["enabled"]
    rows = begin["items"]
    assert len(rows) == 2 and all(r["bundle"] for r in rows)        # expanded into 2 component rows
    assert {r["product_name"] for r in rows} == {"P-" + a, "P-" + b}

    # scan the first component
    r1 = client.post("/api/pack/scan", headers=hdr, json={"tracking": trk, "code": "BCA" + lab}).get_json()
    assert r1["result"] == "ok"
    # box still incomplete — one component not scanned yet
    c = A.sdb(A.DEFAULT_ORG); fin = A._pack_finish(c, A.sdb(A.DEFAULT_ORG).execute(
        "SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone(), None); c.close()
    assert fin["check"] == "missing" and any(m["name"] == "P-" + b for m in fin["missing"])

    # scan the second component → now complete
    r2 = client.post("/api/pack/scan", headers=hdr, json={"tracking": trk, "code": "BCB" + lab}).get_json()
    assert r2["result"] == "ok"
    c = A.sdb(A.DEFAULT_ORG); fin = A._pack_finish(c, A.sdb(A.DEFAULT_ORG).execute(
        "SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone(), None); c.close()
    assert fin["check"] == "complete" and not fin["missing"]


def test_pack_begin_resets_component_progress(appmod, client):
    A = appmod; hdr = _as(client, A); lab = "L" + uuid.uuid4().hex[:6]
    a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a, "BCA" + lab); _prod(A, b, "BCB" + lab)
    _kit(A, lab, "7", [(a, 1), (b, 1)])
    sid, trk = _order(A, lab, "7")
    client.post("/api/pack/begin", headers=hdr, json={"tracking": trk})
    client.post("/api/pack/scan", headers=hdr, json={"tracking": trk, "code": "BCA" + lab})
    # a fresh recording of the same box restarts scanning from zero
    begin = client.post("/api/pack/begin", headers=hdr, json={"tracking": trk}).get_json()
    assert all(r["scanned"] == 0 for r in begin["items"])


def test_duplicate_component_scan_does_not_overcount(appmod, client):
    A = appmod; hdr = _as(client, A); lab = "L" + uuid.uuid4().hex[:6]
    a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a, "BCA" + lab); _prod(A, b, "BCB" + lab)
    _kit(A, lab, "9", [(a, 1), (b, 1)])
    sid, trk = _order(A, lab, "9")
    client.post("/api/pack/begin", headers=hdr, json={"tracking": trk})
    client.post("/api/pack/scan", headers=hdr, json={"tracking": trk, "code": "BCA" + lab})
    dup = client.post("/api/pack/scan", headers=hdr, json={"tracking": trk, "code": "BCA" + lab}).get_json()
    assert dup["result"] == "already"              # same component again ≠ double-count
