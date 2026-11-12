"""SEC-6i — backup copies of a deleted company are erased 30 days after the deletion,
the backup jobs stop copying it, and nothing else's backups are ever touched.

Temp DATA_DIR from conftest; storage is an in-memory fake (never a real bucket); the
clock is injected (`now=`), nothing sleeps.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta

import pytest

import ps_backup

PW = "Passw0rd!x"
MAIN, HR = "fake-main", "fake-hr"
DELETED_AT = datetime(2026, 1, 1, 12, 0, 0)          # UTC, written into requested_at
DAY30 = DELETED_AT + timedelta(days=30)


class FakeR2:
    """In-memory S3 stand-in: {bucket: set(keys)}; records every call."""
    def __init__(self, objects):
        self.objects = {b: set(ks) for b, ks in objects.items()}
        self.calls = []
        self.fail_delete = 0
        self.lock = threading.Lock()

    def list_objects_v2(self, Bucket, Prefix="", MaxKeys=1000, **kw):
        with self.lock:
            self.calls.append(("list", Bucket, Prefix))
            keys = sorted(k for k in self.objects.get(Bucket, ()) if k.startswith(Prefix))[:MaxKeys]
        return {"Contents": [{"Key": k} for k in keys], "KeyCount": len(keys)}

    def delete_objects(self, Bucket, Delete):
        keys = [o["Key"] for o in Delete["Objects"]]
        with self.lock:
            self.calls.append(("delete_objects", Bucket, tuple(keys)))
            if self.fail_delete:
                self.fail_delete -= 1
                raise TimeoutError("simulated storage timeout AKIAFAKEKEY")
            self.objects[Bucket] -= set(keys)
        return {}

    def put_object(self, Bucket, Key, Body=b""):
        with self.lock:
            self.calls.append(("put", Bucket, Key))
            self.objects[Bucket].add(Key)
        return {}

    def __getattr__(self, name):
        raise AssertionError("unexpected storage call: " + name)

    def all_keys(self):
        return {(b, k) for b, ks in self.objects.items() for k in ks}

    def deleted_keys(self):
        return {k for n, _, ks in self.calls if n == "delete_objects" for k in ks}


class FakeStore:
    """In-memory stand-in for the dedicated backup bucket (ps_backup store surface)."""
    def __init__(self): self.obj = {}; self.fail_delete = 0
    def put_fileobj(self, key, fh): self.obj[key] = fh.read()
    def put_bytes(self, key, data): self.obj[key] = data
    def get_bytes(self, key): return self.obj[key]
    def size(self, key): return len(self.obj[key])
    def list_keys(self, prefix): return [k for k in self.obj if k.startswith(prefix)]
    def delete(self, key):
        if self.fail_delete:
            self.fail_delete -= 1
            raise TimeoutError("simulated storage timeout")
        self.obj.pop(key, None)


def _mk_org(A, org, internal=0):
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan,internal) VALUES(?,?,?,?,'pro',?)",
              (org, org.upper() + " Co", org[:10].upper(), "active", internal))
    c.commit(); c.close()
    A.provision_org(org)
    with A.update_json(A.USERS_FILE) as users:
        users[org + "-admin"] = {"password": A._h(PW), "role": "admin", "name": org + " admin", "org": org}
    return org


def _bk(org):
    return {(MAIN, "backups/%s/%s/%s" % (d, org, f)) for d in ("mon", "wed", "sun") for f in ("shipments.db", "giveaways.db")}


def _local(A, org, dow="mon"):
    return os.path.join(A.DATA_DIR, "backups", dow, org, "shipments.db")


def _mk_local(A, org, dow="mon"):
    p = _local(A, org, dow)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"local backup copy")


def _tomb(A, org):
    c = A.pdb()
    r = c.execute("SELECT * FROM org_tombstones WHERE org_id=?", (org,)).fetchone()
    c.close()
    return dict(r) if r else None


def _plant_tomb(A, org, when=DELETED_AT):
    c = A.pdb()
    c.execute("INSERT OR REPLACE INTO org_tombstones(org_id,state,requested_at) VALUES(?,'deleted',?)",
              (org, when.strftime("%Y-%m-%d %H:%M:%S")))
    c.commit(); c.close()


@pytest.fixture
def world(appmod, monkeypatch):
    """Org `ab<x>` deleted on DELETED_AT, next to live `ab<x>c` / `ab<x>-2` / `x ab<x>`
    look-alikes and the founding org, all with backup copies in the bucket and on disk."""
    A = appmod
    org = "ab" + uuid.uuid4().hex[:6]
    near = [org + "c", org + "-2"]
    for o in [org] + near:
        _mk_org(A, o)
    others = set()
    for o in near + [A.DEFAULT_ORG, "x" + org]:
        others |= _bk(o)
        _mk_local(A, o)
    others |= {(MAIN, "backups/mon/platform.db"), (MAIN, "backups/mon/users.json"),
               (MAIN, "backups/mon/" + org), (MAIN, "backups/" + org + "/mon/shipments.db"),
               (MAIN, "backups/mon/x/" + org + "/shipments.db"), (MAIN, "db-backups/20260101T000000Z/" + org + "/shipments.db"),
               (MAIN, near[0] + "/videos/v.webm"), (HR, "backups/mon/" + org + "/shipments.db")}
    for d in ("mon", "thu"):
        _mk_local(A, org, d)
    objs = {MAIN: set(), HR: set()}
    for b, k in _bk(org) | others:
        objs[b].add(k)
    fake = FakeR2(objs)
    monkeypatch.setattr(A, "r2", fake)
    monkeypatch.setattr(A, "R2_BUCKET", MAIN)
    monkeypatch.setattr(A, "R2_HR_BUCKET", HR)
    monkeypatch.setattr(A, "_BK_OK", False)
    monkeypatch.setattr(A, "BACKUP_PRUNE_IN_APP", False)
    assert A._delete_org_data(org)["state"] == "deleted"
    assert _bk(org) <= fake.all_keys()                      # deletion itself keeps the backups
    c = A.pdb()
    c.execute("UPDATE org_tombstones SET requested_at=? WHERE org_id=?", (DELETED_AT.strftime("%Y-%m-%d %H:%M:%S"), org))
    # Tombstones left by other test files in this session must not come due under the
    # injected clock: park their deletion time in the future, put it back afterwards.
    parked = [(r[0], r[1]) for r in c.execute("SELECT org_id, requested_at FROM org_tombstones WHERE org_id<>?", (org,)).fetchall()]
    c.execute("UPDATE org_tombstones SET requested_at='2099-01-01 00:00:00' WHERE org_id<>?", (org,))
    c.commit(); c.close()
    fake.calls.clear()
    yield {"A": A, "org": org, "near": near, "fake": fake, "others": others}
    c = A.pdb()
    c.executemany("UPDATE org_tombstones SET requested_at=? WHERE org_id=?", [(t, o) for o, t in parked])
    c.commit(); c.close()


def _listed(A, org, now):
    return [d for d in A._org_unfinished_deletions(now=now) if d["org_id"] == org]


def test_keep_period_is_30_days(appmod):
    assert appmod.ORG_BACKUP_KEEP_DAYS == 30


def test_not_erased_at_29_days_erased_at_30(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    for now in (DELETED_AT, DELETED_AT + timedelta(days=29), DAY30 - timedelta(seconds=1)):
        assert A._org_backups_erase_due(now=now) == 0
    assert _bk(org) <= fake.all_keys() and os.path.exists(_local(A, org)) and not fake.calls
    assert _tomb(A, org)["backups_state"] is None and not _listed(A, org, DAY30 - timedelta(seconds=1))

    assert A._org_backups_erase_due(now=DAY30) == 1
    assert fake.all_keys() == world["others"]               # exactly the org's weekday copies are gone
    assert fake.deleted_keys() == {k for _, k in _bk(org)}
    assert not os.path.exists(os.path.join(A.DATA_DIR, "backups", "mon", org))
    assert not os.path.exists(os.path.join(A.DATA_DIR, "backups", "thu", org))
    for o in world["near"] + [A.DEFAULT_ORG, "x" + org]:   # live, look-alike and founding copies on disk
        assert os.path.exists(_local(A, o))
    t = _tomb(A, org)
    assert t["backups_state"] == "erased" and t["backups_erased_at"] == "2026-01-31 12:00:00"
    assert t["state"] == "deleted" and not _listed(A, org, DAY30 + timedelta(days=5))
    n = len(fake.calls)                                     # done: later passes make no storage calls
    assert A._org_backups_erase_due(now=DAY30 + timedelta(days=1)) == 0 and len(fake.calls) == n
    c = A.pdb()
    audit = [r[0] for r in c.execute("SELECT detail FROM platform_audit WHERE org_id=? AND action='org_backups_erase'", (org,)).fetchall()]
    c.close()
    assert len(audit) == 1 and "state=erased" in audit[0]


def test_only_listing_prefixes_with_the_exact_org_segment(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    A._org_backups_erase_due(now=DAY30)
    listed = {p for n, b, p in fake.calls if n == "list"}
    assert listed == {"backups/%s/%s/" % (d, org) for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    assert {b for n, b, p in fake.calls} == {MAIN}
    for bad in ("", None, "a/b", "../x", "ab/", "a b", "ab\n", "."):
        assert A._org_backup_prefixes(bad) == []


def test_live_founding_internal_and_malformed_ids_are_never_touched(world):
    """Tombstone rows written straight into the database, all long overdue."""
    A, org, fake = world["A"], world["org"], world["fake"]
    live = world["near"][0]
    internal = _mk_org(A, "in" + uuid.uuid4().hex[:6], internal=1)
    fake.objects[MAIN] |= {k for _, k in _bk(internal)} | {"backups/mon/mon/shipments.db", "backups/mon/backups/x.db"}
    _mk_local(A, internal)
    c = A.pdb(); c.execute("UPDATE org_tombstones SET requested_at='2099-01-01 00:00:00' WHERE org_id=?", (org,)); c.commit(); c.close()
    for bad in (A.DEFAULT_ORG, live, internal, A.PLATFORM_ORG, "", "../x", "ab\n", "a/b", "mon", "backups", "Videos"):
        _plant_tomb(A, bad, DELETED_AT - timedelta(days=400))
    before = fake.all_keys()
    try:
        assert A._org_backups_erase_due(now=DAY30) == 0
        deadline = 10 ** 12
        for bad in (A.DEFAULT_ORG, live, internal, A.PLATFORM_ORG, "", "../x", "ab\n", "a/b", "mon", "backups", "Videos"):
            assert A._org_backups_erase(bad, deadline, DAY30) is None
        assert fake.all_keys() == before and not fake.calls
        for o in (A.DEFAULT_ORG, live, internal):
            assert os.path.exists(_local(A, o))
    finally:
        c = A.pdb()
        c.execute("DELETE FROM org_tombstones WHERE org_id IN (?,?,?,?,'','../x','ab\n','a/b','mon','backups','Videos')",
                  (A.DEFAULT_ORG, live, internal, A.PLATFORM_ORG))
        c.commit(); c.close()


def test_garbage_deletion_time_never_erases_and_is_listed(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    c = A.pdb(); c.execute("UPDATE org_tombstones SET requested_at=NULL WHERE org_id=?", (org,)); c.commit(); c.close()
    assert A._org_backups_erase_due(now=DAY30 + timedelta(days=999)) == 0 and not fake.calls
    assert _bk(org) <= fake.all_keys()
    assert _listed(A, org, DAY30)[0]["backups_overdue"] == 1


def test_backup_jobs_skip_a_tombstoned_org(world, monkeypatch):
    A, org, fake = world["A"], world["org"], world["fake"]
    live = world["near"][0]
    # worst case: the deleted company's folder and database are (still / again) on the volume
    A.provision_org(org)
    assert os.path.exists(A.shipments_db_path(org))
    monkeypatch.setattr(A, "list_org_ids", lambda: [A.DEFAULT_ORG, live, org])
    assert A._backup_org_ids() == [A.DEFAULT_ORG, live]
    fake.objects[MAIN] -= {k for _, k in _bk(org)}
    A._backup_all()
    puts = {k for n, b, k in fake.calls if n == "put"}
    assert any(k.endswith("/" + live + "/shipments.db") for k in puts)
    assert any(k.endswith("/" + A.DEFAULT_ORG + "/shipments.db") for k in puts)
    assert not any("/" + org + "/" in k for k in puts)
    names = [n for n, _ in A._backup_targets()]            # Backup V2 target list
    assert live + "/shipments.db" in names and not any(n.startswith(org + "/") for n in names)
    # a tombstone planted on the founding org never stops the warehouse's own backups
    _plant_tomb(A, A.DEFAULT_ORG)
    try:
        assert A.DEFAULT_ORG in A._backup_org_ids()
    finally:
        c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", (A.DEFAULT_ORG,)); c.commit(); c.close()
    # tombstones unreadable: nothing is skipped (a live company is never left without a backup)
    with monkeypatch.context() as m:
        m.setattr(A, "pdb", lambda: (_ for _ in ()).throw(sqlite3.OperationalError("locked")))
        assert A._backup_org_ids() == [A.DEFAULT_ORG, live, org]


def test_two_workers_at_once(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    barrier = threading.Barrier(2); out = []
    def run():
        barrier.wait()
        out.append(A._org_backups_erase_due(now=DAY30))
    ts = [threading.Thread(target=run) for _ in range(2)]
    [t.start() for t in ts]; [t.join(30) for t in ts]
    assert sorted(out) == [0, 1]
    assert fake.all_keys() == world["others"]
    t = _tomb(A, org)
    assert t["backups_state"] == "erased" and t["backups_attempts"] == 1


def test_retry_after_a_storage_failure(world, capsys):
    A, org, fake = world["A"], world["org"], world["fake"]
    fake.fail_delete = 1
    assert A._org_backups_erase_due(now=DAY30) == 0
    t = _tomb(A, org)
    assert t["backups_state"] == "failed" and t["backups_erased_at"] is None
    assert "TimeoutError" in t["backups_detail"] and "AKIAFAKEKEY" not in t["backups_detail"]
    assert "AKIAFAKEKEY" not in capsys.readouterr().out
    row = _listed(A, org, DAY30)[0]                        # failing: shown at once, no grace
    assert row["backups_state"] == "failed" and row["backups_overdue"] == 1 and "backups_detail" not in row
    assert fake.all_keys() >= world["others"]
    assert A._org_backups_erase_due(now=DAY30 + timedelta(hours=1)) == 1
    assert fake.all_keys() == world["others"]
    assert _tomb(A, org)["backups_state"] == "erased" and not _listed(A, org, DAY30 + timedelta(hours=1))


def test_stops_retrying_at_the_attempt_limit(world, monkeypatch):
    A, org, fake = world["A"], world["org"], world["fake"]
    monkeypatch.setattr(A, "ORG_DELETE_MAX_ATTEMPTS", 2)
    fake.fail_delete = 10 ** 6
    A._org_backups_erase_due(now=DAY30); A._org_backups_erase_due(now=DAY30)
    assert _tomb(A, org)["backups_state"] == "stuck"
    n = len(fake.calls)
    assert A._org_backups_erase_due(now=DAY30) == 0 and len(fake.calls) == n
    assert _listed(A, org, DAY30)[0]["backups_state"] == "stuck"


def test_time_budget_is_respected(world):
    A, org, fake = world["A"], world["org"], world["fake"]
    assert A._org_backups_erase_due(now=DAY30, budget_sec=0) == 0 and not fake.calls
    assert _tomb(A, org)["backups_state"] is None


def test_overdue_erasure_is_shown_to_the_platform_owner(world):
    """The loop did not run: after 30 days (+2h grace) the company is listed."""
    A, org = world["A"], world["org"]
    assert not _listed(A, org, DAY30 + timedelta(hours=1))
    row = _listed(A, org, DAY30 + timedelta(hours=3))[0]
    assert row["backups_overdue"] == 1 and row["state"] == "deleted" and row["backups_state"] is None
    assert not _listed(A, world["near"][0], DAY30 + timedelta(days=99))
    # through the route, with the real clock: the deletion is dated far in the past
    su = A.app.test_client()
    with su.session_transaction() as s:
        s.update(user="su" + uuid.uuid4().hex[:6], role="superadmin", roles=["superadmin"], name="x", org=A.PLATFORM_ORG)
    listed = su.get("/api/orgs").get_json()["unfinished_deletions"]
    mine = [d for d in listed if d["org_id"] == org]
    assert mine and mine[0]["backups_overdue"] == 1
    assert set(mine[0]) == {"org_id", "state", "attempts", "requested_at", "finished_at",
                            "backups_state", "backups_erased_at", "backups_overdue"}


def test_hourly_cleanup_runs_the_erasure(world, monkeypatch):
    A = world["A"]
    seen = []
    monkeypatch.setattr(A, "list_org_ids", lambda: [])
    monkeypatch.setattr(A, "_tt_retention_purge", lambda: 0)
    monkeypatch.setattr(A, "_org_delete_resume_pending", lambda: 0)
    monkeypatch.setattr(A, "_org_backups_erase_due", lambda: seen.append(1) or 7)
    assert A.cleanup_all_orgs()["org_backups_erased"] == 7 and seen == [1]


# ── dedicated backup bucket (Backup V2) ───────────────────────────────────────

def _v2_store(tmp_path, org, other):
    """Two runs holding platform.db + one file per org, written by the real run_backup."""
    store = FakeStore()
    src = tmp_path / "src"; src.mkdir()
    targets = []
    for name in ("platform.db", org + "/shipments.db", org + "/packing_log.csv", other + "/shipments.db"):
        p = src / name.replace("/", "__")
        if name.endswith(".db"):
            c = sqlite3.connect(str(p)); c.execute("CREATE TABLE t(v)"); c.execute("INSERT INTO t VALUES(?)", (name,)); c.commit(); c.close()
        else:
            p.write_text("a,b\n")
        targets.append((name, str(p)))
    for when in (datetime(2025, 12, 20, 6), datetime(2025, 12, 31, 18)):
        ps_backup.run_backup(targets, store, now=when, tmp_dir=str(tmp_path))
    return store


def test_dedicated_bucket_is_not_touched_unless_in_app_deletes_are_on(world, monkeypatch, tmp_path):
    A, org, fake = world["A"], world["org"], world["fake"]
    store = _v2_store(tmp_path, org, world["near"][0])
    before = dict(store.obj)
    monkeypatch.setattr(A, "_BK_OK", True)
    monkeypatch.setattr(A, "_R2BackupStore", lambda: (_ for _ in ()).throw(AssertionError("must not open the backup bucket")))
    assert A._org_backups_erase_due(now=DAY30) == 0
    t = _tomb(A, org)
    assert t["backups_state"] == "external" and t["backups_erased_at"] is None
    assert "in_app_deletes_off" in t["backups_detail"]
    assert store.obj == before and fake.all_keys() == world["others"]     # weekday copies are erased all the same
    assert _listed(A, org, DAY30)[0]["backups_state"] == "external"       # the owner sees the app could not finish
    n = len(fake.calls)
    assert A._org_backups_erase_due(now=DAY30 + timedelta(hours=1)) == 0 and len(fake.calls) == n

    # in-app deletes switched on for the backup bucket: the next pass finishes the job
    monkeypatch.setattr(A, "BACKUP_PRUNE_IN_APP", True)
    monkeypatch.setattr(A, "_R2BackupStore", lambda: store)
    store.fail_delete = 1
    assert A._org_backups_erase_due(now=DAY30 + timedelta(hours=2)) == 0
    assert _tomb(A, org)["backups_state"] == "failed"
    assert A._org_backups_erase_due(now=DAY30 + timedelta(hours=3)) == 1
    assert _tomb(A, org)["backups_state"] == "erased"
    assert not [k for k in store.obj if k.split("/")[2] == org]
    other = world["near"][0]
    for run in ps_backup.list_runs(store):
        assert ps_backup.verify_run(store, run)[0]                         # every run still verifies
        assert "db-backups/%s/%s/shipments.db" % (run, other) in store.obj
        assert "db-backups/%s/platform.db" % run in store.obj
        rep = ps_backup.restore_run(store, run, str(tmp_path / ("restore_" + run)))
        assert rep["ok"] and sorted(f["name"] for f in rep["files"]) == sorted(["platform.db", other + "/shipments.db"])


def test_erase_org_copies_matches_the_whole_segment_only(tmp_path):
    store = _v2_store(tmp_path, "ab", "abc")
    store.obj["db-backups/20251231T180000Z/x/ab/shipments.db"] = b"nested look-alike"
    store.obj["other/20251231T180000Z/ab/shipments.db"] = b"other prefix"
    for bad in ("", None, "a/b", "..", ".", "manifest.json"):
        with pytest.raises(ValueError):
            ps_backup.erase_org_copies(store, bad)
    before = dict(store.obj)
    assert ps_backup.erase_org_copies(store, "ab", deadline=0) == (0, False) and store.obj == before
    n, done = ps_backup.erase_org_copies(store, "ab")
    assert (n, done) == (4, True)
    gone = set(before) - set(store.obj)
    assert gone == {"db-backups/%s/ab/%s" % (r, f) for r in ("20251220T060000Z", "20251231T180000Z")
                    for f in ("shipments.db", "packing_log.csv")}
    man = json.loads(store.obj["db-backups/20251220T060000Z/manifest.json"].decode())
    assert [e["name"] for e in man["files"]] == ["platform.db", "abc/shipments.db"] and man["file_count"] == 2
    assert man["total_bytes"] == sum(e["bytes"] for e in man["files"])
    assert ps_backup.erase_org_copies(store, "ab") == (0, True)            # repeat: nothing left, nothing changed
