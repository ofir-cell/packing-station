"""QA gate for SEC-6 (company deletion cleanup) — written by qa, not by the programmer.

The change deletes data. These tests try to make it delete something that belongs to a
company that was NOT deleted, and check what the hourly resume loop may start on.

* Temp DATA_DIR from conftest; storage is an in-memory fake (never a real bucket).
* Tests that would destroy the founding org run in a child process with its own
  throwaway DATA_DIR, so the shared session database is never damaged.
* ``xfail(strict=True)`` = demonstration of a defect found by this review (repo
  convention, see test_security_mobile_baseline.py). Each asserts the SAFE behaviour.
"""
import hashlib
import json
import os
import subprocess
import sys
import textwrap
import threading
import uuid

import pytest

PW = "Passw0rd!x"
MAIN, HR = "fake-main", "fake-hr"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Killed(BaseException):
    """Stands for the worker dying mid-deletion: not caught by `except Exception`."""


class FakeR2:
    def __init__(self):
        self.objects = {MAIN: set(), HR: set()}
        self.calls = []
        self.kill_on = None         # ("list"|"delete_objects"|"delete_object", nth call)
        self._n = {}
        self.ignore_prefix = False  # a broken listing that returns keys outside the prefix

    def _maybe_kill(self, name):
        self._n[name] = self._n.get(name, 0) + 1
        if self.kill_on and self.kill_on[0] == name and self._n[name] == self.kill_on[1]:
            self.kill_on = None
            raise Killed(name)

    def list_objects_v2(self, Bucket, Prefix="", MaxKeys=1000, **kw):
        self.calls.append(("list", Bucket, Prefix))
        self._maybe_kill("list")
        keys = sorted(k for k in self.objects.get(Bucket, ()) if self.ignore_prefix or k.startswith(Prefix))[:MaxKeys]
        return {"Contents": [{"Key": k} for k in keys], "KeyCount": len(keys)}

    def delete_objects(self, Bucket, Delete):
        keys = [o["Key"] for o in Delete["Objects"]]
        self.calls.append(("delete_objects", Bucket, tuple(keys)))
        self._maybe_kill("delete_objects")
        self.objects[Bucket] -= set(keys)
        return {}

    def delete_object(self, Bucket, Key):
        self.calls.append(("delete_object", Bucket, Key))
        self._maybe_kill("delete_object")
        self.objects[Bucket].discard(Key)
        return {}

    def __getattr__(self, name):
        raise AssertionError("unexpected storage call: " + name)

    def all_keys(self):
        return {(b, k) for b, ks in self.objects.items() for k in ks}

    def mutating_calls(self):
        return [c for c in self.calls if c[0].startswith("delete")]


# ───────────────────────── seeding ─────────────────────────

_HASH = {}


def _pw(A):
    if "h" not in _HASH: _HASH["h"] = A._h(PW)      # bcrypt once, not per user
    return _HASH["h"]


def _mk_org(A, org, fake=None):
    """A complete company: directory row, provisioned DBs with an order and stock, two
    logins, platform rows, a ticket with a file, local hire upload, local backup copy,
    and (when `fake` is given) objects in both buckets and the backup prefix."""
    c = A.pdb()
    c.execute("INSERT OR IGNORE INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (org, org + " Co", org[:10].upper(), "active"))
    A._tt_control_ensure(c)
    shop = "shop-" + org
    c.execute("INSERT INTO tiktok_shops(org_id,shop_id,access_token,refresh_token,active) VALUES(?,?,?,?,1)",
              (org, shop, "fake-access", "fake-refresh"))
    c.execute("INSERT INTO tiktok_orders(order_id,org_id,shop_id,buyer) VALUES(?,?,?,?)", ("o-" + org, org, shop, "Buyer"))
    c.execute("INSERT INTO tiktok_events(shop_id,org_id,order_id,payload) VALUES(?,?,?,?)", (shop, org, "o-" + org, "{}"))
    c.execute("INSERT INTO tiktok_events(shop_id,org_id,order_id,payload) VALUES(?,'',?,?)", (shop, "u-" + org, "{}"))
    c.execute("INSERT INTO tiktok_live_sessions(org_id,session_id,name) VALUES(?,?,?)", (org, "s-" + org, "Live"))
    c.execute("INSERT OR REPLACE INTO tiktok_control(org_id,paused) VALUES(?,1)", (org,))
    c.execute("INSERT INTO billing_requests(org_id,plan,requested_by) VALUES(?,?,?)", (org, "pro", org + "-admin"))
    c.execute("INSERT INTO payments(org_id,amount,plan) VALUES(?,?,?)", (org, 149, "starter"))
    tid = c.execute("INSERT INTO tickets(org_id,created_by,subject) VALUES(?,?,?)", (org, org + "-admin", "Help")).lastrowid
    c.execute("INSERT INTO ticket_messages(ticket_id,author,body) VALUES(?,?,?)", (tid, org + "-admin", "hello"))
    c.execute("INSERT INTO ticket_attachments(ticket_id,filename,storage_key) VALUES(?,?,?)",
              (tid, "shot.png", "support/%d/ab12_shot.png" % tid))
    c.commit(); c.close()
    A.provision_org(org)
    s = A.sdb(org)
    sid = "S-" + uuid.uuid4().hex[:10]
    s.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform,buyer_name) "
              "VALUES(?,?,'packed','csv','Show 1','tiktok','Buyer')", (sid, "TRK" + uuid.uuid4().hex[:10].upper()))
    s.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) VALUES(?,?,'S1','Lip',1,1)",
              (sid, "O" + sid))
    s.execute("INSERT INTO stock_moves(sku,qty,reason) VALUES('S1',-1,'packed')") if _has_cols(s, "stock_moves", ("sku", "qty", "reason")) else None
    s.commit(); s.close()
    with A.update_json(A.USERS_FILE) as users:
        users[org + "-admin"] = {"password": _pw(A), "role": "admin", "name": org + " admin", "org": org}
        users[org + "-worker"] = {"password": _pw(A), "role": "worker", "name": org + " worker", "org": org}
    with open(os.path.join(A.HIRE_LOCAL_UPLOAD_DIR, org + "__hire_uploads__1__2__id_front.jpg"), "wb") as fh:
        fh.write(b"id photo of " + org.encode())
    b = os.path.join(A.DATA_DIR, "backups", "mon", org); os.makedirs(b, exist_ok=True)
    with open(os.path.join(b, "shipments.db"), "wb") as fh:
        fh.write(b"backup of " + org.encode())
    if fake is not None:
        for b_, k in _org_keys(org, tid) | _backup_keys(org):
            fake.objects[b_].add(k)
    return tid


