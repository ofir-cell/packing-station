"""Cycle-78: Warehouse Control — broadcast to the floor + hold a shipment from packing/picking."""
import uuid


def _as(client, A, role, user):
    with client.session_transaction() as s:
        s.update(user=user, role=role, roles=[role], org=A.DEFAULT_ORG, name=user)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _ship(A, trk, user="janed"):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:9]
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code,buyer_username,buyer_name)
                 VALUES(?,'pending','tiktok','b','Peach Live',?,?,?)""", (sid, trk, user, "Jane D"))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,1)",
              (sid, "O" + sid, "214", "Serum Part 1"))
    c.commit(); c.close()
    return sid


def test_broadcast_post_and_latest(appmod, client):
    A = appmod; hdr = _as(client, A, "manager", "admin")
    r = client.post("/api/control/broadcast", json={"message": "Break in 10 minutes"}, headers=hdr).get_json()
    assert r["ok"] and r["id"]
    # a worker (Pack/Pick) polls latest and sees it
    w = A.app.test_client()
    with w.session_transaction() as s:
        s.update(user="worker1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Pam")
    g = w.get("/api/control/broadcast/latest").get_json()
    assert g["ok"] and g["broadcast"]["message"] == "Break in 10 minutes" and g["broadcast"]["id"] == r["id"]


def test_hold_blocks_packing_and_lists(appmod, client):
    A = appmod; hdr = _as(client, A, "manager", "admin")
    trk = "9236" + uuid.uuid4().hex[:12]
    _ship(A, trk)
    # find + hold (pack only)
    f = client.get("/api/control/shipment?trk=" + trk, headers=hdr).get_json()
    assert f["ok"] and f["shipment"]["buyer_name"] == "Jane D"
    h = client.post("/api/control/hold", json={"trk": trk, "scope": "pack", "reason": "Address change"}, headers=hdr).get_json()
    assert h["ok"] and h["scope"] == "pack"
    # the packer scanning it is blocked (DO NOT PACK)
    wk = A.app.test_client(); whdr = _as(wk, A, "worker", "worker1")
    pk = wk.get("/api/shipment/" + trk, headers=whdr).get_json()
    assert pk["ok"] is False and pk["held"] is True and pk["hold"]["reason"] == "Address change"
    # pack-only does NOT block picking
    sid = f["shipment"]["shipment_id"]
    pick = wk.get("/api/pick/" + sid, headers=whdr).get_json()
    assert pick["held"] is False
    # it shows in the holds list
    hl = client.get("/api/control/holds", headers=hdr).get_json()
    assert any(x["tracking_code"] == trk for x in hl["holds"])
    # release clears it
    client.post("/api/control/release", json={"trk": trk}, headers=hdr)
    pk2 = wk.get("/api/shipment/" + trk, headers=whdr).get_json()
    assert pk2["ok"] is True and not pk2.get("held")


def test_hold_both_blocks_picking(appmod, client):
    A = appmod; hdr = _as(client, A, "admin", "admin")
    trk = "9400" + uuid.uuid4().hex[:12]
    sid = _ship(A, trk)
    client.post("/api/control/hold", json={"trk": trk, "scope": "both", "reason": "stop"}, headers=hdr)
    wk = A.app.test_client(); whdr = _as(wk, A, "worker", "worker1")
    pick = wk.get("/api/pick/" + sid, headers=whdr).get_json()
    assert pick["held"] is True and pick["hold"]["scope"] == "both"
