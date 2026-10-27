"""Cycle-5 — close remaining P0/P1 risks. AUTOMATED SANDBOX ONLY.
S2 temp-password handoff · E5 shared rate limiter · C4-2 rollback-on-exception.
"""
import uuid, threading


def _true_admin(client, appmod):
    with appmod.update_json(appmod.USERS_FILE) as u:
        u["adm"] = {"password": "x", "role": "admin", "name": "A", "org": appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="adm", role="admin", roles=["admin"], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


# ========================= S2 =========================
def test_issue_temp_password_once_and_not_stored(appmod, client):
    org = appmod.DEFAULT_ORG
    uname = "hire" + uuid.uuid4().hex[:6]
    c = appmod.sdb(org)
    cur = c.execute("""INSERT INTO new_hires(full_name,role_target,provisioned_username,provisioned_at,invite_token)
                       VALUES('Jan','worker',?,datetime('now'),?)""", (uname, uuid.uuid4().hex))
    hid = cur.lastrowid; c.commit(); c.close()
    with appmod.update_json(appmod.USERS_FILE) as u:
        u[uname] = {"password": appmod._h("orig"), "role": "worker", "name": "Jan", "org": org, "from_hire_id": hid}

    hdr = _true_admin(client, appmod)
    r = client.post(f"/api/hires/{hid}/issue-temp-password", json={}, headers=hdr).get_json()
    assert r["ok"] is True and r["username"] == uname and len(r["temp_password"]) >= 6
    tp = r["temp_password"]
    # users.json now holds the HASH of the issued password (login works), not plaintext
    users = appmod.ldj(appmod.USERS_FILE)
    assert users[uname]["password"].startswith("$2") and appmod._verify(tp, users[uname]["password"])
    # the plaintext is never persisted in new_hires
    c = appmod.sdb(org)
    pw = c.execute("SELECT provisioned_password FROM new_hires WHERE id=?", (hid,)).fetchone()["provisioned_password"]
    c.close()
    assert pw is None, "plaintext temp password was persisted"


def test_issue_temp_password_requires_true_admin(appmod, client):
    org = appmod.DEFAULT_ORG
    with appmod.update_json(appmod.USERS_FILE) as u:
        u["mgr"] = {"password": "x", "role": "manager", "name": "M", "org": org}
    with client.session_transaction() as s:
        s.update(user="mgr", role="manager", roles=["manager"], org=org)
    client.set_cookie("csrf_token", "tok")
    assert client.post("/api/hires/1/issue-temp-password", json={}, headers={"X-CSRF-Token": "tok"}).status_code == 403


def test_boot_migration_purges_legacy_plaintext(appmod):
    org = appmod.DEFAULT_ORG
    c = appmod.sdb(org)
    c.execute("""INSERT INTO new_hires(full_name,role_target,provisioned_username,provisioned_password,invite_token)
                 VALUES('Leg','worker',?, 'PLAINTEXT123', ?)""", ("legacy" + uuid.uuid4().hex[:5], uuid.uuid4().hex))
    c.commit(); c.close()
    appmod.sdb_init(org)   # re-run migrations
    c = appmod.sdb(org)
    leftover = c.execute("SELECT COUNT(*) FROM new_hires WHERE provisioned_password IS NOT NULL").fetchone()[0]
    c.close()
    assert leftover == 0, "legacy plaintext temp passwords not purged"


# ========================= E5 shared rate limiter =========================
def test_rate_limiter_blocks_at_limit(appmod):
    key = "lead:" + uuid.uuid4().hex[:8]
    allowed = [appmod._rate_ok(key, limit=3, window=100) for _ in range(5)]
    assert allowed == [True, True, True, False, False], allowed


def test_rate_limiter_is_db_backed_shared(appmod):
    # a fresh key recorded through _rate_ok shows up in platform.db -> shared across workers
    key = "apply:" + uuid.uuid4().hex[:8]
    appmod._rate_ok(key, limit=5, window=100)
    c = appmod.pdb()
    n = c.execute("SELECT COUNT(*) FROM rate_hits WHERE rk=?", (key,)).fetchone()[0]
    c.close()
    assert n >= 1, "rate hit not persisted to shared store"


# ========================= C4-2 rollback-on-exception =========================
def test_teardown_closes_leaked_connection(appmod):
    org = appmod.DEFAULT_ORG
    leaked = {}
    with appmod.app.test_request_context():
        c = appmod.sdb(org)                      # tracked on g
        c.execute("CREATE TABLE IF NOT EXISTS _c42(x)")
        c.execute("INSERT INTO _c42(x) VALUES(1)")   # uncommitted write holding the lock
        leaked["c"] = c
        # context exits here WITHOUT commit/close -> teardown must roll back + close
    import sqlite3 as _sq
    raised = False
    try:
        leaked["c"].execute("SELECT 1")
    except _sq.ProgrammingError:
        raised = True
    assert raised, "leaked connection was not closed at request teardown"


# ========================= 15-STATION SIMULATION =========================
def _seed_order(appmod, org, on_hand=5, qty=1):
    tag = uuid.uuid4().hex[:8]
    psku, sticker, label, sid = "P"+tag, "ST"+tag, "SHOW-"+tag, "SH"+tag
    trk = "9400" + uuid.uuid4().hex[:14]
    c = appmod.sdb(org)
    c.execute("INSERT INTO products(sku,name,on_hand,avg_cost,updated_at) VALUES(?,?,?,?,datetime('now'))",
              (psku, "P"+tag, on_hand, 1.0))
    c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku,mapped_at) VALUES(?,?,?,?,datetime('now'))",
              (label, sticker, 0, psku))
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform) VALUES(?,?,?,?,?,'tiktok')",
              (sid, trk, "pending", "b"+tag, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) VALUES(?,?,?,?,?,0)",
              (sid, "O"+tag, sticker, "P"+tag, qty))
    c.commit(); c.close()
    return sid, trk, psku, qty