def _has_cols(conn, table, cols):
    have = {r[1] for r in conn.execute('PRAGMA table_info("%s")' % table).fetchall()}
    return set(cols) <= have


def _org_keys(org, tid):
    return {
        (MAIN, org + "/videos/S1_TRK_1.webm"), (MAIN, org + "/photos/S1_TRK_1.jpg"),
        (MAIN, org + "/labels/l.pdf"), (MAIN, org + "/documents/d.pdf"),
        (MAIN, org + "/products/sku.png"), (MAIN, org + "/invoices/po1.pdf"),
        (MAIN, org + "/hire_uploads/1/2/id_front_a.jpg"), (HR, org + "/hire_uploads/1/2/id_front_a.jpg"),
        (MAIN, "support/%d/ab12_shot.png" % tid),
    }


def _backup_keys(org):
    """Backup copies are NOT deleted with the company (they expire by backup retention),
    so they count as "everything else" in every snapshot below."""
    return {(MAIN, "backups/mon/" + org + "/shipments.db"), (MAIN, "backups/sun/" + org + "/giveaways.db")}


SHARED_KEYS = {(MAIN, "videos/S1_LEGACY.webm"), (MAIN, "photos/S1_LEGACY.jpg"), (MAIN, "documents/legacy.pdf"),
               (MAIN, "labels/legacy.pdf"), (MAIN, "hire_uploads/9/9/x.jpg"), (HR, "hire_uploads/9/9/x.jpg"),
               (MAIN, "backups/mon/platform.db"), (MAIN, "backups/mon/users.json"), (MAIN, "support/999999/zz_other.png")}


# ───────────────────────── snapshots of "everything else" ─────────────────────────

def _platform_snapshot(A, exclude_org, exclude_tid):
    """Every platform.db row that is NOT keyed to `exclude_org`."""
    c = A.pdb(); out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        cols = [r[1] for r in c.execute('PRAGMA table_info("%s")' % t).fetchall()]
        if t in ("org_tombstones", "rate_hits"):
            continue
        if "org_id" in cols:
            rows = c.execute('SELECT * FROM "%s" WHERE org_id<>?' % t, (exclude_org,)).fetchall()
            if t == "tiktok_events":   # unmapped events (org_id '') of the deleted org's own shop go with it
                rows = [r for r in rows if not (r["org_id"] == "" and r["shop_id"] == "shop-" + exclude_org)]
        elif "ticket_id" in cols:
            rows = c.execute('SELECT * FROM "%s" WHERE ticket_id<>?' % t, (exclude_tid,)).fetchall()
        else:
            rows = c.execute('SELECT * FROM "%s"' % t).fetchall()
        out[t] = sorted(json.dumps([str(v) for v in tuple(r)]) for r in rows)
    c.close()
    return out


def _files_snapshot(A, exclude_org, exclude_tid):
    """sha1 of every file on the volume that is NOT `exclude_org`'s (control-plane files
    that every deletion legitimately rewrites are left out)."""
    root = A.DATA_DIR; out = {}
    skip_dirs = {os.path.join("orgs", exclude_org), os.path.join("support", str(exclude_tid))}
    for dp, dns, fns in os.walk(root):
        rel = os.path.relpath(dp, root)
        if rel in skip_dirs:
            dns[:] = []; continue
        for fn in fns:
            r = os.path.normpath(os.path.join(rel, fn))
            if os.sep not in r and (fn.startswith(".") or fn.startswith(("platform.db", "users.json"))):
                continue
            if rel == "hire_uploads" and fn.startswith(exclude_org + "__hire_uploads__"):
                continue
            with open(os.path.join(dp, fn), "rb") as fh:
                out[r] = hashlib.sha1(fh.read()).hexdigest()
    return out


def _users_snapshot(A, exclude_org):
    return {u: v for u, v in A.ldj(A.USERS_FILE).items() if (v.get("org") or A.DEFAULT_ORG) != exclude_org}


def _snapshot(A, fake, org, tid):
    own = _org_keys(org, tid)
    return {"platform": _platform_snapshot(A, org, tid), "files": _files_snapshot(A, org, tid),
            "users": _users_snapshot(A, org), "keys": fake.all_keys() - own}


def _tomb(A, org):
    c = A.pdb(); r = c.execute("SELECT * FROM org_tombstones WHERE org_id=?", (org,)).fetchone(); c.close()
    return dict(r) if r else None


def _org_row(A, org):
    c = A.pdb(); r = c.execute("SELECT 1 FROM organizations WHERE org_id=?", (org,)).fetchone(); c.close()
    return bool(r)


def _own_platform_rows(A, org, tid):
    c = A.pdb(); out = {}
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        cols = {r[1] for r in c.execute('PRAGMA table_info("%s")' % t).fetchall()}
        if "org_id" in cols and t not in ("org_tombstones", "platform_audit", "payments"):
            n = c.execute('SELECT COUNT(*) FROM "%s" WHERE org_id=?' % t, (org,)).fetchone()[0]
            if n: out[t] = n
    for t in ("ticket_messages", "ticket_attachments"):
        n = c.execute("SELECT COUNT(*) FROM %s WHERE ticket_id=?" % t, (tid,)).fetchone()[0]
        if n: out[t] = n
    c.close()
    return out


