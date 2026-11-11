"""SEC-6 — deleting a company removes its platform rows and stored objects, can be
retried after a failure, never matches another company, and its id cannot be reused.

Temp DATA_DIR from conftest; storage is an in-memory fake (never a real bucket).
"""
import os
import uuid

import pytest

PW = "Passw0rd!x"
MAIN, HR = "fake-main", "fake-hr"
KEPT = ("org_tombstones", "platform_audit", "payments")   # deletion record + the platform owner's own ledgers


class FakeR2:
    """In-memory S3 stand-in: {bucket: set(keys)}; records every call."""
    def __init__(self, objects):
        self.objects = {b: set(ks) for b, ks in objects.items()}
        self.calls = []            # (name, bucket, prefix-or-keys)
        self.fail_delete = 0       # raise on the next N delete calls

    def list_objects_v2(self, Bucket, Prefix="", MaxKeys=1000, **kw):
        self.calls.append(("list", Bucket, Prefix))
        keys = sorted(k for k in self.objects.get(Bucket, ()) if k.startswith(Prefix))[:MaxKeys]
        return {"Contents": [{"Key": k} for k in keys], "KeyCount": len(keys)}

    def delete_objects(self, Bucket, Delete):
        keys = [o["Key"] for o in Delete["Objects"]]
        self.calls.append(("delete_objects", Bucket, tuple(keys)))
        if self.fail_delete:
            self.fail_delete -= 1
            raise TimeoutError("simulated storage timeout")
        self.objects[Bucket] -= set(keys)
        return {}

    def delete_object(self, Bucket, Key):
        self.calls.append(("delete_object", Bucket, Key))
        if self.fail_delete:
            self.fail_delete -= 1
            raise TimeoutError("simulated storage timeout")
        self.objects[Bucket].discard(Key)
        return {}

    def __getattr__(self, name):   # anything else would be an unexpected storage call
        raise AssertionError("unexpected storage call: " + name)

    def all_keys(self):
        return {(b, k) for b, ks in self.objects.items() for k in ks}


def _mk_org(A, org):
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (org, org.upper() + " Co", org[:10].upper(), "active"))
    c.commit(); c.close()
    A.provision_org(org)
    with A.update_json(A.USERS_FILE) as users:
        users[org + "-admin"] = {"password": A._h(PW), "role": "admin", "name": org + " admin", "org": org}
        users[org + "-worker"] = {"password": A._h(PW), "role": "worker", "name": org + " worker", "org": org}
    return org


def _seed_platform(A, org):
    """One row in every platform table that is keyed to a company. Returns the ticket id."""
    c = A.pdb()
    A._tt_control_ensure(c)
    c.execute("CREATE TABLE IF NOT EXISTS tiktok_products(org_id TEXT, shop_id TEXT, product_id TEXT)")
    shop = "shop-" + org
    c.execute("INSERT INTO tiktok_shops(org_id,shop_id,access_token,refresh_token,active) VALUES(?,?,?,?,1)",
              (org, shop, "fake-access", "fake-refresh"))
    c.execute("INSERT INTO tiktok_orders(order_id,org_id,shop_id,buyer) VALUES(?,?,?,?)", ("o-" + org, org, shop, "Buyer"))
    c.execute("INSERT INTO tiktok_events(shop_id,org_id,order_id,payload) VALUES(?,?,?,?)", (shop, org, "o-" + org, "{}"))
    c.execute("INSERT INTO tiktok_events(shop_id,org_id,order_id,payload) VALUES(?,'',?,?)", (shop, "o2-" + org, "{}"))
    c.execute("INSERT INTO tiktok_live_sessions(org_id,session_id,name) VALUES(?,?,?)", (org, "s-" + org, "Live"))
    c.execute("INSERT INTO tiktok_control(org_id,paused) VALUES(?,1)", (org,))
    c.execute("INSERT INTO tiktok_products(org_id,shop_id,product_id) VALUES(?,?,?)", (org, shop, "p1"))
    c.execute("INSERT INTO billing_requests(org_id,plan,requested_by) VALUES(?,?,?)", (org, "pro", org + "-admin"))
    tid = c.execute("INSERT INTO tickets(org_id,created_by,subject) VALUES(?,?,?)", (org, org + "-admin", "Help")).lastrowid
    c.execute("INSERT INTO ticket_messages(ticket_id,author,body) VALUES(?,?,?)", (tid, org + "-admin", "hello"))
    c.execute("INSERT INTO ticket_attachments(ticket_id,filename,storage_key) VALUES(?,?,?)",
              (tid, "shot.png", "support/%d/ab12_shot.png" % tid))
    c.commit(); c.close()
    return tid


