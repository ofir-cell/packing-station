"""Cycle-33: a COMBINED order that carries a free prize (giveaway) alongside a paid
live-sold product can land in the 'giveaway' shipment status. The picking screen showed
both items and let the worker tick them, but 'Done — bring to packer' returned
"Already picked by someone" because pick-complete only accepted status='pending'.
Fix: pick-complete also accepts 'giveaway'. Cancelled/picked/packed/shipped still block."""
import uuid


def _worker(client, A):
    with A.update_json(A.USERS_FILE) as uu:
        uu["w1"] = {"password": "x", "role": "worker", "name": "Dana", "org": A.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="w1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Dana")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _combined_giveaway_order(A, sid, status="giveaway"):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code) "
              "VALUES(?,?,'whatnot','csv','WN Show',?)", (sid, status, "TRK" + sid))
    # a paid live product + a live-giveaway sample, combined into one box
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) "
              "VALUES(?,?,'996','$1 BEAUTY Part 1',1,12)", (sid, "OA" + sid))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) "
              "VALUES(?,?,'PB-LIVE-GIVEAWAY','Fragrance Sample',1,0)", (sid, "OB" + sid))
    c.commit(); c.close()


def test_giveaway_status_combined_order_can_be_picked(appmod, client):
    A = appmod; hdr = _worker(client, A); sid = "PKG" + uuid.uuid4().hex[:6]
    _combined_giveaway_order(A, sid, status="giveaway")
    det = client.get("/api/pick/" + sid).get_json()
    assert det["ok"] and det["already_picked"] is False and len(det["items"]) == 2
    r = client.post("/api/pick/complete/" + sid, headers=hdr).get_json()
    assert r["ok"] is True                                   # was: "Already picked by someone"
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT status, picked_by FROM shipments WHERE shipment_id=?", (sid,)).fetchone(); c.close()
    assert row["status"] == "picked" and row["picked_by"] == "Dana"


def test_pending_order_still_completes(appmod, client):
    A = appmod; hdr = _worker(client, A); sid = "PKP" + uuid.uuid4().hex[:6]
    _combined_giveaway_order(A, sid, status="pending")
    assert client.post("/api/pick/complete/" + sid, headers=hdr).get_json()["ok"] is True


def test_cancelled_order_still_blocks(appmod, client):
    A = appmod; hdr = _worker(client, A); sid = "PKC" + uuid.uuid4().hex[:6]
    _combined_giveaway_order(A, sid, status="cancelled")
    r = client.post("/api/pick/complete/" + sid, headers=hdr).get_json()
    assert r["ok"] is False and "cancel" in r["error"].lower()