def _assert_gone(A, fake, org, tid):
    assert _own_platform_rows(A, org, tid) == {}
    assert not _org_row(A, org) and not os.path.isdir(A.org_path(org))
    assert not [u for u, v in A.ldj(A.USERS_FILE).items() if v.get("org") == org]
    assert not (_org_keys(org, tid) & fake.all_keys())


@pytest.fixture
def fake(appmod, monkeypatch):
    f = FakeR2()
    for b, k in SHARED_KEYS:
        f.objects[b].add(k)
    monkeypatch.setattr(appmod, "r2", f)
    monkeypatch.setattr(appmod, "R2_BUCKET", MAIN)
    monkeypatch.setattr(appmod, "R2_HR_BUCKET", HR)
    # Warm-up: the first sign-in attempt of a process lazily writes a settings marker
    # into the founding org's database (existing behaviour, unrelated to deletion); do
    # it before any snapshot is taken.
    _login(appmod, "qa-no-such-user")
    return f


def _family(A, fake, n=3):
    """`ab`-style neighbours: an id, the id plus a letter, plus '-2', plus '_', the same
    id in upper case, and ids that have it as a suffix / as a prefix with a digit."""
    base = "qa" + uuid.uuid4().hex[:6]
    ids = [base, base + "c", base + "-2", base + "_", base.upper(), "x" + base, base + "2"]
    assert len(set(ids)) == len(ids)
    return base, {o: _mk_org(A, o, fake) for o in ids[:n]}


# ═════════════ 1. exact matching ═════════════

@pytest.mark.parametrize("which", range(7))
def test_deleting_one_org_never_touches_a_similarly_named_one(appmod, fake, which):
    A = appmod
    base, tids = _family(A, fake, 7)
    org = list(tids)[which]; tid = tids[org]
    before = _snapshot(A, fake, org, tid)
    res = A._delete_org_data(org)
    assert res["ok"], res
    after = _snapshot(A, fake, org, tid)
    assert after["keys"] == before["keys"]
    assert after["users"] == before["users"]
    assert after["platform"] == before["platform"]
    assert after["files"] == before["files"]
    # only this org's exact prefixes were ever listed; every deleted key is this org's
    assert {(b, p) for n, b, p in fake.calls if n == "list"} == {(MAIN, org + "/"), (HR, org + "/")}
    assert _backup_keys(org) <= fake.all_keys()            # backup copies stay
    assert os.path.exists(os.path.join(A.DATA_DIR, "backups", "mon", org, "shipments.db"))
    own = {k for _, k in _org_keys(org, tid)}
    for n, b, what in fake.mutating_calls():
        assert set(what if isinstance(what, tuple) else (what,)) <= own, (n, what)
    _assert_gone(A, fake, org, tid)
    # the neighbours still work: their order and their logins are there
    for o in tids:
        if o == org: continue
        assert _org_row(A, o) and _tomb(A, o) is None
        s = A.sdb(o); n = s.execute("SELECT COUNT(*) FROM shipments WHERE status='packed'").fetchone()[0]; s.close()
        assert n == 1
        assert os.path.exists(os.path.join(A.HIRE_LOCAL_UPLOAD_DIR, o + "__hire_uploads__1__2__id_front.jpg"))
        assert os.path.exists(os.path.join(A.DATA_DIR, "backups", "mon", o, "shipments.db"))


BAD_IDS = ["", None, " ", "/", "//", ".", "..", "../x", "a/b", "ab/", "/ab", "a b", " ab", "ab ", "%", "a%",
           "ab%2f", "%2e%2e", "a.b", "ab\x00", "ab\\", "*", "a*", "-ab", "_ab", "a" * 65, 0, [], ["ab"], {"a": 1},
           "ab/../cd", "orgs/../..", "אב"]


@pytest.mark.parametrize("bad", BAD_IDS, ids=[repr(x)[:16] for x in BAD_IDS])
def test_malformed_org_id_is_refused_before_anything_is_touched(appmod, fake, bad):
    A = appmod
    base, tids = _family(A, fake)
    keys = fake.all_keys(); users = A.ldj(A.USERS_FILE)
    plat = _platform_snapshot(A, "\0none", -1); files = _files_snapshot(A, "\0none", -1)
    c = A.pdb(); tombs = c.execute("SELECT COUNT(*) FROM org_tombstones").fetchone()[0]; c.close()
    res = A._delete_org_data(bad)
    assert res["ok"] is False and res["errors"]
    assert fake.calls == []                               # storage was not even listed
    assert fake.all_keys() == keys and A.ldj(A.USERS_FILE) == users
    assert _platform_snapshot(A, "\0none", -1) == plat and _files_snapshot(A, "\0none", -1) == files
    c = A.pdb(); assert c.execute("SELECT COUNT(*) FROM org_tombstones").fetchone()[0] == tombs; c.close()


def test_platform_sentinel_org_is_refused(appmod, fake):
    A = appmod
    assert A._delete_org_data(A.PLATFORM_ORG)["ok"] is False and fake.calls == []


@pytest.mark.parametrize("prefix", ["", "/", "//", "/ab/", "ab", "ab/videos", None])
def test_delete_prefix_refuses_a_prefix_that_could_match_everything(appmod, fake, prefix):
    A = appmod
    _family(A, fake)
    keys = fake.all_keys()
    out = A._r2_delete_prefix(MAIN, prefix, A.time.time() + 30)
    assert out["done"] is False and out["error"] and out["deleted"] == 0
    assert fake.calls == [] and fake.all_keys() == keys


def test_storage_prefixes_always_end_right_after_the_org_segment(appmod, fake):
    A = appmod
    for org in ("ab", "ab-2", "ab_", "AB", "a", "videos"):
        for bucket, prefix in A._org_storage_targets(org):
            assert bucket in (MAIN, HR)
            assert prefix in (org + "/",) or (prefix.startswith("backups/") and prefix.split("/")[1] in A._BACKUP_DOWS
                                              and prefix.split("/")[2:] == [org, ""]), prefix


