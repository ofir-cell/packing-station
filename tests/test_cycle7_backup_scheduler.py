"""Backup V2 scheduler marker logic — regression for the 'failed run suppresses retries
for 6h' incident. Covers: failed run (no marker advance), restart with a stale marker,
successful run, and 6h cadence. Plus the real run path end-to-end (fake store, no R2)."""
import sqlite3


# ---------- pure tick-decision helper ----------
def test_due_failed_run_not_suppressed_by_recent_marker(appmod):
    # a prior FAILED deploy touched the marker 1 min ago; this process hasn't succeeded yet
    now = 1_000_000.0
    assert appmod._backup_v2_due(now - 60, now, ran_ok_once=False, last_ok=False) is True
    assert appmod._backup_v2_due(now - 60, now, ran_ok_once=False, last_ok=None) is True


def test_due_restart_with_stale_marker_runs(appmod):
    # fresh process after a restart: ran_ok_once resets to False, status last_ok None,
    # marker only 5 min old -> must still run (first success not suppressed)
    now = 1_000_000.0
    assert appmod._backup_v2_due(now - 300, now, ran_ok_once=False, last_ok=None) is True


def test_due_no_repeat_after_success_within_6h(appmod):
    now = 1_000_000.0
    # succeeded this process, marker 1h old -> NOT due (no uncontrolled repeats)
    assert appmod._backup_v2_due(now - 3600, now, ran_ok_once=True, last_ok=True) is False


def test_due_6h_cadence_after_success(appmod):
    now = 1_000_000.0
    assert appmod._backup_v2_due(now - 6*3600, now, ran_ok_once=True, last_ok=True) is True
    assert appmod._backup_v2_due(now - (6*3600 - 1), now, ran_ok_once=True, last_ok=True) is False


# ---------- real run path (success + failure) ----------
class _FakeStore:
    def __init__(self, fail=False): self.obj={}; self.fail=fail
    def put_fileobj(self,k,fh):
        if self.fail: raise IOError("simulated R2 outage")
        self.obj[k]=fh.read()
    def put_bytes(self,k,d): self.obj[k]=d
    def get_bytes(self,k): return self.obj[k]
    def size(self,k): return len(self.obj[k])
    def delete(self,k): self.obj.pop(k,None)
    def list_keys(self,p): return [k for k in self.obj if k.startswith(p)]


def _seed(appmod, monkeypatch, tmp_path, store):
    db=tmp_path/"platform.db"; c=sqlite3.connect(str(db)); c.execute("CREATE TABLE t(x)"); c.execute("INSERT INTO t VALUES(1)"); c.commit(); c.close()
    monkeypatch.setattr(appmod,"_backup_targets",lambda:[("platform.db",str(db))])
    monkeypatch.setattr(appmod,"_R2BackupStore",lambda:store)
    monkeypatch.setenv("TMPDIR",str(tmp_path/"tmp"))


def test_run_success_sets_last_ok(appmod, monkeypatch, tmp_path):
    appmod._backup_status.update(last_ok=None)
    _seed(appmod, monkeypatch, tmp_path, _FakeStore(fail=False))
    man=appmod._backup_v2_run_once()
    assert man and man["file_count"]==1 and appmod._backup_status["last_ok"] is True


def test_run_failure_sets_last_ok_false_and_no_marker_advance(appmod, monkeypatch, tmp_path):
    appmod._backup_status.update(last_ok=None)
    _seed(appmod, monkeypatch, tmp_path, _FakeStore(fail=True))
    man=appmod._backup_v2_run_once()
    assert man is None and appmod._backup_status["last_ok"] is False
    # because last_ok is not True, the loop's marker advance is skipped and a retry stays due
    assert appmod._backup_v2_due(1_000_000.0-60, 1_000_000.0, ran_ok_once=False, last_ok=appmod._backup_status["last_ok"]) is True
