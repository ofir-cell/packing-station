"""QA gate for SEC-6i (backup copies of a deleted company erased after 30 days).

This code deletes BACKUPS. Every test here tries to make it delete (or stop writing) a
backup that belongs to a company that still exists, or to erase too early.

Temp DATA_DIR from conftest; the main bucket and the dedicated backup bucket are
in-memory fakes; the clock is injected. ``xfail(strict=True)`` = a defect found by this
review (asserts the SAFE behaviour).
"""
import io
import json
import os
import threading
import uuid
from datetime import datetime, timedelta

import pytest

import ps_backup
import test_sec6_qa_gate as G

MAIN, HR = G.MAIN, G.HR
KEEP = 30


class FakeR2(G.FakeR2):
    fail_for = None                      # every delete of a key containing this text raises

    def delete_objects(self, Bucket, Delete):
        if self.fail_for and any(self.fail_for in o["Key"] for o in Delete["Objects"]):
            self.calls.append(("delete_objects_failed", Bucket, tuple(o["Key"] for o in Delete["Objects"])))
            raise TimeoutError("simulated")
        return super().delete_objects(Bucket, Delete)

    def put_object(self, Bucket, Key, Body=b"", **kw):
        self.calls.append(("put", Bucket, Key)); self.objects[Bucket].add(Key)
        return {}

    def reset(self):
        self.calls.clear(); self._n.clear(); self.kill_on = None


class FakeStore:
    """The dedicated backup bucket (ps_backup store interface)."""
    def __init__(self):
        self.o = {}; self.deleted = []; self.puts = []; self.fail_delete_for = None
    def put_fileobj(self, key, fh): self.o[key] = fh.read()
    def put_bytes(self, key, data): self.o[key] = data; self.puts.append(key)
    def get_bytes(self, key): return self.o[key]
    def size(self, key): return len(self.o[key])
    def list_keys(self, prefix): return sorted(k for k in self.o if k.startswith(prefix))
    def delete(self, key):
        if self.fail_delete_for and self.fail_delete_for in key: raise TimeoutError("simulated")
        self.deleted.append(key); del self.o[key]


def _now():
    return datetime.utcnow().replace(microsecond=0)


def _set_requested(A, org, value):
    c = A.pdb()
    if not c.execute("SELECT 1 FROM org_tombstones WHERE org_id=?", (org,)).fetchone():
        c.execute("INSERT INTO org_tombstones(org_id,state) VALUES(?, 'deleted')", (org,))
    c.execute("UPDATE org_tombstones SET requested_at=? WHERE org_id=?", (value, org))
    c.commit(); c.close()


def _ago(now, **kw):
    return (now - timedelta(**kw)).strftime("%Y-%m-%d %H:%M:%S")


def _tomb(A, org):
    c = A.pdb(); r = c.execute("SELECT * FROM org_tombstones WHERE org_id=?", (org,)).fetchone(); c.close()
    return dict(r) if r else None


def _local_bk(A, org, dow="mon"):
    return os.path.join(A.DATA_DIR, "backups", dow, org)


def _main_bk(org):
    return G._backup_keys(org)


def _v2_run(A, store, orgs, when):
    """A real ps_backup run (real key layout, real manifest) holding the platform files
    and the given orgs' databases."""
    t = [("platform.db", A.PLATFORM_DB), ("users.json", A.USERS_FILE), ("stations.json", A.STATIONS_FILE)]
    for o in orgs:
        t += [(o + "/shipments.db", A.shipments_db_path(o)), (o + "/giveaways.db", A.giveaway_db_path(o)),
              (o + "/onboarding.json", A.org_path(o, "onboarding.json"))]
    return ps_backup.run_backup(t, store, now=when)["run_id"]