def test_listing_that_returns_foreign_keys_deletes_nothing(appmod, fake):
    """If storage ever answers a prefix listing with keys outside it, stop: delete nothing."""
    A = appmod
    base, tids = _family(A, fake)
    fake.ignore_prefix = True
    keys = fake.all_keys()
    res = A._delete_org_data(base)
    own_ticket_file = {(MAIN, "support/%d/ab12_shot.png" % tids[base])}   # removed by exact key, not by listing
    assert res["state"] == "pending" and fake.all_keys() == keys - own_ticket_file
    assert not [c for c in fake.calls if c[0] == "delete_objects"]


@pytest.mark.parametrize("name", ["videos", "photos", "documents", "labels", "products", "invoices",
                                  "hire_uploads", "backups", "support"])
def test_org_named_like_a_shared_top_level_folder_never_deletes_that_folder(appmod, fake, name):
    A = appmod
    c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", (name,)); c.commit(); c.close()
    tid = _mk_org(A, name)
    extra = {(MAIN, name + "/SHARED_legacy_object.bin"), (HR, name + "/SHARED_legacy_object.bin"),
             (MAIN, name + "/" + name + "/own.bin")}
    for b, k in extra: fake.objects[b].add(k)
    keys = fake.all_keys()
    res = A._delete_org_data(name)
    assert res["ok"] and res["state"] == "partial" and not res["complete"]
    assert fake.all_keys() == keys                         # nothing under "<name>/" was removed
    assert not any(n == "list" and p == name + "/" for n, b, p in fake.calls)
    assert not [c for c in fake.calls if c[0] == "delete_objects"]
    assert A._org_delete_resume_pending() == 0 or _tomb(A, name)["state"] == "partial"
    assert fake.all_keys() == keys


def test_shop_shared_with_another_org_keeps_that_orgs_rows_and_unmapped_events(appmod, fake):
    A = appmod
    base, tids = _family(A, fake)
    other = base + "c"; shop = "shop-" + base
    c = A.pdb()
    c.execute("INSERT INTO tiktok_shops(org_id,shop_id,access_token,refresh_token,active) VALUES(?,?,?,?,1)",
              (other, shop, "other-access", "other-refresh"))
    c.commit(); c.close()
    A._delete_org_data(base)
    c = A.pdb()
    assert c.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=? AND shop_id=?", (other, shop)).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM tiktok_events WHERE shop_id=? AND org_id=''", (shop,)).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=?", (base,)).fetchone()[0] == 0
    c.close()


# ═════════════ 2. platform rows ═════════════

PURGED = {"billing_requests", "tiktok_shops", "tiktok_events", "tiktok_orders", "tiktok_live_sessions",
          "tiktok_control", "tickets"}
KEPT = {"organizations", "org_tombstones", "platform_audit", "payments"}   # organizations: its row is removed in step 1


def test_every_platform_table_with_org_id_has_an_explicit_decision(appmod):
    """The purge discovers tables from the live schema, so a table with an `org_id`
    column added later would be purged with nobody deciding. This pins today's list:
    adding such a table fails here until it is put in PURGED or KEPT on purpose
    (and, if kept, in app._ORG_DELETE_KEEP_TABLES)."""
    A = appmod
    c = A.pdb(); A._tt_control_ensure(c); c.commit()
    c.execute("DROP TABLE IF EXISTS tiktok_products")   # created only by the programmer's test
    c.commit()
    have = set()
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        if "org_id" in {r[1] for r in c.execute('PRAGMA table_info("%s")' % t).fetchall()}:
            have.add(t)
    c.close()
    assert have == PURGED | KEPT, "undecided: %r; gone: %r" % (have - PURGED - KEPT, (PURGED | KEPT) - have)
    assert KEPT | {"tickets"} == set(A._ORG_DELETE_KEEP_TABLES)


def test_owner_ledgers_and_sales_records_survive_and_everything_else_goes(appmod, fake):
    A = appmod
    base, tids = _family(A, fake)
    c = A.pdb()
    c.execute("INSERT INTO leads(company,email,converted_org) VALUES(?,?,?)", (base + " Co", "x@example.com", base))
    c.execute("INSERT INTO client_intakes(company_name,contact_email,converted_org) VALUES(?,?,?)", (base + " Co", "x@example.com", base))
    c.commit(); c.close()
    A._delete_org_data(base)
    c = A.pdb()
    assert c.execute("SELECT COUNT(*) FROM payments WHERE org_id=?", (base,)).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM platform_audit WHERE org_id=? AND action='org_delete'", (base,)).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM leads WHERE converted_org=?", (base,)).fetchone()[0] == 1
    assert c.execute("SELECT COUNT(*) FROM client_intakes WHERE converted_org=?", (base,)).fetchone()[0] == 1
    c.close()
    assert _own_platform_rows(A, base, tids[base]) == {}


# ═════════════ 3. the hourly loop ═════════════

def test_loop_with_nothing_pending_touches_nothing(appmod, fake):
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    before = (fake.all_keys(), A.ldj(A.USERS_FILE), _platform_snapshot(A, "\0none", -1), _files_snapshot(A, "\0none", -1))
    assert A._org_delete_resume_pending() == 0
    assert fake.calls == []
    assert before == (fake.all_keys(), A.ldj(A.USERS_FILE), _platform_snapshot(A, "\0none", -1), _files_snapshot(A, "\0none", -1))


@pytest.mark.parametrize("state", ["pending", "partial", "deleted", "", "PENDING", "weird"])
def test_loop_never_deletes_a_live_org_whatever_its_tombstone_says(appmod, fake, state):
    """A tombstone row on an org that still has its organizations row (restore from a
    backup, a hand edit, a bug) must not start a deletion."""
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    c = A.pdb(); c.execute("INSERT INTO org_tombstones(org_id,state) VALUES(?,?)", (base, state)); c.commit(); c.close()
    before = (fake.all_keys(), A.ldj(A.USERS_FILE), _files_snapshot(A, "\0none", -1))
    assert A._org_delete_resume_pending() == 0
    assert fake.calls == [] and _org_row(A, base)
    assert before == (fake.all_keys(), A.ldj(A.USERS_FILE), _files_snapshot(A, "\0none", -1))
    c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", (base,)); c.commit(); c.close()