def test_15_stations_full_flow(appmod):
    org = appmod.DEFAULT_ORG
    N = 15
    orders = [_seed_order(appmod, org, on_hand=5, qty=1) for _ in range(N)]
    errors = []

    def station(order):
        sid, trk, psku, qty = order
        try:
            cl = appmod.app.test_client()
            with cl.session_transaction() as s:
                s.update(user="admin", role="admin", roles=["admin"], org=org)
            cl.set_cookie("csrf_token", "tok")
            h = {"X-CSRF-Token": "tok"}
            # pick (fire twice to simulate a duplicate request -> exactly one winner)
            r1 = cl.post(f"/api/pick/complete/{sid}", json={}, headers=h).get_json()
            r2 = cl.post(f"/api/pick/complete/{sid}", json={}, headers=h).get_json()
            assert (r1.get("ok") is True) ^ (r2.get("ok") is True) or (r1.get("ok") and not r2.get("ok"))
            # scan lookup
            assert cl.get(f"/api/shipment/{trk}").get_json()["ok"] is True
            # pack twice (duplicate upload must not double-deduct)
            cl.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"}, headers=h, content_type="multipart/form-data")
            cl.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"}, headers=h, content_type="multipart/form-data")
        except Exception as e:
            errors.append(repr(e))

    ts = [threading.Thread(target=station, args=(o,)) for o in orders]
    for t in ts: t.start()
    for t in ts: t.join()

    assert not errors, f"station errors: {errors[:3]}"
    c = appmod.sdb(org)
    for sid, trk, psku, qty in orders:
        st = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()["status"]
        oh = c.execute("SELECT on_hand FROM products WHERE sku=?", (psku,)).fetchone()["on_hand"]
        assert st == "packed", f"{sid} ended {st}"
        assert oh == 5 - qty, f"{sid} inventory wrong: on_hand={oh} (expected {5-qty}) — double/zero deduct"
    c.close()