@pytest.fixture
def env(appmod, monkeypatch):
    A = appmod
    fake = FakeR2()
    for b, k in G.SHARED_KEYS: fake.objects[b].add(k)
    store = FakeStore()
    monkeypatch.setattr(A, "r2", fake); monkeypatch.setattr(A, "R2_BUCKET", MAIN); monkeypatch.setattr(A, "R2_HR_BUCKET", HR)
    monkeypatch.setattr(A, "_R2BackupStore", lambda: store)
    monkeypatch.setattr(A, "_BK_OK", True); monkeypatch.setattr(A, "BACKUP_PRUNE_IN_APP", True)
    # These tests age deletions against the real clock ("31 days ago"), which until
    # 2026-12 is before the production floor (2026-11-01). The floor is moved for the
    # test only; 1970 / 0001 / numeric values stay below it. (Added by the programmer
    # with the QA-SEC6I-1 fix; the production value is asserted in test_sec6i_backup_retention.)
    fake.prod_floor = A.ORG_BACKUP_DELETED_AT_FLOOR      # qa: the value production runs with, kept for the floor tests
    monkeypatch.setattr(A, "ORG_BACKUP_DELETED_AT_FLOOR", datetime(2020, 1, 1))
    G._login(A, "qa-no-such-user")
    # deletions left behind by earlier tests in this session are not this test's business
    c = A.pdb(); c.execute("UPDATE org_tombstones SET backups_state='erased' WHERE backups_state IS NULL OR backups_state<>'erased'")
    c.commit(); c.close()
    return A, fake, store


def _deleted_org(A, fake, store, now, age_days=31, name=None, runs=2):
    """A company with backups in all three places, then deleted `age_days` ago."""
    org = name or ("qb" + uuid.uuid4().hex[:6])
    G._mk_org(A, org, fake)
    for i in range(runs):
        _v2_run(A, store, [org], now - timedelta(days=40 + i, seconds=hash(org) % 3000))
    assert A._delete_org_data(org)["ok"]
    _set_requested(A, org, _ago(now, days=age_days))
    fake.reset(); store.puts.clear(); store.deleted.clear()
    return org


def _v2_keys(store, org):
    return {k for k in store.o if k.split("/")[2:3] == [org]}


def _has_backups(A, fake, store, org):
    return (_main_bk(org) <= fake.all_keys(), os.path.exists(os.path.join(_local_bk(A, org), "shipments.db")),
            len(_v2_keys(store, org)) > 0)


# ═════════════ 1. only after 30 full days; a bad timestamp is never "very old" ═════════════

def test_29_days_23_hours_is_untouched_and_30_days_is_erased(env):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    _set_requested(A, org, _ago(now, days=KEEP, seconds=-1))             # 29 d 23 h 59 m 59 s
    assert A._org_backups_erase_due(now=now) == 0
    assert _has_backups(A, fake, store, org) == (True, True, True) and fake.mutating_calls() == [] and store.deleted == []
    _set_requested(A, org, _ago(now, days=KEEP - 1, hours=23))
    assert A._org_backups_erase_due(now=now) == 0 and _has_backups(A, fake, store, org) == (True, True, True)
    _set_requested(A, org, _ago(now, days=KEEP))                          # exactly 30 days
    assert A._org_backups_erase_due(now=now) == 1
    assert _has_backups(A, fake, store, org) == (False, False, False)
    assert _tomb(A, org)["backups_state"] == "erased"


_BAD_TS = [None, "", " ", "garbage", "not-a-date", "now", "0000-00-00 00:00:00", "2026-13-45 99:99:99",
           1731300000, "1731300000", -1, "31/12/2020", "2020-01-01 00:00:00 garbage", b"\x00\x01"]
_FUTURE = ["+1h", "+1d", "+400d"]
# Values SQLite's datetime() reads as a Julian day number or a real-but-absurd date:
_JULIAN = [0, "0", 1, "1", "2026", 2026, 2460000.5, "1970-01-01 00:00:00", "0001-01-01 00:00:00"]


@pytest.mark.parametrize("ts", _BAD_TS + _FUTURE, ids=lambda v: repr(v)[:22])
def test_missing_malformed_or_future_deletion_time_never_erases(env, ts):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    if isinstance(ts, str) and ts.startswith("+"):
        ts = _ago(now, days=-int(ts[1:-1])) if ts.endswith("d") else _ago(now, hours=-1)
    _set_requested(A, org, ts)
    assert A._org_backups_erase_due(now=now) == 0
    assert A._org_backups_erase(org, A.time.time() + 30, now) is None
    assert _has_backups(A, fake, store, org) == (True, True, True)
    assert fake.calls == [] and store.deleted == [] and store.puts == []


@pytest.mark.parametrize("ts", _JULIAN, ids=lambda v: repr(v)[:22])
def test_zero_epoch_or_numeric_deletion_time_is_not_treated_as_very_old(env, ts):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    _set_requested(A, org, ts)
    A._org_backups_erase_due(now=now)
    assert _has_backups(A, fake, store, org) == (True, True, True)


def test_clock_jumping_backwards_never_erases(env):
    """Server clock wrong by a year in the past: nothing is due."""
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now, age_days=31)
    assert A._org_backups_erase_due(now=now - timedelta(days=365)) == 0
    assert _has_backups(A, fake, store, org) == (True, True, True)