@pytest.mark.parametrize("state", ["partial", "deleted", "", "PENDING", "weird"])
def test_loop_ignores_tombstones_that_are_not_pending(appmod, fake, state):
    """Finished / needs-a-human / unknown states: the loop leaves them alone even when
    objects exist under the old prefix."""
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    org = "qz" + uuid.uuid4().hex[:6]
    fake.objects[MAIN].add(org + "/videos/late.webm")
    c = A.pdb(); c.execute("INSERT INTO org_tombstones(org_id,state) VALUES(?,?)", (org, state)); c.commit(); c.close()
    assert A._org_delete_resume_pending() == 0 and fake.calls == []
    assert (MAIN, org + "/videos/late.webm") in fake.all_keys()


def test_loop_skips_the_founding_org_and_malformed_ids(appmod, fake):
    A = appmod
    c = A.pdb()
    c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'")
    bad = ["", "/", "..", "a/b", A.PLATFORM_ORG, "%"]
    for b in bad:
        c.execute("INSERT OR REPLACE INTO org_tombstones(org_id,state) VALUES(?, 'pending')", (b,))
    c.commit(); c.close()
    fake.objects[MAIN].add(A.DEFAULT_ORG + "/videos/own.webm")
    keys = fake.all_keys(); users = A.ldj(A.USERS_FILE); files = _files_snapshot(A, "\0none", -1)
    try:
        A._org_delete_resume_pending()
        assert fake.calls == [] and fake.all_keys() == keys
        assert A.ldj(A.USERS_FILE) == users and _files_snapshot(A, "\0none", -1) == files
        assert _org_row(A, A.DEFAULT_ORG)
    finally:
        c = A.pdb()
        for b in bad: c.execute("DELETE FROM org_tombstones WHERE org_id=?", (b,))
        c.commit(); c.close()


def test_org_without_directory_row_and_without_tombstone_is_not_deleted(appmod, fake):
    """Missing organizations row alone is not a deletion request."""
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    c = A.pdb(); c.execute("DELETE FROM organizations WHERE org_id=?", (base,)); c.commit(); c.close()
    A._org_delete_resume_pending()
    assert fake.calls == [] and os.path.isdir(A.org_path(base)) and (base + "-worker") in A.ldj(A.USERS_FILE)
    assert _org_keys(base, tids[base]) <= fake.all_keys()


def test_only_the_delete_route_and_the_loop_can_start_a_deletion():
    """Source pin: one writer of the tombstone, two callers of the deletion."""
    src = open(os.path.join(REPO, "app.py"), encoding="utf-8").read()
    assert src.count("INSERT INTO org_tombstones") == 1
    assert src.count("_delete_org_data(") == 3            # def + /api/account/delete + resume loop
    assert src.count("_org_delete_resume_pending(") == 2  # def + cleanup_all_orgs
    assert src.count("cleanup_all_orgs(") == 2            # def + the elected hourly loop


def test_several_workers_resuming_at_once_finish_once_and_touch_nobody_else(appmod, fake):
    A = appmod
    base, tids = _family(A, fake)
    org, tid = base, tids[base]
    before = _snapshot(A, fake, org, tid)
    assert A._delete_org_data(org, budget_sec=-1)["state"] == "pending"
    errs = []
    def run(fn):
        try: fn()
        except BaseException as e: errs.append(repr(e))
    ts = [threading.Thread(target=run, args=(A._org_delete_resume_pending,)) for _ in range(4)]
    ts += [threading.Thread(target=run, args=(lambda: A._delete_org_data(org),)) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join(60)
    assert not errs, errs
    assert _tomb(A, org)["state"] == "deleted"
    _assert_gone(A, fake, org, tid)
    after = _snapshot(A, fake, org, tid)
    assert after == before
    c = A.pdb()
    assert c.execute("SELECT COUNT(*) FROM org_tombstones WHERE org_id=?", (org,)).fetchone()[0] == 1
    c.close()


# ═════════════ 4. order and retry ═════════════

def _login(A, username):
    c = A.app.test_client()
    c.get("/login")
    tok = c.get_cookie("csrf_token").value
    return c.post("/api/login", json={"username": username, "password": PW}, headers={"X-CSRF-Token": tok})


def _stale_session(A, org):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=org + "-worker", role="worker", roles=["worker"], name="w", org=org)
    c.set_cookie("csrf_token", "tok")
    return c


def _kill_at(A, fake, m, step):
    def boom(*a, **k): raise Killed(step)
    if step == "logins":
        m.setattr(A, "update_json", boom)
    elif step == "platform_rows":
        m.setattr(A, "_org_purge_platform_rows", boom)
    elif step == "tickets":
        m.setattr(A, "_org_purge_tickets", boom)
    elif step == "ticket_file":
        fake.kill_on = ("delete_object", 1)
    elif step == "local_files":
        m.setattr(A, "_org_purge_local_files", boom)
    elif step == "storage_first_list":
        fake.kill_on = ("list", 1)
    elif step == "storage_first_delete":
        fake.kill_on = ("delete_objects", 1)
    elif step == "storage_second_bucket":
        fake.kill_on = ("delete_objects", 2)
    elif step == "record_outcome":
        real = A.json.dumps
        def dumps(o, *a, **k):
            if isinstance(o, dict) and "platform_rows" in o: raise Killed(step)
            return real(o, *a, **k)
        m.setattr(A.json, "dumps", dumps)
    elif step == "audit_line":
        m.setattr(A, "plog", boom)
    else:
        raise AssertionError(step)


STEPS = ["logins", "platform_rows", "tickets", "ticket_file", "local_files", "storage_first_list",
         "storage_first_delete", "storage_second_bucket", "record_outcome", "audit_line"]