def _platform_rows(A, org, tid=None):
    """{table: rows still tied to the org} over every table of platform.db."""
    c = A.pdb(); out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        cols = {r[1] for r in c.execute('PRAGMA table_info("%s")' % t).fetchall()}
        if "org_id" in cols and t not in KEPT:
            n = c.execute('SELECT COUNT(*) FROM "%s" WHERE org_id=?' % t, (org,)).fetchone()[0]
            if n: out[t] = n
    if tid is not None:
        for t in ("ticket_messages", "ticket_attachments"):
            n = c.execute("SELECT COUNT(*) FROM %s WHERE ticket_id=?" % t, (tid,)).fetchone()[0]
            if n: out[t] = n
    n = c.execute("SELECT COUNT(*) FROM tiktok_events WHERE shop_id=?", ("shop-" + org,)).fetchone()[0]
    if n: out["tiktok_events(by shop)"] = n
    c.close()
    return out


def _org_keys(org, tid):
    return {
        (MAIN, org + "/videos/S1_TRK_1.webm"), (MAIN, org + "/photos/S1_TRK_1.jpg"),
        (MAIN, org + "/labels/l.pdf"), (MAIN, org + "/documents/d.pdf"),
        (MAIN, org + "/products/sku.png"), (MAIN, org + "/invoices/po1.pdf"),
        (MAIN, org + "/hire_uploads/1/2/id_front_a.jpg"), (HR, org + "/hire_uploads/1/2/id_front_a.jpg"),
        (MAIN, "support/%d/ab12_shot.png" % tid),
    }


def _backup_keys(org):
    """Backup copies of a company are kept on deletion (they expire by backup retention)."""
    return {(MAIN, "backups/mon/" + org + "/shipments.db"), (MAIN, "backups/sun/" + org + "/giveaways.db")}


@pytest.fixture
def world(appmod, monkeypatch):
    """Org `ab<x>` (to delete) next to `ab<x>c` and `ab<x>-2` (similar names, must
    survive), each with platform rows and objects; storage is a FakeR2."""
    A = appmod
    org = "ab" + uuid.uuid4().hex[:6]
    near = [org + "c", org + "-2"]
    tids = {o: _seed_platform(A, _mk_org(A, o)) for o in [org] + near}
    others = _backup_keys(org)
    for o in near:
        others |= _org_keys(o, tids[o]) | _backup_keys(o)
    os.makedirs(os.path.join(A.DATA_DIR, "backups", "mon", org), exist_ok=True)
    with open(os.path.join(A.DATA_DIR, "backups", "mon", org, "shipments.db"), "wb") as fh:
        fh.write(b"local backup copy")
    others |= {(MAIN, "videos/S1_LEGACY.webm"), (MAIN, "photos/S1_LEGACY.jpg"), (MAIN, "hire_uploads/9/9/x.jpg"),
               (MAIN, A.DEFAULT_ORG + "/videos/S1_OWN.webm"), (MAIN, "backups/mon/platform.db"),
               (MAIN, "backups/mon/" + A.DEFAULT_ORG + "/shipments.db"), (HR, A.DEFAULT_ORG + "/hire_uploads/1/1/a.jpg"),
               (MAIN, "x" + org + "/videos/other.webm")}
    objs = {MAIN: set(), HR: set()}
    for b, k in _org_keys(org, tids[org]) | others:
        objs[b].add(k)
    fake = FakeR2(objs)
    monkeypatch.setattr(A, "r2", fake)
    monkeypatch.setattr(A, "R2_BUCKET", MAIN)
    monkeypatch.setattr(A, "R2_HR_BUCKET", HR)
    return {"A": A, "org": org, "near": near, "tids": tids, "fake": fake, "others": others}


