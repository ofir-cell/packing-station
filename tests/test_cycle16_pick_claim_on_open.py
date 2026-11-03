"""Cycle-16: a floor worker who OPENS a pickable order is recorded as the puller
(pick_started_by) — so an order pulled off the shelf and abandoned with zero item
ticks still shows who took it. Admin/CS inspecting never claims it; first open wins."""
import uuid


def _ship(appmod, sid, status="pending"):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) "
              "VALUES(?,?,'tiktok-api','L','tiktok')", (sid, status))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) "
              "VALUES(?,?,'S1','Lip',1,0)", (sid, "O" + sid))
    c.commit(); c.close()


def _as(client, appmod, name, role):
    uname = name.lower()
    with appmod.update_json(appmod.USERS_FILE) as users:     # so session-revocation sees a live account
        users[uname] = {"password": "x", "role": role, "name": name, "org": appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=appmod.DEFAULT_ORG, name=name, station_name="")
    client.set_cookie("csrf_token", "tok")
    client.csrf = {"X-CSRF-Token": "tok"}
    return client


def _started_by(appmod, sid):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    r = c.execute("SELECT pick_started_by FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    c.close()
    return r["pick_started_by"] if r else None


def test_worker_open_claims_the_pull(appmod, client):
    sid = "pk-" + uuid.uuid4().hex[:6]; _ship(appmod, sid)
    _as(client, appmod, "Dana", "worker")
    r = client.get("/api/pick/" + sid).get_json()
    assert r["ok"] is True
    assert r["pick_started_by"] == "Dana"          # returned to the screen
    assert _started_by(appmod, sid) == "Dana"      # and persisted — even with zero ticks


def test_admin_inspect_does_not_claim(appmod, client):
    sid = "pk-" + uuid.uuid4().hex[:6]; _ship(appmod, sid)
    _as(client, appmod, "Boss", "admin")
    client.get("/api/pick/" + sid + "?force=1")
    assert _started_by(appmod, sid) is None        # admin inspecting never becomes the puller


def test_first_open_wins_no_overwrite(appmod, client):
    sid = "pk-" + uuid.uuid4().hex[:6]; _ship(appmod, sid)
    _as(client, appmod, "Dana", "worker"); client.get("/api/pick/" + sid)
    _as(client, appmod, "Noa", "worker"); client.get("/api/pick/" + sid)
    assert _started_by(appmod, sid) == "Dana"      # the worker who took it first stays recorded


def test_already_picked_order_not_reattributed_on_open(appmod, client):
    sid = "pk-" + uuid.uuid4().hex[:6]; _ship(appmod, sid, status="picked")
    _as(client, appmod, "Dana", "worker")
    client.get("/api/pick/" + sid)
    assert _started_by(appmod, sid) is None        # an already-handled order isn't claimed on open


def test_full_reset_clears_the_claim(appmod, client):
    sid = "pk-" + uuid.uuid4().hex[:6]; _ship(appmod, sid)
    _as(client, appmod, "Dana", "worker"); client.get("/api/pick/" + sid)
    assert _started_by(appmod, sid) == "Dana"
    # Full reset back to pending (manager undo) must clear the claim so it's a fresh pull.
    _as(client, appmod, "Boss", "admin")      # revert is a manager action
    r = client.post("/api/shipment/" + sid + "/revert", json={"to": "pending"}, headers=client.csrf)
    assert r.status_code == 200
    assert _started_by(appmod, sid) is None
