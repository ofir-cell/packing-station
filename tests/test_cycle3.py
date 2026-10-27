"""Cycle-3 regression coverage.

Q1  pack upload resolves USPS-prefixed scans via the shared substring resolver
Q3  CSV cancel restores depleted stock and closes a fully-cancelled shipment
Q5  pick-complete refuses a flagged 'issue' shipment (no silent no-op)
E4  concurrent _receive_stock never loses an increment
E3  admin-authoritative label resolve (true-admin only; no re-buy)
S8  hire hard-delete revokes the orphaned control-plane login
S3  deleted user's session is revoked; a demotion re-syncs roles next request
"""
import uuid, threading


def _mk_ship(appmod, sid, tracking, status="pending"):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("""INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform)
                 VALUES(?,?,?,'b','L','tiktok')""", (sid, tracking, status))
    c.commit(); c.close()


# ---------- Q1 ----------
def test_pack_upload_resolves_usps_prefix(appmod, admin):
    tracking = "9400" + uuid.uuid4().hex[:14]          # 18-char stored tracking
    scanned = "420921" + tracking                       # IMpb-style prefixed scan
    sid = "Q1" + uuid.uuid4().hex[:6]
    _mk_ship(appmod, sid, tracking)
    r = admin.post("/api/upload", data={"tracking": scanned, "station": "S0", "duration": "3"},
                   headers=admin.csrf, content_type="multipart/form-data")
    assert r.get_json()["ok"] is True
    c = appmod.sdb(appmod.DEFAULT_ORG)
    st = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()["status"]
    c.close()
    assert st == "packed", f"prefixed scan did not pack the shipment (status={st})"