def _create(A, *a, **k):
    # SEC-14 (open, separate fix): the /api/orgs/create route decorators sit on this
    # helper, so outside a request it has to be reached through __wrapped__.
    return getattr(A._create_tenant, "__wrapped__", A._create_tenant)(*a, **k)


def _tomb(A, org):
    c = A.pdb(); r = c.execute("SELECT * FROM org_tombstones WHERE org_id=?", (org,)).fetchone(); c.close()
    return dict(r) if r else None


def test_delete_removes_every_platform_row(world):
    A, org, tid = world["A"], world["org"], world["tids"][world["org"]]
    assert set(_platform_rows(A, org, tid)) >= {"organizations", "tiktok_shops", "tiktok_orders", "tiktok_events",
                                                "tiktok_live_sessions", "tiktok_control", "tiktok_products",
                                                "billing_requests", "tickets", "ticket_messages", "ticket_attachments"}
    res = A._delete_org_data(org)
    assert res["ok"] and res["complete"] and res["state"] == "deleted", res
    assert _platform_rows(A, org, tid) == {}
    users = A.ldj(A.USERS_FILE)
    assert not [u for u, v in users.items() if v.get("org") == org]
    assert not os.path.isdir(A.org_path(org))
    assert _tomb(A, org)["state"] == "deleted"
    c = A.pdb()                                           # the deletion itself stays on the audit trail
    assert c.execute("SELECT COUNT(*) FROM platform_audit WHERE org_id=? AND action='org_delete'", (org,)).fetchone()[0] == 1
    c.close()