@pytest.mark.parametrize("step", STEPS)
def test_killed_after_each_step_then_resumed_ends_complete(appmod, fake, monkeypatch, step):
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    org, tid = base, tids[base]
    before = _snapshot(A, fake, org, tid)
    with monkeypatch.context() as m:
        _kill_at(A, fake, m, step)
        with pytest.raises(Killed):
            A._delete_org_data(org)
    fake.kill_on = None
    # the worker is dead, nothing has resumed yet: nobody of that company gets in
    assert not _org_row(A, org) and _tomb(A, org) is not None
    for u in (org + "-worker", org + "-admin"):
        r = _login(A, u)
        assert r.status_code in (401, 403) or not (r.get_json() or {}).get("ok"), (step, u, r.get_json())
    r = _stale_session(A, org).get("/api/shows")
    assert r.status_code in (401, 402, 403), (step, r.status_code)
    now = _snapshot(A, fake, org, tid)
    assert {k: (v, now["files"].get(k)) for k, v in before["files"].items() if now["files"].get(k) != v} == {}
    assert set(now["files"]) == set(before["files"])
    assert now == before                                   # and nobody else lost anything
    if step == "audit_line":
        assert _tomb(A, org)["state"] == "deleted"         # everything was already done
    else:
        assert _tomb(A, org)["state"] == "pending"
        assert A._org_delete_resume_pending() == 1         # the hourly loop
    assert _tomb(A, org)["state"] == "deleted", _tomb(A, org)
    _assert_gone(A, fake, org, tid)
    # nothing comes back: an old cookie, a sign-in attempt and another loop pass
    assert _stale_session(A, org).get("/api/shows").status_code in (401, 402, 403)
    _login(A, org + "-worker")
    attempts = _tomb(A, org)["attempts"]
    assert A._org_delete_resume_pending() == 0
    assert _tomb(A, org)["attempts"] == attempts
    _assert_gone(A, fake, org, tid)
    assert _snapshot(A, fake, org, tid) == before


def test_killed_before_the_tombstone_commits_changes_nothing(appmod, fake, monkeypatch):
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    org, tid = base, tids[base]
    everything = (fake.all_keys(), A.ldj(A.USERS_FILE), _platform_snapshot(A, "\0none", -1), _files_snapshot(A, "\0none", -1))
    with monkeypatch.context() as m:
        def boom(): raise Killed("pdb")
        m.setattr(A, "pdb", boom)
        with pytest.raises(Killed):
            A._delete_org_data(org)
    assert _tomb(A, org) is None and _org_row(A, org)
    assert A._org_delete_resume_pending() == 0 and fake.calls == []
    assert everything == (fake.all_keys(), A.ldj(A.USERS_FILE), _platform_snapshot(A, "\0none", -1), _files_snapshot(A, "\0none", -1))


def test_only_the_deleted_orgs_database_files_are_removed(appmod, fake):
    A = appmod
    base, tids = _family(A, fake)
    dbs = {o: (A.shipments_db_path(o), A.giveaway_db_path(o)) for o in tids}
    assert all(os.path.exists(p) for ps in dbs.values() for p in ps)
    A._delete_org_data(base)
    for o, ps in dbs.items():
        for p in ps:
            assert os.path.exists(p) == (o != base), p
    assert os.path.exists(A.shipments_db_path(A.DEFAULT_ORG)) and os.path.exists(A.PLATFORM_DB)


# ═════════════ 5. local paths ═════════════

def test_symlinks_are_never_followed_out_of_the_data_root(appmod, fake, tmp_path):
    A = appmod
    outside = tmp_path / "outside"; outside.mkdir()
    for n in ("a", "b", "c"):
        (outside / n).mkdir(); (outside / n / "keep.txt").write_text("keep")
    base, tids = _family(A, fake)
    # (a) a link INSIDE the org folder, (b) the org's backup folder is a link
    os.symlink(str(outside / "a"), os.path.join(A.org_path(base), "videos_link"))
    b = os.path.join(A.DATA_DIR, "backups", "tue"); os.makedirs(b, exist_ok=True)
    os.symlink(str(outside / "b"), os.path.join(b, base))
    A._delete_org_data(base)
    assert (outside / "a" / "keep.txt").read_text() == "keep" and (outside / "b" / "keep.txt").read_text() == "keep"
    os.unlink(os.path.join(b, base))
    # (c) the org folder itself is a link: refused, reported, target intact
    org2 = base + "c"
    import shutil
    shutil.rmtree(A.org_path(org2)); os.symlink(str(outside / "c"), A.org_path(org2))
    res = A._delete_org_data(org2)
    assert (outside / "c" / "keep.txt").read_text() == "keep"
    assert res["state"] == "pending" and any("local files" in e for e in res["errors"])
    os.unlink(A.org_path(org2))
    assert A._delete_org_data(org2)["state"] == "deleted"


def test_local_delete_targets_stay_inside_the_data_root(appmod, fake, monkeypatch):
    """Record every rmtree/remove the deletion performs: each is the org's own folder,
    its own backup copy, its own ticket folder or its own flat hire file."""
    A = appmod
    import shutil
    base, tids = _family(A, fake)
    org, tid = base, tids[base]
    d = os.path.join(A.DATA_DIR, "support", str(tid)); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "f.png"), "wb").close()
    seen = []
    real_rm, real_remove = shutil.rmtree, os.remove
    monkeypatch.setattr(shutil, "rmtree", lambda p, *a, **k: (seen.append(os.path.abspath(p)), real_rm(p, *a, **k))[1])
    monkeypatch.setattr(os, "remove", lambda p, *a, **k: (seen.append(os.path.abspath(p)), real_remove(p, *a, **k))[1])
    A._delete_org_data(org)
    root = os.path.abspath(A.DATA_DIR)
    allowed = {os.path.join(root, "orgs", org), os.path.join(root, "support", str(tid)),
               os.path.join(root, "hire_uploads", org + "__hire_uploads__1__2__id_front.jpg")}
    assert seen and set(seen) <= allowed, set(seen) - allowed


# ═════════════ 6. unchanged behaviour ═════════════

def _as(A, username):
    info = A.ldj(A.USERS_FILE)[username]
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=info["role"], roles=A._effective_roles(info), name=info["name"], org=info["org"])
    c.set_cookie("csrf_token", "tok")
    c.csrf = {"X-CSRF-Token": "tok"}
    return c


