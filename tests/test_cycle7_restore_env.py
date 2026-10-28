"""restore_backup.py must use the dedicated R2_BACKUP_* creds/bucket (never operational
R2_*) and fail clearly when any are missing. Regression for the KeyError: 'R2_ENDPOINT'."""
import os, sys, importlib, pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load():
    import restore_backup
    return importlib.reload(restore_backup)


def test_missing_backup_env_errors_clearly(monkeypatch):
    for k in ("R2_BACKUP_ENDPOINT","R2_BACKUP_ACCESS_KEY_ID","R2_BACKUP_SECRET_ACCESS_KEY","R2_BACKUP_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    rb = _load()
    with pytest.raises(SystemExit) as e:
        rb.R2Store("packing-station-staging-backups")
    assert "R2_BACKUP_" in str(e.value)


def test_uses_backup_creds_not_operational(monkeypatch):
    # dedicated set; operational set to DIFFERENT sentinels — the client must receive the backup ones
    monkeypatch.setenv("R2_BACKUP_ENDPOINT", "https://backup.endpoint")
    monkeypatch.setenv("R2_BACKUP_ACCESS_KEY_ID", "BACKUP_AK")
    monkeypatch.setenv("R2_BACKUP_SECRET_ACCESS_KEY", "BACKUP_SK")
    monkeypatch.setenv("R2_BACKUP_BUCKET", "packing-station-staging-backups")
    monkeypatch.setenv("R2_ENDPOINT", "https://operational.endpoint")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "OP_AK")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "OP_SK")
    rb = _load()
    captured = {}
    def fake_client(svc, **kw): captured.update(kw); return object()
    monkeypatch.setattr(rb.boto3, "client", fake_client)
    rb.R2Store("packing-station-staging-backups")
    assert captured["endpoint_url"] == "https://backup.endpoint"
    assert captured["aws_access_key_id"] == "BACKUP_AK"
    assert captured["aws_secret_access_key"] == "BACKUP_SK"
