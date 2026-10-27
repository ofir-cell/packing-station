"""ps_backup tests — fully local: throwaway SQLite DBs + an in-memory fake store.
No real R2, no Production data, no threads."""
import os, io, sqlite3, json, hashlib, datetime, tempfile, pytest
import ps_backup


class FakeStore:
    """In-memory object store mirroring the R2 surface ps_backup needs."""
    def __init__(self): self.obj = {}
    def put_fileobj(self, key, fh): self.obj[key] = fh.read()
    def put_bytes(self, key, data): self.obj[key] = data
    def get_bytes(self, key): return self.obj[key]
    def size(self, key): return len(self.obj[key])
    def delete(self, key): self.obj.pop(key, None)
    def list_keys(self, prefix): return [k for k in self.obj if k.startswith(prefix)]


def _mkdb(path, rows):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    c.executemany("INSERT INTO t(v) VALUES(?)", [(r,) for r in rows])
    c.commit(); c.close()


@pytest.fixture
def workspace(tmp_path):
    data = tmp_path / "data"; data.mkdir()
    tmp = tmp_path / "tmp"; tmp.mkdir()
    db1 = data / "platform.db"; _mkdb(str(db1), ["a", "b", "c"])
    orgd = data / "orgs" / "5sec"; orgd.mkdir(parents=True)
    db2 = orgd / "shipments.db"; _mkdb(str(db2), ["x", "y"])
    js = data / "users.json"; js.write_text(json.dumps({"admin": {"role": "admin"}}))
    targets = [("platform.db", str(db1)), ("5sec/shipments.db", str(db2)), ("users.json", str(js))]
    return {"data": str(data), "tmp": str(tmp), "targets": targets}


def test_snapshot_is_consistent_and_valid(workspace, tmp_path):
    dst = str(tmp_path / "snap.db")
    ps_backup.snapshot_sqlite(workspace["targets"][0][1], dst)
    c = sqlite3.connect(dst)
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert c.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 3
    c.close()


def test_run_backup_manifest_and_sizes(workspace):
    store = FakeStore()
    man = ps_backup.run_backup(workspace["targets"], store, app_revision="c2b4088",
                               now=datetime.datetime(2026, 1, 15, 6, 0, 0), tmp_dir=workspace["tmp"])
    assert man["app_revision"] == "c2b4088" and man["file_count"] == 3
    # manifest + 3 files all live under the dedicated prefix, never operational media paths
    assert all(k.startswith("db-backups/20260115T060000Z/") for k in store.obj)
    for e in man["files"]:
        assert e["bytes"] == store.size(e["key"])
        assert len(e["sha256"]) == 64
    # no large temp left behind on the data volume
    assert not any(f.endswith(".db") for f in os.listdir(workspace["data"]) if f.startswith("tmp"))


def test_tmp_not_on_data_volume(workspace, monkeypatch):
    # run_backup must snapshot into tmp_dir, never into the data dir
    store = FakeStore()
    seen = {}
    real_mkstemp = tempfile.mkstemp
    def spy(*a, **k):
        seen["dir"] = k.get("dir"); return real_mkstemp(*a, **k)
    monkeypatch.setattr(ps_backup.tempfile, "mkstemp", spy)
    ps_backup.run_backup(workspace["targets"], store, tmp_dir=workspace["tmp"])
    assert seen["dir"] == workspace["tmp"] and not seen["dir"].startswith(workspace["data"])


def test_restore_roundtrip_verifies(workspace):
    store = FakeStore()
    man = ps_backup.run_backup(workspace["targets"], store, now=datetime.datetime(2026, 1, 15, 6, 0, 0),
                               tmp_dir=workspace["tmp"])
    dest = os.path.join(workspace["tmp"], "restore")
    rep = ps_backup.restore_run(store, man["run_id"], dest, data_dir_guard=workspace["data"])
    assert rep["ok"] and all(f["checksum_ok"] and f["integrity_ok"] for f in rep["files"])


def test_restore_refuses_production_dir(workspace):
    store = FakeStore()
    man = ps_backup.run_backup(workspace["targets"], store, now=datetime.datetime(2026, 1, 15, 6, 0, 0),
                               tmp_dir=workspace["tmp"])
    with pytest.raises(ValueError):
        ps_backup.restore_run(store, man["run_id"], workspace["data"], data_dir_guard=workspace["data"])


def test_restore_detects_corruption(workspace):
    store = FakeStore()
    man = ps_backup.run_backup(workspace["targets"], store, now=datetime.datetime(2026, 1, 15, 6, 0, 0),
                               tmp_dir=workspace["tmp"])
    # tamper one uploaded object
    key = man["files"][0]["key"]
    store.obj[key] = store.obj[key] + b"corrupt"
    with pytest.raises(ValueError):
        ps_backup.restore_run(store, man["run_id"], os.path.join(workspace["tmp"], "r2"),
                              data_dir_guard=workspace["data"])


def test_retention_tiers():
    # build run_ids across many days/weeks
    base = datetime.datetime(2026, 1, 1, 6, 0, 0)
    runs = []
    for day in range(40):
        for hour in (0, 6, 12, 18):
            runs.append((base + datetime.timedelta(days=day, hours=hour)).strftime("%Y%m%dT%H%M%SZ"))
    keep = ps_backup.select_retained(runs, now=None, keep_6h=8, keep_daily=7, keep_weekly=6)
    # most-recent 8 runs are kept
    assert set(sorted(runs)[-8:]).issubset(keep)
    # at least one run per retained week/day; kept set is far smaller than all runs
    assert len(keep) < len(runs)
    # nothing kept that isn't a real run
    assert keep.issubset(set(runs))


def test_retention_prune_deletes_old(workspace):
    store = FakeStore()
    base = datetime.datetime(2026, 1, 1, 6, 0, 0)
    for day in range(30):
        ps_backup.run_backup(workspace["targets"], store,
                             now=base + datetime.timedelta(days=day), tmp_dir=workspace["tmp"])
    kept, deleted = ps_backup.retention_prune(store, keep_6h=4, keep_daily=7, keep_weekly=4)
    assert deleted and kept
    # every deleted run's objects are gone; every kept run still has a manifest
    for r in kept:
        assert ("db-backups/%s/manifest.json" % r) in store.obj
    for r in deleted:
        assert not store.list_keys("db-backups/%s/" % r)