# ═════════════ 2. nobody else's backups, in any of the three places ═════════════

def test_only_the_deleted_orgs_backups_go_everything_else_is_byte_identical(env):
    A, fake, store = env
    now = _now()
    base = "qb" + uuid.uuid4().hex[:6]
    live = [base + "c", base + "-2", "x" + base, base + "2", base.upper() + "X"]
    recent = base.upper()                                    # deleted 10 days ago: not due
    stray = base + "-2"                                      # LIVE org carrying an old tombstone row
    internal = "qi" + uuid.uuid4().hex[:6]
    for o in [base, recent, internal] + live:
        G._mk_org(A, o, fake)
    c = A.pdb(); c.execute("UPDATE organizations SET internal=1 WHERE org_id=?", (internal,)); c.commit(); c.close()
    everyone = [A.DEFAULT_ORG, base, recent, internal] + live
    fake.objects[MAIN] |= {"backups/mon/%s/shipments.db" % A.DEFAULT_ORG, "backups/mon/mon/shipments.db",
                           "backups/mon/videos/shipments.db", "backups/mon//shipments.db"}
    os.makedirs(_local_bk(A, A.DEFAULT_ORG), exist_ok=True)
    open(os.path.join(_local_bk(A, A.DEFAULT_ORG), "shipments.db"), "wb").write(b"founding backup")
    runs = [_v2_run(A, store, everyone, now - timedelta(days=45 - i, minutes=i)) for i in range(3)]
    assert A._delete_org_data(base)["ok"] and A._delete_org_data(recent)["ok"]
    old = _ago(now, days=400)
    _set_requested(A, base, _ago(now, days=31)); _set_requested(A, recent, _ago(now, days=10))
    planted = [stray, internal, A.DEFAULT_ORG, A.PLATFORM_ORG, "", "/", "..", "a/b", "../" + live[0], "mon", "videos",
               "backups", "Videos", "MON", live[0] + "\n", live[0] + "/", "db-backups", "manifest.json", "platform.db"]
    for p in planted: _set_requested(A, p, old)
    try:
        own_main = _main_bk(base); own_v2 = _v2_keys(store, base)
        assert len(own_v2) == 9                              # 3 files x 3 runs
        main_before = fake.all_keys() - own_main
        v2_before = {k: v for k, v in store.o.items() if k not in own_v2 and not k.endswith("manifest.json")}
        files_before = G._files_snapshot(A, "\0none", -1)
        fake.reset(); store.puts.clear(); store.deleted.clear()

        # 2 = base, plus the planted id "db-backups": a plain id with an old tombstone and no
        # company row, so it is processed too - and has nothing anywhere to erase
        assert A._org_backups_erase_due(now=now) == 2

        # main bucket: only base's two objects are gone; only exact-segment prefixes were listed
        assert fake.all_keys() == main_before
        assert {p for n, b, p in fake.calls if n == "list"} == {
            "backups/%s/%s/" % (d, o) for d in A._BACKUP_DOWS for o in (base, "db-backups")}
        for n, b, what in fake.mutating_calls():
            assert b == MAIN and set(what) <= {k for _, k in own_main}
        # dedicated bucket: exactly base's objects, in every run; nothing else changed
        assert set(store.deleted) == own_v2
        assert {k: v for k, v in store.o.items() if not k.endswith("manifest.json")} == v2_before
        assert set(store.puts) == {"db-backups/%s/manifest.json" % r for r in runs}
        for r in runs:
            ok, detail = ps_backup.verify_run(store, r)
            assert ok, detail
            man = json.loads(store.o["db-backups/%s/manifest.json" % r])
            names = {e["name"] for e in man["files"]}
            assert {"platform.db", "users.json", "stations.json"} <= names
            assert not [n for n in names if n.startswith(base + "/")]
            for o in everyone:
                if o != base:
                    assert o + "/shipments.db" in names and "db-backups/%s/%s/shipments.db" % (r, o) in store.o, o
            assert man["file_count"] == len(man["files"]) and man["total_bytes"] == sum(e["bytes"] for e in man["files"])
        # volume: only DATA_DIR/backups/mon/<base>/ is gone
        files_after = G._files_snapshot(A, "\0none", -1)
        gone = set(files_before) - set(files_after)
        assert gone == {os.path.join("backups", "mon", base, "shipments.db")}
        assert {k: v for k, v in files_before.items() if k not in gone} == files_after
        for o in everyone:
            if o != base:
                assert _tomb(A, o) is None or _tomb(A, o)["backups_state"] is None, o
    finally:
        c = A.pdb()
        for p in planted: c.execute("DELETE FROM org_tombstones WHERE org_id=?", (p,))
        c.commit(); c.close()