@pytest.mark.parametrize("who,body", [("worker", {}), ("worker", {"wipe_org": True}), ("admin", {"wipe_org": True}), ("admin", {})])
def test_single_account_delete_in_a_company_with_another_admin_keeps_the_company(appmod, fake, who, body):
    A = appmod
    base, tids = _family(A, fake)
    org, tid = base, tids[base]
    with A.update_json(A.USERS_FILE) as users:
        users[org + "-admin2"] = {"password": A._h(PW), "role": "admin", "name": "second admin", "org": org}
    keys = fake.all_keys(); plat = _platform_snapshot(A, "\0none", -1)
    c = _as(A, org + "-" + who)
    j = c.post("/api/account/delete", headers=c.csrf, json=body).get_json()
    assert j["ok"] and j["org_deleted"] is False and "org_cleanup" not in j
    users = A.ldj(A.USERS_FILE)
    assert (org + "-" + who) not in users and (org + "-admin2") in users
    assert _org_row(A, org) and _tomb(A, org) is None and os.path.isdir(A.org_path(org))
    assert fake.calls == [] and fake.all_keys() == keys
    plat2 = _platform_snapshot(A, "\0none", -1)
    plat.pop("platform_audit", None); plat2.pop("platform_audit", None)
    assert plat == plat2


def test_last_admin_without_wipe_org_gets_409_and_nothing_is_deleted(appmod, fake):
    A = appmod
    base, tids = _family(A, fake)
    c = _as(A, base + "-admin")
    r = c.post("/api/account/delete", headers=c.csrf, json={})
    assert r.status_code == 409 and r.get_json()["need_org_confirm"] is True
    assert (base + "-admin") in A.ldj(A.USERS_FILE) and _org_row(A, base) and _tomb(A, base) is None
    assert fake.calls == []


def test_another_orgs_admin_cannot_name_the_org_to_wipe(appmod, fake):
    """The org comes from the caller's own user record, never from the request."""
    A = appmod
    base, tids = _family(A, fake)
    victim = base + "c"
    c = _as(A, base + "-admin")
    j = c.post("/api/account/delete", headers=c.csrf, json={"wipe_org": True, "org": victim, "org_id": victim}).get_json()
    assert j["org_deleted"] is True
    assert _org_row(A, victim) and _tomb(A, victim) is None and _tomb(A, base) is not None
    assert _org_keys(victim, tids[victim]) <= fake.all_keys()


def test_intake_provision_skips_a_tombstoned_slug_and_still_creates(appmod, fake):
    A = appmod
    slug = "qi" + uuid.uuid4().hex[:6]
    c = A.pdb()
    c.execute("INSERT INTO org_tombstones(org_id,state) VALUES(?, 'deleted')", (slug,))
    iid = c.execute("INSERT INTO client_intakes(company_name,contact_name,contact_email) VALUES(?,?,?)",
                    (slug, "Dana", "dana@example.com")).lastrowid
    c.commit(); c.close()
    cl = A.app.test_client()
    with cl.session_transaction() as s:
        s.update(user="qa-super", role="superadmin", roles=["superadmin"], name="p", org=A.PLATFORM_ORG)
    with A.update_json(A.USERS_FILE) as users:
        users["qa-super"] = {"password": A._h(PW), "role": "superadmin", "name": "p", "org": A.PLATFORM_ORG}
    cl.set_cookie("csrf_token", "tok")
    j = cl.post("/api/intakes/%d/provision" % iid, headers={"X-CSRF-Token": "tok"}, json={}).get_json()
    assert j.get("ok"), j
    assert _org_row(A, slug + "2") and not _org_row(A, slug)
    assert fake.calls == []


# ═════════════ 7. staging safe mode ═════════════

def test_staging_safe_mode_deletes_no_object_and_stays_pending(appmod, fake, monkeypatch):
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    org, tid = base, tids[base]
    before = _snapshot(A, fake, org, tid)
    keys = fake.all_keys()
    monkeypatch.setattr(A, "r2", A._SafeR2(fake))
    res = A._delete_org_data(org)
    assert res["ok"] and res["state"] == "pending" and not res["complete"]
    for _ in range(3):
        assert A._org_delete_resume_pending() == 1
    assert fake.all_keys() == keys and fake.mutating_calls() == []      # the shared bucket is intact
    assert _tomb(A, org)["state"] == "pending" and _tomb(A, org)["attempts"] == 4
    assert not _org_row(A, org) and _snapshot(A, fake, org, tid) == before
    assert not (_login(A, org + "-worker").get_json() or {}).get("ok")
    monkeypatch.setattr(A, "r2", fake)                                    # outside safe mode it finishes
    assert A._org_delete_resume_pending() == 1 and _tomb(A, org)["state"] == "deleted"
    _assert_gone(A, fake, org, tid)
    assert _snapshot(A, fake, org, tid) == before


# ═════════════ founding org — child process, own DATA_DIR ═════════════

