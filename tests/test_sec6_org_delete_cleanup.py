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
        (MAIN, "backups/mon/" + org + "/shipments.db"), (MAIN, "backups/sun/" + org + "/giveaways.db"),
        (MAIN, "support/%d/ab12_shot.png" % tid),
    }


@pytest.fixture
def world(appmod, monkeypatch):
    """Org `ab<x>` (to delete) next to `ab<x>c` and `ab<x>-2` (similar names, must
    survive), each with platform rows and objects; storage is a FakeR2."""
    A = appmod
    org = "ab" + uuid.uuid4().hex[:6]
    near = [org + "c", org + "-2"]
    tids = {o: _seed_platform(A, _mk_org(A, o)) for o in [org] + near}
    others = set()
    for o in near:
        others |= _org_keys(o, tids[o])
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
    assert listed == {(MAIN, org + "/"), (HR, org + "/")} | {(MAIN, "backups/%s/%s/" % (d, org)) for d in A._BACKUP_DOWS}
    tid = world["tids"][org]
    for n, b, what in fake.calls:
        if n == "delete_objects":
            assert all(k.startswith(org + "/") or (k.startswith("backups/") and k.split("/")[2] == org) for k in what), what
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