@pytest.mark.parametrize("bad", ["", None, "/", "..", ".", "a/b", "ab/", "/ab", "manifest.json", "platform.db", "a b",
                                 "%", "ab\n", "*", 0, [], "db-backups"])
def test_direct_calls_with_a_malformed_id_touch_nothing(env, bad):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    before = dict(store.o); keys = fake.all_keys()
    if bad != "db-backups":                                # that one is a plain id (it just has no tombstone)
        assert A._org_backup_prefixes(bad) == []
    assert A._org_backups_erase(bad, A.time.time() + 30, now) is None
    if not (isinstance(bad, str) and bad and "/" not in bad and bad not in (".", "..", "manifest.json")):
        with pytest.raises(ValueError):
            ps_backup.erase_org_copies(store, bad)
    else:
        assert ps_backup.erase_org_copies(store, bad) == (0, True)       # a plain segment that matches no company
    assert store.o == before and store.deleted == [] and store.puts == [] and fake.all_keys() == keys and fake.calls == []


def test_dedicated_bucket_matches_the_org_segment_exactly_in_every_run(env):
    """db-backups/<run>/<org>/...: a run id, a file name or a deeper folder equal to the
    org id must not match; neither must a longer or differently-cased org."""
    A, fake, store = env
    org = "qd" + uuid.uuid4().hex[:6]
    keep = {
        "db-backups/20260101T000000Z/%sc/shipments.db" % org: b"1", "db-backups/20260101T000000Z/x%s/shipments.db" % org: b"2",
        "db-backups/20260101T000000Z/%s/shipments.db" % org.upper(): b"3", "db-backups/20260101T000000Z/%s" % org: b"4",
        "db-backups/%s/other/shipments.db" % org: b"5", "db-backups/20260101T000000Z/other/%s/file" % org: b"6",
        "db-backups/20260101T000000Z/platform.db": b"7", "%s/20260101T000000Z/%s/file" % (org, org): b"8",
        "db-backups2/20260101T000000Z/%s/shipments.db" % org: b"9", "db-backups/20260101T000000Z/%s-2/a/b" % org: b"10",
    }
    mine = {"db-backups/20260101T000000Z/%s/shipments.db" % org: b"a", "db-backups/20260102T000000Z/%s/sub/dir/f" % org: b"b",
            "db-backups/no-manifest-run/%s/giveaways.db" % org: b"c"}
    store.o.update(keep); store.o.update(mine)
    n, done = ps_backup.erase_org_copies(store, org)
    assert (n, done) == (3, True) and store.o == keep and set(store.deleted) == set(mine)


# ═════════════ 3. the BACKUP_PRUNE_IN_APP switch ═════════════

def test_with_in_app_deletes_off_the_dedicated_bucket_is_never_written_or_deleted(env, monkeypatch):
    A, fake, store = env
    now = _now()
    monkeypatch.setattr(A, "BACKUP_PRUNE_IN_APP", False)
    org = _deleted_org(A, fake, store, now)
    before = dict(store.o)
    for _ in range(3):
        assert A._org_backups_erase_due(now=now) == 0
    assert store.o == before and store.deleted == [] and store.puts == []
    t = _tomb(A, org)
    assert t["backups_state"] == "external" and t["backups_attempts"] == 1          # not retried every hour
    assert _has_backups(A, fake, store, org) == (False, False, True)
    listed = [d for d in A._org_unfinished_deletions(now) if d["org_id"] == org]
    assert listed and listed[0]["backups_state"] == "external" and listed[0]["backups_overdue"] == 1
    monkeypatch.setattr(A, "BACKUP_PRUNE_IN_APP", True)                              # switched on later: finished
    assert A._org_backups_erase_due(now=now) == 1 and _v2_keys(store, org) == set()


def test_without_backup_v2_the_dedicated_bucket_client_is_never_built(env, monkeypatch):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    monkeypatch.setattr(A, "_BK_OK", False)
    def never(): raise AssertionError("backup bucket client built while Backup V2 is off")
    monkeypatch.setattr(A, "_R2BackupStore", never)
    assert A._org_backups_erase_due(now=now) == 1 and _tomb(A, org)["backups_state"] == "erased"