_CHILD = r'''
import os, sys, json, io, contextlib
phase, data_dir, repo = sys.argv[1], sys.argv[2], sys.argv[3]
os.environ["DATA_DIR"] = data_dir; os.environ["SECRET_KEY"] = "t" * 40
for k in ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "APP_ENV", "DEFAULT_ORG", "SUPERADMIN_USER"):
    os.environ.pop(k, None)
sys.path.insert(0, repo)
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    import app as A
    D = A.DEFAULT_ORG
    class Killed(BaseException): pass
    class R2:
        def __init__(s, keys): s.o = {"m": set(keys), "h": {D + "/hire_uploads/1/1/i9.jpg"}}
        def list_objects_v2(s, Bucket, Prefix="", MaxKeys=1000, **k):
            ks = sorted(x for x in s.o[Bucket] if x.startswith(Prefix)); return {"Contents": [{"Key": x} for x in ks]}
        def delete_objects(s, Bucket, Delete): s.o[Bucket] -= {o["Key"] for o in Delete["Objects"]}; return {}
        def delete_object(s, Bucket, Key): s.o[Bucket].discard(Key); return {}
    def state():
        c = A.pdb()
        t = c.execute("SELECT state FROM org_tombstones WHERE org_id=?", (D,)).fetchone()
        row = bool(c.execute("SELECT 1 FROM organizations WHERE org_id=?", (D,)).fetchone()); c.close()
        ships = None
        if os.path.exists(A.shipments_db_path(D)):
            s = A.sdb(D); ships = s.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]; s.close()
        return {"tombstone": t[0] if t else None, "org_row": row, "shipments": ships,
                "users": sorted(u for u, v in A.ldj(A.USERS_FILE).items() if (v.get("org") or D) == D)}
    def login(u):
        c = A.app.test_client(); c.get("/login"); tok = c.get_cookie("csrf_token").value
        r = c.post("/api/login", json={"username": u, "password": "Passw0rd!x"}, headers={"X-CSRF-Token": tok})
        return bool((r.get_json() or {}).get("ok"))
    out = {}
    if phase in ("wipe", "kill"):
        fake = R2({D + "/videos/own.webm", "videos/legacy.webm", "backups/mon/" + D + "/shipments.db", "backups/mon/platform.db"})
        A.r2 = fake; A.R2_BUCKET = "m"; A.R2_HR_BUCKET = "h"
        s = A.sdb(D)
        s.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform,buyer_name) "
                  "VALUES('S-1','TRK1','pending','csv','Show 1','tiktok','Buyer')"); s.commit(); s.close()
        with A.update_json(A.USERS_FILE) as users:
            for u in users.values(): u["password"] = A._h("Passw0rd!x")
    if phase == "wipe":
        cl = A.app.test_client()
        with cl.session_transaction() as s: s.update(user="admin", role="admin", roles=["admin"], name="Admin", org=D)
        cl.set_cookie("csrf_token", "tok")
        out["response"] = cl.post("/api/account/delete", headers={"X-CSRF-Token": "tok"}, json={"wipe_org": True}).get_json()
        out["keys_left"] = sorted(fake.o["m"] | fake.o["h"]); out["after"] = state()
    elif phase == "kill":
        real = A.update_json
        def boom(*a, **k): raise Killed()
        A.update_json = boom
        try: A._delete_org_data(D)
        except Killed: pass
        A.update_json = real
        out["after_kill"] = state(); out["worker_can_sign_in"] = login("worker1")
        out["resumed"] = A._org_delete_resume_pending(); out["after_loop"] = state()
        out["worker_can_sign_in_after_loop"] = login("worker1")
    elif phase == "boot":
        out["after_boot"] = state(); out["resumed"] = A._org_delete_resume_pending(); out["after_loop"] = state()
sys.stdout.write(json.dumps(out))
'''


def _child(phase, data_dir):
    p = subprocess.run([sys.executable, "-c", _CHILD, phase, str(data_dir), REPO],
                       capture_output=True, text=True, timeout=180)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def test_founding_org_is_not_left_both_deleted_and_live(tmp_path):
    w = _child("wipe", tmp_path)
    b = _child("boot", tmp_path)
    info = textwrap.shorten(json.dumps({"wipe": w, "boot": b}), 1500)
    refused = w["after"]["tombstone"] is None and w["after"]["shipments"] == 1
    stays_deleted = b["after_boot"]["org_row"] is False
    assert refused or stays_deleted, info


def test_founding_org_interrupted_deletion_is_not_left_half_done(tmp_path):
    k = _child("kill", tmp_path)
    info = textwrap.shorten(json.dumps(k), 1500)
    untouched = k["after_kill"]["tombstone"] is None and k["after_kill"]["org_row"]
    locked_out = not k["worker_can_sign_in"]
    assert untouched or locked_out, info


def test_org_id_with_trailing_newline_is_refused(appmod, fake):
    A = appmod
    try:
        res = A._delete_org_data("zz\n")
        assert res["ok"] is False and fake.calls == []
    finally:
        c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", ("zz\n",)); c.commit(); c.close()


# ═════════════ re-review of e973284: the loop's late-row purge ═════════════

@pytest.mark.parametrize("state", ["deleted", "partial", "stuck", "pending", "weird"])
def test_late_row_purge_never_touches_a_live_org_or_a_neighbour(appmod, fake, state):
    """The loop now also removes platform rows of finished deletions. It must do that
    only for ids without an organizations row, and only for that exact id."""
    A = appmod
    c = A.pdb(); c.execute("UPDATE org_tombstones SET state='deleted' WHERE state='pending'"); c.commit(); c.close()
    base, tids = _family(A, fake)
    live, gone = base, "qg" + uuid.uuid4().hex[:6]
    c = A.pdb()
    c.execute("INSERT INTO org_tombstones(org_id,state) VALUES(?,?)", (live, state))        # stray tombstone on a LIVE org
    if state != "pending":
        c.execute("INSERT INTO org_tombstones(org_id,state) VALUES(?,?)", (gone, state))    # a finished deletion...
        c.execute("INSERT INTO tiktok_shops(org_id,shop_id,access_token,refresh_token,active) VALUES(?,?,?,?,1)",
                  (gone, "late-" + gone, "late", "late"))                                    # ...with a late row
    c.commit(); c.close()
    before = _platform_snapshot(A, gone, -1)
    keys, users, files = fake.all_keys(), A.ldj(A.USERS_FILE), _files_snapshot(A, "\0none", -1)
    try:
        assert A._org_delete_resume_pending() == 0
        after = _platform_snapshot(A, gone, -1)
        before.pop("platform_audit"); after.pop("platform_audit")
        assert after == before                                  # the live org and its neighbours kept every row
        assert fake.calls == [] and fake.all_keys() == keys
        assert A.ldj(A.USERS_FILE) == users and _files_snapshot(A, "\0none", -1) == files
        c = A.pdb()
        left = c.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=?", (gone,)).fetchone()[0]
        c.close()
        assert left == 0
    finally:
        c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", (live,)); c.commit(); c.close()
