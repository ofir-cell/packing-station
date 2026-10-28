"""Cycle-7 Path B: backup-only Safe Mode exception — fail-closed permission + store.
(The live Safe-Mode isolation proof runs app import under APP_ENV=staging in a subprocess
in test_cycle7_safe_mode_isolation.py.)"""
import uuid, pytest


def _reset_env(monkeypatch, **kv):
    for k in ("R2_BACKUP_BUCKET","R2_BACKUP_ACCESS_KEY_ID","R2_BACKUP_SECRET_ACCESS_KEY","R2_BACKUP_ENDPOINT"):
        monkeypatch.delenv(k, raising=False)
    for k, v in kv.items():
        monkeypatch.setenv(k, v)


def _good_env(monkeypatch, appmod):
    _reset_env(monkeypatch,
               R2_BACKUP_BUCKET="packing-station-staging-backups",
               R2_BACKUP_ACCESS_KEY_ID="ded-ak", R2_BACKUP_SECRET_ACCESS_KEY="ded-sk",
               R2_BACKUP_ENDPOINT="https://acct.r2.cloudflarestorage.com")
    monkeypatch.setattr(appmod, "BACKUP_V2_ENABLED", True, raising=False)
    # operational identifiers distinct from the backup ones
    monkeypatch.setattr(appmod, "R2_BUCKET", "packing-station", raising=False)
    monkeypatch.setattr(appmod, "R2_HR_BUCKET", "packing-station-hr", raising=False)
    monkeypatch.setattr(appmod, "R2_ACCESS_KEY_ID", "op-ak", raising=False)
    monkeypatch.setattr(appmod, "R2_SECRET_ACCESS_KEY", "op-sk", raising=False)


def test_permit_all_good(appmod, monkeypatch):
    _good_env(monkeypatch, appmod)
    ok, reason = appmod._backup_v2_permitted()
    assert ok is True and reason == "ok"


def test_permit_fail_closed_disabled(appmod, monkeypatch):
    _good_env(monkeypatch, appmod)
    monkeypatch.setattr(appmod, "BACKUP_V2_ENABLED", False, raising=False)
    ok, reason = appmod._backup_v2_permitted()
    assert ok is False and "disabled" in reason


def test_permit_fail_closed_no_bucket(appmod, monkeypatch):
    _good_env(monkeypatch, appmod)
    monkeypatch.delenv("R2_BACKUP_BUCKET", raising=False)
    ok, reason = appmod._backup_v2_permitted()
    assert ok is False and "R2_BACKUP_BUCKET" in reason


def test_permit_fail_closed_bucket_is_operational(appmod, monkeypatch):
    _good_env(monkeypatch, appmod)
    monkeypatch.setenv("R2_BACKUP_BUCKET", "packing-station")  # == operational
    ok, reason = appmod._backup_v2_permitted()
    assert ok is False and "differ from operational" in reason


def test_permit_fail_closed_missing_creds(appmod, monkeypatch):
    _good_env(monkeypatch, appmod)
    monkeypatch.delenv("R2_BACKUP_SECRET_ACCESS_KEY", raising=False)
    ok, reason = appmod._backup_v2_permitted()
    assert ok is False and "dedicated" in reason


def test_permit_fail_closed_creds_equal_operational(appmod, monkeypatch):
    _good_env(monkeypatch, appmod)
    monkeypatch.setenv("R2_BACKUP_ACCESS_KEY_ID", "op-ak")  # == operational key
    ok, reason = appmod._backup_v2_permitted()
    assert ok is False and "separate from operational" in reason


def test_store_fail_closed_without_dedicated_creds(appmod, monkeypatch):
    _reset_env(monkeypatch)  # no R2_BACKUP_* at all
    monkeypatch.setattr(appmod, "R2_BACKUP_BUCKET", None, raising=False)
    with pytest.raises(RuntimeError):
        appmod._R2BackupStore()