@pytest.mark.parametrize("flag", [False, True])
def test_live_backup_run_and_its_retention_are_what_main_does(env, monkeypatch, flag):
    """The backup job itself: flag off -> nothing is ever deleted; flag on -> exactly the
    runs ps_backup.select_retained (8 / 7 / 6, unchanged from main) does not keep."""
    A, fake, store = env
    monkeypatch.setattr(A, "BACKUP_PRUNE_IN_APP", flag)
    live = "ql" + uuid.uuid4().hex[:6]; G._mk_org(A, live)
    monkeypatch.setattr(A, "list_org_ids", lambda: [A.DEFAULT_ORG, live])
    now = _now()
    old_runs = [_v2_run(A, store, [A.DEFAULT_ORG, live], now - timedelta(days=d, minutes=d)) for d in range(1, 80, 3)]
    store.puts.clear(); store.deleted.clear()
    man = A._backup_v2_run_once()
    assert man and A._backup_status["last_ok"] is True
    names = {e["name"] for e in man["files"]}
    assert {"platform.db", "users.json", live + "/shipments.db", A.DEFAULT_ORG + "/shipments.db"} <= names
    all_runs = old_runs + [man["run_id"]]
    left = set(ps_backup.list_runs(store))
    if not flag:
        assert store.deleted == [] and left == set(all_runs)
    else:
        expect = ps_backup.select_retained(all_runs, datetime.utcnow(), 8, 7, 6) | {max(all_runs)}
        assert left == expect and 0 < len(left) < len(all_runs)


# ═════════════ 4. which companies are backed up ═════════════

def test_backup_org_list_equals_the_live_org_list(env, monkeypatch):
    A, fake, store = env
    now = _now()
    odd = ["qo" + uuid.uuid4().hex[:6] + s for s in ("", "-2", "_x")] + ["QO" + uuid.uuid4().hex[:6].upper()]
    for o in odd: G._mk_org(A, o)
    dead = _deleted_org(A, fake, store, now, age_days=1)
    live = A.list_org_ids()
    assert A.DEFAULT_ORG in live and set(odd) <= set(live) and dead not in live
    assert A._backup_org_ids() == live                                    # same companies, same order
    def boom(): raise A.sqlite3.OperationalError("locked")
    real = A.pdb
    monkeypatch.setattr(A, "list_org_ids", lambda: live)
    monkeypatch.setattr(A, "pdb", boom)                                   # tombstones unreadable: skip nobody
    assert A._backup_org_ids() == live
    monkeypatch.setattr(A, "pdb", real)
    # and the job's file list is the pre-change formula over the live orgs
    want = ["platform.db", "users.json", "stations.json"]
    for o in live:
        want += [o + "/shipments.db", o + "/giveaways.db"] + [o + "/" + f for f in
                 ("packing_log.csv", "documents.json", "announcements.json", "onboarding.json")]
    assert [n for n, _ in A._backup_targets()] == want


def test_legacy_daily_backup_writes_every_live_org(env, monkeypatch):
    A, fake, store = env
    live = "ql" + uuid.uuid4().hex[:6]; G._mk_org(A, live)
    monkeypatch.setattr(A, "list_org_ids", lambda: [A.DEFAULT_ORG, live])
    fake.reset()
    A._backup_all()
    puts = [k for n, b, k in fake.calls if n == "put"]
    dow = datetime.now().strftime("%a").lower()
    assert set(puts) == {"backups/%s/%s" % (dow, n) for n in ("platform.db", "users.json", live + "/shipments.db",
                         live + "/giveaways.db", A.DEFAULT_ORG + "/shipments.db", A.DEFAULT_ORG + "/giveaways.db")}


def test_live_org_with_a_stray_tombstone_is_still_backed_up(env):
    A, fake, store = env
    live = "ql" + uuid.uuid4().hex[:6]; G._mk_org(A, live)
    _set_requested(A, live, _ago(_now(), days=5))
    try:
        assert live in A.list_org_ids()
        assert live in A._backup_org_ids()
    finally:
        c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", (live,)); c.commit(); c.close()


# ═════════════ 5. the hourly loop ═════════════