def test_storage_delete_hits_exactly_the_orgs_prefixes(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    A._delete_org_data(org)
    assert fake.all_keys() == world["others"]            # everything else is still there, nothing of the org is
    listed = {(b, p) for n, b, p in fake.calls if n == "list"}
    assert listed == {(MAIN, org + "/"), (HR, org + "/")}
    tid = world["tids"][org]
    for n, b, what in fake.calls:
        if n == "delete_objects":
            assert all(k.startswith(org + "/") for k in what), what
        if n == "delete_object":
            assert what == "support/%d/ab12_shot.png" % tid


def test_similarly_named_orgs_are_untouched(world):
    A, org = world["A"], world["org"]
    before = {o: _platform_rows(A, o, world["tids"][o]) for o in world["near"]}
    A._delete_org_data(org)
    users = A.ldj(A.USERS_FILE)
    for o in world["near"]:
        assert _platform_rows(A, o, world["tids"][o]) == before[o] and before[o]
        assert os.path.isdir(A.org_path(o)) and (o + "-admin") in users
        assert _org_keys(o, world["tids"][o]) <= world["fake"].all_keys()
        assert _tomb(A, o) is None


def test_retry_after_midway_failure_finishes_the_job(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    tid = world["tids"][org]
    fake.fail_delete = 2                                  # ticket file + first prefix time out
    res = A._delete_org_data(org)
    assert res["ok"] and not res["complete"] and res["state"] == "pending" and res["errors"]
    # the company is already gone for its users, tokens included; nothing is half-visible
    assert not A.org_is_active(org) and org not in A.list_org_ids()
    assert not [u for u, v in A.ldj(A.USERS_FILE).items() if v.get("org") == org]
    left = _platform_rows(A, org, tid)
    assert "tiktok_shops" not in left and "organizations" not in left
    assert set(left) == {"tickets", "ticket_messages", "ticket_attachments"}   # kept only to find the file again
    assert _org_keys(org, tid) & fake.all_keys()
    assert _tomb(A, org)["state"] == "pending"
    assert A._org_delete_resume_pending() >= 1            # what the hourly loop runs
    assert _platform_rows(A, org, tid) == {}
    assert fake.all_keys() == world["others"]
    assert _tomb(A, org)["state"] == "deleted" and _tomb(A, org)["attempts"] == 2
    again = A._delete_org_data(org)                       # a third run changes nothing
    assert again["complete"] and fake.all_keys() == world["others"]


def test_time_budget_leaves_a_pending_tombstone(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    res = A._delete_org_data(org, budget_sec=-1)          # storage budget already used up
    assert res["ok"] and res["state"] == "pending" and not any(n == "delete_objects" for n, _, _ in fake.calls)
    assert A._delete_org_data(org)["complete"] and fake.all_keys() == world["others"]


def test_deleted_org_id_cannot_be_created_again(world):
    A, org = world["A"], world["org"]
    A._delete_org_data(org)
    ok, err = _create(A, org, "Second Co", "adm" + uuid.uuid4().hex[:6], actor="test")
    assert ok is False and "deleted company" in err
    c = A.pdb(); n = c.execute("SELECT COUNT(*) FROM organizations WHERE org_id=?", (org,)).fetchone()[0]; c.close()
    assert n == 0 and not os.path.isdir(A.org_path(org))
    fresh = "new" + uuid.uuid4().hex[:6]                  # a never-used id still works
    ok, res = _create(A, fresh, "Fresh Co", "adm" + uuid.uuid4().hex[:6], actor="test")
    assert ok is True and res["org_id"] == fresh


def test_route_reports_cleanup_result(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    with A.update_json(A.USERS_FILE) as users:
        del users[org + "-worker"]
    cl = A.app.test_client()
    with cl.session_transaction() as s:
        s.update(user=org + "-admin", role="admin", roles=["admin"], name="a", org=org)
    cl.set_cookie("csrf_token", "tok")
    fake.fail_delete = 99
    j = cl.post("/api/account/delete", headers={"X-CSRF-Token": "tok"}, json={"wipe_org": True}).get_json()
    assert j["ok"] and j["org_deleted"] is True
    assert j["org_cleanup"]["complete"] is False and j["org_cleanup"]["state"] == "pending"
    fake.fail_delete = 0
    A._org_delete_resume_pending()
    assert fake.all_keys() == world["others"]


def test_unsafe_or_shared_ids_never_reach_storage(world):
    A, fake = world["A"], world["fake"]
    before = fake.all_keys()
    for bad in ("", A.PLATFORM_ORG, "a/b", "../x", "ab/", "a b"):
        assert A._delete_org_data(bad)["ok"] is False
    res = A._delete_org_data("videos")                    # id equal to a shared top-level key name
    assert res["state"] == "partial" and any("videos/" in s for s in res["skipped"])
    assert fake.all_keys() == before
    assert not any(n == "list" and p == "videos/" for n, _, p in fake.calls)


def test_backup_copies_are_kept(world):
    """While deletion needs no re-authentication (SEC-7), backups are the way back from a
    wrongful wipe: neither the bucket copies nor the local ones are removed."""
    A, org, fake = world["A"], world["org"], world["fake"]
    assert A._delete_org_data(org)["state"] == "deleted"
    assert _backup_keys(org) <= fake.all_keys()
    assert os.path.exists(os.path.join(A.DATA_DIR, "backups", "mon", org, "shipments.db"))
    assert not any(p.startswith("backups/") for n, b, p in fake.calls if n == "list")


def _session(A, user, org, role="admin"):
    cl = A.app.test_client()
    with cl.session_transaction() as s:
        s.update(user=user, role=role, roles=[role], name="x", org=org)
    cl.set_cookie("csrf_token", "tok")
    cl.csrf = {"X-CSRF-Token": "tok"}
    return cl


def test_sec6a_stale_session_cannot_delete_a_namesake_company(world):
    A, org = world["A"], world["org"]
    with A.update_json(A.USERS_FILE) as u:
        del u[org + "-worker"]
    c = _session(A, org + "-admin", org)
    assert c.post("/api/account/delete", headers=c.csrf, json={"wipe_org": True}).get_json()["org_deleted"] is True
    ok, res = _create(A, "fresh" + org[-6:], "Fresh Co", org + "-admin")     # same admin username, new company
    assert ok, res
    new = res["org_id"]
    for path, method in (("/api/account/delete", "post"), ("/api/shows", "get"), ("/api/tiktok/connect", "post"), ("/me", "get")):
        stale = _session(A, org + "-admin", org)                             # the old company's cookie
        r = getattr(stale, method)(path, headers=stale.csrf, **({"json": {"wipe_org": True}} if method == "post" else {}))
        # routes behind the billing gate answer 402 first (the old company has no
        # directory row); routes the gate leaves open reach the session check: 401
        assert r.status_code in (301, 302, 401, 402, 403), (path, r.status_code)
        if path == "/api/account/delete":
            assert r.status_code == 401 and r.get_json()["error"] == "session_revoked"
    p = A.pdb(); alive = p.execute("SELECT 1 FROM organizations WHERE org_id=?", (new,)).fetchone(); p.close()
    assert alive and (org + "-admin") in A.ldj(A.USERS_FILE) and not A.org_id_tombstoned(new)
    assert os.path.isdir(A.org_path(new))


def test_session_whose_org_differs_from_the_user_record_is_dead(world):
    """Not only after a deletion: a cookie naming another company than the user's own."""
    A, org, other = world["A"], world["org"], world["near"][0]
    for path in ("/api/shows", "/api/account/delete"):
        cl = _session(A, org + "-admin", other)
        r = cl.post(path, headers=cl.csrf, json={"wipe_org": True}) if path.endswith("delete") else cl.get(path)
        assert r.status_code == 401, (path, r.status_code)
    p = A.pdb(); n = p.execute("SELECT COUNT(*) FROM organizations WHERE org_id IN (?,?)", (org, other)).fetchone()[0]; p.close()
    assert n == 2 and _tomb(A, org) is None and _tomb(A, other) is None
    ok = _session(A, org + "-admin", org).get("/api/shows")                  # the matching cookie still works
    assert ok.status_code == 200


def test_session_of_a_tombstoned_org_is_dead_even_while_its_login_still_exists(world, monkeypatch):
    """Deletion killed between the tombstone and the logins step: the record is still
    there, the cookie matches it, and it is dead anyway."""
    A, org = world["A"], world["org"]
    class Killed(BaseException): pass
    def boom(*a, **k): raise Killed()
    with monkeypatch.context() as m:
        m.setattr(A, "update_json", boom)
        with pytest.raises(Killed):
            A._delete_org_data(org)
    assert (org + "-admin") in A.ldj(A.USERS_FILE) and A.org_id_tombstoned(org)
    cl = _session(A, org + "-admin", org)
    assert cl.get("/api/shows").status_code in (401, 402)
    assert cl.get("/api/me").status_code == 401            # open through the billing gate
    cl = _session(A, org + "-admin", org)
    assert cl.post("/api/account/delete", headers=cl.csrf, json={"wipe_org": True}).status_code == 401
    assert A._org_delete_resume_pending() == 1 and _tomb(A, org)["state"] == "deleted"


def test_sec6b_founding_org_cannot_be_wiped(appmod, admin):
    A = appmod
    # other tests add admins to the founding org; set them aside so "admin" is the last one
    with A.update_json(A.USERS_FILE) as users:
        aside = {k: users.pop(k) for k, v in list(users.items())
                 if k != "admin" and v.get("role") == "admin" and (v.get("org") or A.DEFAULT_ORG) == A.DEFAULT_ORG}
    try:
        r = admin.post("/api/account/delete", headers=admin.csrf, json={})
        assert r.status_code == 409 and r.get_json()["need_org_confirm"]      # this is the wipe path
        r = admin.post("/api/account/delete", headers=admin.csrf, json={"wipe_org": True})
        assert r.status_code == 403 and r.get_json()["error"] == "org_protected"
        assert "admin" in A.ldj(A.USERS_FILE) and os.path.exists(A.shipments_db_path(A.DEFAULT_ORG))
        assert not A.org_id_tombstoned(A.DEFAULT_ORG)
        res = A._delete_org_data(A.DEFAULT_ORG)          # and the function itself refuses
        assert res["ok"] is False and not A.org_id_tombstoned(A.DEFAULT_ORG)
        p = A.pdb(); row = p.execute("SELECT 1 FROM organizations WHERE org_id=?", (A.DEFAULT_ORG,)).fetchone(); p.close()
        assert row and "admin" in A.ldj(A.USERS_FILE)
    finally:
        with A.update_json(A.USERS_FILE) as users:
            users.update(aside)


def test_internal_org_cannot_be_wiped(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    p = A.pdb(); p.execute("UPDATE organizations SET internal=1 WHERE org_id=?", (org,)); p.commit(); p.close()
    with A.update_json(A.USERS_FILE) as u:
        del u[org + "-worker"]
    cl = _session(A, org + "-admin", org)
    r = cl.post("/api/account/delete", headers=cl.csrf, json={"wipe_org": True})
    assert r.status_code == 403 and r.get_json()["error"] == "org_protected"
    assert A._delete_org_data(org)["ok"] is False
    assert (org + "-admin") in A.ldj(A.USERS_FILE) and _tomb(A, org) is None and fake.calls == []
    assert os.path.isdir(A.org_path(org))


def test_founding_org_tombstone_is_removed_at_boot_and_never_resumed(world):
    A, fake = world["A"], world["fake"]
    p = A.pdb(); p.execute("INSERT OR REPLACE INTO org_tombstones(org_id,state) VALUES(?, 'pending')", (A.DEFAULT_ORG,))
    p.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending' AND org_id<>?", (A.DEFAULT_ORG,))
    p.commit(); p.close()
    try:
        A._org_delete_resume_pending()
        assert fake.calls == [] and "admin" in A.ldj(A.USERS_FILE)
        A.pdb_init()                                     # what every boot runs
        assert not A.org_id_tombstoned(A.DEFAULT_ORG)
    finally:
        p = A.pdb(); p.execute("DELETE FROM org_tombstones WHERE org_id=?", (A.DEFAULT_ORG,)); p.commit(); p.close()


def test_sec6c_callback_cannot_attach_a_shop_to_a_deleted_org(world, monkeypatch):
    A, org = world["A"], world["org"]
    outbound = []
    monkeypatch.setattr(A, "_tt_token_exchange", lambda code: (outbound.append("exchange") or
                        {"data": {"access_token": "late-access", "refresh_token": "late-refresh", "open_id": "late"}}))
    monkeypatch.setattr(A, "_tt_get_shops", lambda tok: (outbound.append("shops") or {"data": {"shops": [{"id": "late-shop"}]}}))
    monkeypatch.setattr(A, "_tt_state_org", lambda state: org)               # a link minted before the deletion
    A._delete_org_data(org)
    r = A.app.test_client().get("/api/tiktok/callback?code=abc&state=whatever")
    assert r.status_code == 400 and outbound == []
    assert A._tt_store_shop(org, {"access_token": "x"}, {"id": "late-shop"}) is False            # deleted
    assert A._tt_store_shop("never" + uuid.uuid4().hex[:6], {"access_token": "x"}, {"id": "s"}) is False   # unknown
    p = A.pdb(); n = p.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=?", (org,)).fetchone()[0]; p.close()
    assert n == 0
    live = world["near"][0]                                                  # a live company still connects
    monkeypatch.setattr(A, "_tt_state_org", lambda state: live)
    assert A.app.test_client().get("/api/tiktok/callback?code=abc&state=whatever").status_code == 200
    p = A.pdb(); n = p.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=? AND shop_id='late-shop'", (live,)).fetchone()[0]; p.close()
    assert n == 1


def test_loop_purges_rows_written_after_the_deletion_finished(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    tid = world["tids"][org]
    assert A._delete_org_data(org)["state"] == "deleted"
    near_before = {o: _platform_rows(A, o, world["tids"][o]) for o in world["near"]}
    p = A.pdb()                                           # an in-flight sync finishing late
    p.execute("INSERT INTO tiktok_shops(org_id,shop_id,access_token,refresh_token,active) VALUES(?,?,?,?,1)",
              (org, "shop-" + org, "late-access", "late-refresh"))
    p.execute("INSERT INTO tiktok_orders(order_id,org_id,shop_id,buyer) VALUES(?,?,?,?)", ("late-" + org, org, "shop-" + org, "Buyer"))
    p.commit(); p.close()
    calls = len(fake.calls)
    assert A._org_delete_resume_pending() == 0            # nothing pending, yet the rows go
    assert _platform_rows(A, org, tid) == {}
    assert len(fake.calls) == calls and _tomb(A, org)["attempts"] == 1
    assert {o: _platform_rows(A, o, world["tids"][o]) for o in world["near"]} == near_before


def test_sec6e_reserved_ids_cannot_be_created(world):
    A = world["A"]
    for name in ("videos", "photos", "documents", "labels", "products", "invoices", "backups", "support", "orgs", "platform", "mon"):
        ok, err = _create(A, name, name + " Co", "adm" + uuid.uuid4().hex[:6], actor="test")
        assert ok is False and "reserved" in err, name
        p = A.pdb(); n = p.execute("SELECT COUNT(*) FROM organizations WHERE org_id=?", (name,)).fetchone()[0]; p.close()
        assert n == 0, name
    # intake with such a company name lands on a different id
    p = A.pdb()
    iid = p.execute("INSERT INTO client_intakes(company_name,contact_name,contact_email) VALUES('Backups','B','b@example.com')").lastrowid
    p.commit(); p.close()
    su = "su" + uuid.uuid4().hex[:6]
    cl = _session(A, su, A.PLATFORM_ORG, role="superadmin")
    j = cl.post("/api/intakes/%d/provision" % iid, headers=cl.csrf, json={}).get_json()
    assert j.get("ok"), j
    p = A.pdb()
    got = p.execute("SELECT converted_org FROM client_intakes WHERE id=?", (iid,)).fetchone()[0]
    p.close()
    assert got and got != "backups" and got.startswith("backups")


def test_undecided_platform_table_is_not_purged_and_deletion_ends_partial(world):
    A, org = world["A"], world["org"]
    p = A.pdb()
    p.execute("CREATE TABLE IF NOT EXISTS zz_future_feature(org_id TEXT, v TEXT)")
    p.execute("INSERT INTO zz_future_feature VALUES(?, 'x')", (org,)); p.commit(); p.close()
    try:
        res = A._delete_org_data(org)
        assert res["state"] == "partial" and any("zz_future_feature" in x for x in res["skipped"])
        p = A.pdb(); n = p.execute("SELECT COUNT(*) FROM zz_future_feature WHERE org_id=?", (org,)).fetchone()[0]; p.close()
        assert n == 1
    finally:
        p = A.pdb(); p.execute("DROP TABLE zz_future_feature"); p.commit(); p.close()
    assert set(A._ORG_DELETE_PURGE_TABLES).isdisjoint(A._ORG_DELETE_KEEP_TABLES)


def test_retries_stop_at_the_cap_and_store_no_exception_text(world, monkeypatch):
    A, org, fake = world["A"], world["org"], world["fake"]
    monkeypatch.setattr(A, "ORG_DELETE_MAX_ATTEMPTS", 3)
    secret = "AKIAFAKEKEY-do-not-store"
    def broken(**k): raise RuntimeError("bucket said no: " + secret)
    monkeypatch.setattr(fake, "delete_objects", broken)
    monkeypatch.setattr(fake, "delete_object", lambda **k: broken())
    res = A._delete_org_data(org)
    assert res["state"] == "pending" and secret not in repr(res)
    assert A._org_delete_resume_pending() == 1 and _tomb(A, org)["state"] == "pending"
    assert A._org_delete_resume_pending() == 1 and _tomb(A, org)["state"] == "stuck"      # third attempt = the cap
    for _ in range(3):
        assert A._org_delete_resume_pending() == 0                                        # no more automatic retries
    t = _tomb(A, org)
    assert t["attempts"] == 3 and secret not in (t["detail"] or "") and "RuntimeError" in t["detail"]
    p = A.pdb()
    audit = [r[0] for r in p.execute("SELECT detail FROM platform_audit WHERE org_id=? AND action='org_delete' ORDER BY id", (org,)).fetchall()]
    p.close()
    assert len(audit) == 2 and "state=pending" in audit[0] and "state=stuck" in audit[1]  # first attempt + the final state
    assert A.org_id_tombstoned(org)                                                       # still not reusable
    su = _session(A, "su" + uuid.uuid4().hex[:6], A.PLATFORM_ORG, role="superadmin")      # visible to the platform owner
    listed = su.get("/api/orgs").get_json()["unfinished_deletions"]
    assert [d for d in listed if d["org_id"] == org and d["state"] == "stuck" and d["attempts"] == 3]
    monkeypatch.undo()                                                                    # bucket fixed: a person re-runs it
    monkeypatch.setattr(A, "r2", fake); monkeypatch.setattr(A, "R2_BUCKET", MAIN); monkeypatch.setattr(A, "R2_HR_BUCKET", HR)
    assert A._delete_org_data(org)["state"] == "deleted"
