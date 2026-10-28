"""Cycle-7 Path B — SAFE MODE ISOLATION PROOF.

Boots app.py in a subprocess with APP_ENV=staging (STAGING_SAFE armed) + a dedicated,
isolated backup config, and asserts:
  * STAGING_SAFE is True (safe mode really on)
  * the backup-only exception IS granted  (_backup_v2_permitted -> True)
  * TikTok external path is STILL blocked  (_tt_request returns SAFE_MODE)
  * carrier label purchase is STILL blocked (_can_buy_labels False)
So the exception unblocks ONLY backups, nothing else.
"""
import os, sys, subprocess, tempfile, json


def test_safe_mode_isolation_backup_only():
    data = tempfile.mkdtemp(prefix="c7iso-")
    env = {
        "PATH": os.environ.get("PATH", ""),
        "APP_ENV": "staging",                       # arm Safe Mode
        "SECRET_KEY": "t" * 40,
        "DATA_DIR": data,
        "TIKTOK_APP_KEY": "k", "TIKTOK_APP_SECRET": "s",
        "BACKUP_V2": "1",
        # dedicated, isolated backup config (no operational R2_* set -> r2 disabled)
        "R2_BACKUP_BUCKET": "packing-station-staging-backups",
        "R2_BACKUP_ACCESS_KEY_ID": "ded-ak",
        "R2_BACKUP_SECRET_ACCESS_KEY": "ded-sk",
        "R2_BACKUP_ENDPOINT": "https://acct.r2.cloudflarestorage.com",
    }
    probe = (
        "import app, json;"
        "print('PROBE'+json.dumps({"
        "'staging_safe': bool(app.STAGING_SAFE),"
        "'permitted': app._backup_v2_permitted(),"
        "'tt': (app._tt_request('GET','https://open-api.tiktokglobalshop.com/x') or {}).get('code'),"
        "'can_buy': bool(app._can_buy_labels()),"
        "}))"
    )
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-c", probe], cwd=repo, env=env,
                       capture_output=True, text=True, timeout=120)
    line = [l for l in r.stdout.splitlines() if l.startswith("PROBE")]
    assert line, "probe failed:\nSTDOUT:\n%s\nSTDERR:\n%s" % (r.stdout, r.stderr[-2000:])
    d = json.loads(line[0][5:])
    assert d["staging_safe"] is True, "Safe Mode not armed"
    assert d["permitted"][0] is True, "backup exception not granted: %s" % (d["permitted"],)
    assert d["tt"] == "SAFE_MODE", "TikTok NOT blocked under safe mode: %r" % d["tt"]
    assert d["can_buy"] is False, "carrier label purchase NOT blocked under safe mode"