def test_several_workers_at_once_erase_once_and_nothing_else(env):
    A, fake, store = env
    now = _now()
    a = _deleted_org(A, fake, store, now); b = _deleted_org(A, fake, store, now)
    live = "ql" + uuid.uuid4().hex[:6]; G._mk_org(A, live, fake); _v2_run(A, store, [live], now - timedelta(days=50))
    fake.reset(); store.puts.clear(); store.deleted.clear()
    keep_main = fake.all_keys() - _main_bk(a) - _main_bk(b)
    keep_v2 = {k for k in store.o if k not in _v2_keys(store, a) | _v2_keys(store, b)}
    errs = []
    def run():
        try: A._org_backups_erase_due(now=now)
        except BaseException as e: errs.append(repr(e))
    ts = [threading.Thread(target=run) for _ in range(5)]
    for t in ts: t.start()
    for t in ts: t.join(60)
    assert not errs, errs
    assert fake.all_keys() == keep_main and set(store.o) == keep_v2
    for o in (a, b):
        t = _tomb(A, o); assert t["backups_state"] == "erased" and t["backups_attempts"] == 1
    assert len(store.deleted) == len(set(store.deleted))                  # no key deleted twice
    assert ps_backup.verify_run(store, ps_backup.list_runs(store)[0])[0]


def test_a_failing_company_does_not_block_the_others_and_ends_stuck_and_listed(env, monkeypatch):
    A, fake, store = env
    now = _now()
    monkeypatch.setattr(A, "ORG_DELETE_MAX_ATTEMPTS", 3)
    bad = _deleted_org(A, fake, store, now, age_days=60)                  # older: tried first
    good = _deleted_org(A, fake, store, now, age_days=31)
    fake.fail_for = "/%s/" % bad
    assert A._org_backups_erase_due(now=now) == 1
    assert _tomb(A, good)["backups_state"] == "erased" and _tomb(A, bad)["backups_state"] == "failed"
    assert _main_bk(bad) <= fake.all_keys()
    good2 = _deleted_org(A, fake, store, now, age_days=31)
    assert A._org_backups_erase_due(now=now) == 1 and _tomb(A, good2)["backups_state"] == "erased"
    A._org_backups_erase_due(now=now)
    t = _tomb(A, bad)
    assert t["backups_state"] == "stuck" and t["backups_attempts"] == 3
    n = len(fake.calls)
    assert A._org_backups_erase_due(now=now) == 0 and len(fake.calls) == n          # no more automatic retries
    listed = [d for d in A._org_unfinished_deletions(now) if d["org_id"] == bad]
    assert listed and listed[0]["backups_state"] == "stuck" and listed[0]["backups_overdue"] == 1
    assert not [d for d in A._org_unfinished_deletions(now) if d["org_id"] in (good, good2)]


def test_killed_mid_erasure_then_resumed_completes(env):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    others_main = fake.all_keys() - _main_bk(org)
    fake.kill_on = ("delete_objects", 1)
    with pytest.raises(G.Killed):
        A._org_backups_erase(org, A.time.time() + 30, now)
    assert _tomb(A, org)["backups_state"] is None
    store.fail_delete_for = "/%s/giveaways.db" % org                      # next pass: dedicated bucket fails half-way
    assert A._org_backups_erase_due(now=now) == 0 and _tomb(A, org)["backups_state"] == "failed"
    for r in ps_backup.list_runs(store):
        assert ps_backup.verify_run(store, r)[0]                          # runs still verify while half-erased
    store.fail_delete_for = None
    assert A._org_backups_erase_due(now=now) == 1
    assert _has_backups(A, fake, store, org) == (False, False, False) and fake.all_keys() == others_main


def test_time_budget_bounds_a_pass(env):
    A, fake, store = env
    now = _now()
    orgs = [_deleted_org(A, fake, store, now, runs=1) for _ in range(3)]
    assert A._org_backups_erase_due(now=now, budget_sec=-1) == 0
    assert fake.calls == [] and store.deleted == []
    for o in orgs: assert _tomb(A, o)["backups_state"] is None
    assert A._org_backups_erase_due(now=now) == 3


def test_erased_tombstone_still_blocks_reuse_and_is_not_listed(env):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now, name="qr" + uuid.uuid4().hex[:6])
    assert A._org_backups_erase_due(now=now) == 1
    assert A.org_id_tombstoned(org)
    assert not [d for d in A._org_unfinished_deletions(now) if d["org_id"] == org]
    ok, err = getattr(A._create_tenant, "__wrapped__", A._create_tenant)(org, "Again Co", "adm" + uuid.uuid4().hex[:6], actor="t")
    assert ok is False and "deleted company" in err


# ═════════════ 6. local volume ═════════════