# ---------- Q3 ----------
def test_cancel_restores_stock_and_closes_shipment(appmod):
    org = appmod.DEFAULT_ORG
    c = appmod.sdb(org)
    sku = "CXK" + uuid.uuid4().hex[:6]
    c.execute("INSERT INTO products(sku,name,on_hand,avg_cost,updated_at) VALUES(?,?,?,?,datetime('now'))",
              (sku, "Widget", 10, 1.0))
    sid = "Q3" + uuid.uuid4().hex[:6]
    oid = "O" + uuid.uuid4().hex[:6]
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'b','L','tiktok')",
              (sid, "pending"))
    # one depleted line (as if already packed): 3 units off the shelf
    c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,depleted_qty,depleted_sku)
                 VALUES(?,?,?,?,3,3,?)""", (sid, oid, sku, "Widget", sku))
    c.commit(); c.close()

    c = appmod.sdb(org)
    appmod._apply_cancel_rows(c, [{"order_id": oid, "quantity": 3, "cancel_reason": "buyer"}],
                              "tiktok", "L", "cancel_batch")
    c.commit()
    on_hand = c.execute("SELECT on_hand FROM products WHERE sku=?", (sku,)).fetchone()["on_hand"]
    st = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()["status"]
    dq = c.execute("SELECT COALESCE(depleted_qty,0) FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()[0]
    c.close()
    assert on_hand == 13, f"stock not restored (on_hand={on_hand}, expected 13)"
    assert st == "cancelled", f"fully-cancelled shipment not closed (status={st})"
    assert dq == 0, "depletion marker not cleared after restore"


# ---------- Q5 ----------
def test_pick_complete_refuses_issue(appmod, admin):
    sid = "Q5" + uuid.uuid4().hex[:6]
    _mk_ship(appmod, sid, None, status="issue")
    r = admin.post(f"/api/pick/complete/{sid}", json={}, headers=admin.csrf)
    j = r.get_json()
    assert j["ok"] is False and "issue" in j["error"].lower()


# ---------- E4 ----------
def test_receive_stock_concurrent_no_lost_update(appmod):
    org = appmod.DEFAULT_ORG
    sku = "E4K" + uuid.uuid4().hex[:6]
    c = appmod.sdb(org)
    c.execute("INSERT INTO products(sku,name,on_hand,avg_cost,updated_at) VALUES(?,?,0,0,datetime('now'))", (sku, "Thing"))
    c.commit(); c.close()

    N = 20
    def worker():
        cc = appmod.sdb(org)
        with appmod.app.test_request_context():
            appmod._receive_stock(cc, sku, 1, 2.0, note="t")
        cc.commit(); cc.close()

    ts = [threading.Thread(target=worker) for _ in range(N)]
    for t in ts: t.start()
    for t in ts: t.join()

    c = appmod.sdb(org)
    on_hand = c.execute("SELECT on_hand FROM products WHERE sku=?", (sku,)).fetchone()["on_hand"]
    c.close()
    assert on_hand == N, f"lost update: on_hand={on_hand}, expected {N}"


# ---------- E3 ----------
def _seed_uncertain(appmod, rid, sid):
    c = appmod.sdb(appmod.DEFAULT_ORG); appmod._label_claim_ensure(c)
    now = appmod.datetime.now().isoformat(timespec="seconds")
    c.execute("INSERT INTO label_purchases(rate_id,shipment_id,status,idem_key,created_at,updated_at) VALUES(?,?,?,?,?,?)",
              (rid, sid, "uncertain", "idem_"+rid, now, now))
    c.commit(); c.close()


def test_label_resolve_admin_bought(appmod, admin):
    rid = "R" + uuid.uuid4().hex[:8]; sid = "S" + uuid.uuid4().hex[:5]
    _seed_uncertain(appmod, rid, sid)
    r = admin.post("/api/label/resolve", json={"rate_id": rid, "outcome": "bought", "tracking": "TRKX"},
                   headers=admin.csrf)
    assert r.get_json().get("status") == "bought"
    c = appmod.sdb(appmod.DEFAULT_ORG)
    row = c.execute("SELECT status,tracking FROM label_purchases WHERE rate_id=?", (rid,)).fetchone()
    c.close()
    assert row["status"] == "bought" and row["tracking"] == "TRKX"


def test_label_resolve_requires_true_admin(appmod, client):
    rid = "R" + uuid.uuid4().hex[:8]; sid = "S" + uuid.uuid4().hex[:5]
    _seed_uncertain(appmod, rid, sid)
    mgr = "mgr"+uuid.uuid4().hex[:5]
    with appmod.update_json(appmod.USERS_FILE) as users:
        users[mgr] = {"password": "x", "role": "manager", "name": "M", "org": appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user=mgr, role="manager", roles=["manager"], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    r = client.post("/api/label/resolve", json={"rate_id": rid, "outcome": "bought"}, headers={"X-CSRF-Token": "tok"})
    assert r.status_code == 403


# ---------- S8 ----------
def test_hire_delete_revokes_login(appmod, admin):
    org = appmod.DEFAULT_ORG
    uname = "hire" + uuid.uuid4().hex[:6]
    c = appmod.sdb(org)
    cur = c.execute("""INSERT INTO new_hires(full_name,role_target,provisioned_username,invite_token)
                       VALUES('Jane','worker',?,?)""", (uname, uuid.uuid4().hex))
    hid = cur.lastrowid
    c.commit(); c.close()
    with appmod.update_json(appmod.USERS_FILE) as users:
        users[uname] = {"password": "x", "role": "worker", "name": "Jane", "org": org, "from_hire_id": hid}
    r = admin.delete(f"/api/hires/{hid}", headers=admin.csrf)
    assert r.get_json()["ok"] is True
    users = appmod.ldj(appmod.USERS_FILE)
    assert uname not in users, "orphaned login survived hire deletion"


# ---------- S3 ----------
def test_session_revoked_when_user_deleted(appmod, client):
    org = appmod.DEFAULT_ORG
    ghost = "ghost" + uuid.uuid4().hex[:6]
    with client.session_transaction() as s:
        s.update(user=ghost, role="admin", roles=["admin"], org=org)   # user not in users.json
    client.set_cookie("csrf_token", "tok")
    r = client.get("/api/users")
    assert r.status_code == 401, f"deleted user kept access ({r.status_code})"


def test_demotion_resyncs_roles(appmod, client):
    org = appmod.DEFAULT_ORG
    uname = "demo" + uuid.uuid4().hex[:6]
    with appmod.update_json(appmod.USERS_FILE) as users:
        users[uname] = {"password": "x", "role": "worker", "name": "D", "org": org}
    with client.session_transaction() as s:
        s.update(user=uname, role="admin", roles=["admin"], org=org)   # stale elevated session
    client.set_cookie("csrf_token", "tok")
    # any authenticated request triggers the re-sync; admin-only users list must now 403
    assert client.get("/api/users").status_code == 403