def test_local_erasure_never_follows_a_symlink(env, tmp_path):
    A, fake, store = env
    now = _now()
    outside = tmp_path / "outside"; (outside / "inner").mkdir(parents=True)
    (outside / "keep.txt").write_text("keep"); (outside / "inner" / "keep.txt").write_text("keep")
    org = _deleted_org(A, fake, store, now)
    os.symlink(str(outside / "inner"), os.path.join(_local_bk(A, org), "link_inside"))   # link inside the folder
    tue = os.path.join(A.DATA_DIR, "backups", "tue"); os.makedirs(tue, exist_ok=True)
    os.symlink(str(outside), os.path.join(tue, org))                                     # the folder itself is a link
    try:
        assert A._org_backups_erase_due(now=now) == 0
        assert (outside / "keep.txt").read_text() == "keep" and (outside / "inner" / "keep.txt").read_text() == "keep"
        t = _tomb(A, org)
        assert t["backups_state"] == "failed" and "unexpected_entry" in t["backups_detail"]
        assert not os.path.exists(_local_bk(A, org))                                     # the real folder did go
    finally:
        os.unlink(os.path.join(tue, org))
    assert A._org_backups_erase_due(now=now) == 1


def test_local_erasure_removes_only_the_exact_org_folders(env, monkeypatch):
    import shutil
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    for o in (org + "c", org.upper(), "x" + org):
        os.makedirs(_local_bk(A, o, "wed"), exist_ok=True); open(os.path.join(_local_bk(A, o, "wed"), "f.db"), "wb").close()
    os.makedirs(_local_bk(A, org, "wed"), exist_ok=True)
    seen = []
    real_rm, real_remove, real_unlink = shutil.rmtree, os.remove, os.unlink
    monkeypatch.setattr(shutil, "rmtree", lambda p, *a, **k: (seen.append(os.path.abspath(p)), real_rm(p, *a, **k))[1])
    monkeypatch.setattr(os, "remove", lambda p, *a, **k: (seen.append(os.path.abspath(p)), real_remove(p, *a, **k))[1])
    A._org_backups_erase_due(now=now)
    monkeypatch.undo()
    root = os.path.abspath(os.path.join(A.DATA_DIR, "backups"))
    assert set(seen) == {os.path.join(root, "mon", org), os.path.join(root, "wed", org)}
    for o in (org + "c", org.upper(), "x" + org):
        assert os.path.exists(os.path.join(_local_bk(A, o, "wed"), "f.db"))


def test_weekday_folder_that_is_a_symlink_is_not_followed(env, tmp_path):
    A, fake, store = env
    now = _now()
    org = _deleted_org(A, fake, store, now)
    outside = tmp_path / "elsewhere"; (outside / org).mkdir(parents=True); (outside / org / "keep.txt").write_text("keep")
    thu = os.path.join(A.DATA_DIR, "backups", "thu")
    moved = None
    if os.path.lexists(thu):
        moved = thu + ".qa-aside"; os.rename(thu, moved)
    os.symlink(str(outside), thu)
    try:
        A._org_backups_erase_due(now=now)
        assert (outside / org / "keep.txt").exists()
    finally:
        os.unlink(thu)
        if moved: os.rename(moved, thu)


# ═════════════ re-review of 4d98279: the production floor and the accepted format ═════════════

def test_production_floor_refuses_any_deletion_time_before_november_2026(env, monkeypatch):
    """Runs with the floor production uses (the env fixture lowers it for the other
    tests). Fails if the floor is removed or moved earlier."""
    A, fake, store = env
    monkeypatch.setattr(A, "ORG_BACKUP_DELETED_AT_FLOOR", fake.prod_floor)
    far = datetime(2030, 1, 1)
    org = _deleted_org(A, fake, store, _now())
    for ts in ("2026-10-31 23:59:59", "2026-01-01 00:00:00", "2025-06-01 12:00:00", "2020-01-01 00:00:00", "1999-12-31 23:59:59"):
        _set_requested(A, org, ts)
        assert A._org_backup_deleted_at(ts, far) == (None, "deletion_time_before_floor")
        assert A._org_backups_erase_due(now=far) == 0
        assert _has_backups(A, fake, store, org) == (True, True, True) and fake.calls == [] and store.deleted == []
        listed = [d for d in A._org_unfinished_deletions(far) if d["org_id"] == org]
        assert listed and listed[0]["backups_reason"] == "deletion_time_before_floor"
    _set_requested(A, org, "2026-11-01 00:00:00")                         # the first acceptable instant
    assert A._org_backups_erase_due(now=datetime(2026, 11, 30, 23, 59, 59)) == 0
    assert A._org_backups_erase_due(now=datetime(2026, 12, 1, 0, 0, 0)) == 1


def test_time_written_by_a_real_deletion_is_accepted_under_the_production_floor(env, monkeypatch):
    """Round trip: the only writer of requested_at is the column default of the row
    _delete_org_data inserts. That exact value must be erasable 30 days later, or real
    deletions would never be erased."""
    A, fake, store = env
    monkeypatch.setattr(A, "ORG_BACKUP_DELETED_AT_FLOOR", fake.prod_floor)
    org = "qt" + uuid.uuid4().hex[:6]
    G._mk_org(A, org, fake); _v2_run(A, store, [org], _now() - timedelta(days=3))
    assert A._delete_org_data(org)["ok"]
    fake.reset(); store.puts.clear(); store.deleted.clear()
    written = _tomb(A, org)["requested_at"]
    real_now = datetime.utcnow()
    t, bad = A._org_backup_deleted_at(written, real_now)                  # accepted the very moment it is written
    assert bad is None and abs((real_now - t).total_seconds()) < 120, (written, bad)
    assert A._org_backups_erase_due() == 0                                 # the real clock: not due
    assert A._org_backups_erase_due(now=t + timedelta(days=30, seconds=-1)) == 0
    assert _has_backups(A, fake, store, org) == (True, True, True)
    assert not [d for d in A._org_unfinished_deletions(real_now) if d["org_id"] == org]
    assert A._org_backups_erase_due(now=t + timedelta(days=30)) == 1
    assert _has_backups(A, fake, store, org) == (False, False, False)


def test_requested_at_has_a_single_writer():
    src = open(os.path.join(G.REPO, "app.py"), encoding="utf-8").read()
    assert src.count("INSERT INTO org_tombstones") == 1
    assert "INSERT INTO org_tombstones(org_id,state,attempts) VALUES(?,'pending',1)" in src   # requested_at = column default
    assert "requested_at TEXT DEFAULT CURRENT_TIMESTAMP" in src
    assert "SET requested_at" not in src and "requested_at=" not in src.replace("t.requested_at", "")


@pytest.mark.parametrize("ts", ["2026-11-05T10:00:00", "2026-11-05 10:00:00Z", "2026-11-05T10:00:00Z", "2026-11-05 10:00:00.123",
                                "2026-11-05 10:00:00+00:00", "2026-11-05 10:00", "2026-11-05", "2026-11-05 10:00:00 ",
                                " 2026-11-05 10:00:00", "2026-11-05 10:00:00\n", "2026-02-30 10:00:00", "2026-11-05 24:00:00"])
def test_every_other_shape_of_timestamp_is_refused_and_listed(env, ts):
    """Only 'YYYY-MM-DD HH:MM:SS' (what the app writes) is trusted. Variants are never
    erased automatically; they show up for the platform owner instead."""
    A, fake, store = env
    far = datetime(2030, 1, 1)
    org = _deleted_org(A, fake, store, _now())
    _set_requested(A, org, ts)
    assert A._org_backup_deleted_at(ts, far) == (None, "deletion_time_malformed")
    assert A._org_backups_erase_due(now=far) == 0 and _has_backups(A, fake, store, org) == (True, True, True)
    listed = [d for d in A._org_unfinished_deletions(far) if d["org_id"] == org]
    assert listed and listed[0]["backups_reason"] == "deletion_time_malformed" and listed[0]["backups_overdue"] == 1


def test_live_org_with_an_old_tombstone_keeps_its_backups_and_stays_in_the_backup_list(env):
    A, fake, store = env
    now = _now()
    live = "ql" + uuid.uuid4().hex[:6]; G._mk_org(A, live, fake); _v2_run(A, store, [live], now - timedelta(days=50))
    _set_requested(A, live, _ago(now, days=400))
    fake.reset(); store.deleted.clear()
    try:
        assert A._org_backups_erase_due(now=now) == 0
        assert A._org_backups_erase(live, A.time.time() + 30, now) is None
        assert _has_backups(A, fake, store, live) == (True, True, True) and fake.calls == [] and store.deleted == []
        assert A._backup_org_ids() == A.list_org_ids() and live in A._backup_org_ids()
        assert live + "/shipments.db" in [n for n, _ in A._backup_targets()]
    finally:
        c = A.pdb(); c.execute("DELETE FROM org_tombstones WHERE org_id=?", (live,)); c.commit(); c.close()
