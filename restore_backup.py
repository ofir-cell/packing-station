#!/usr/bin/env python3
"""restore_backup — isolated, read-only restore tester for ps_backup runs.

Downloads a backup run from R2 into a LOCAL isolated directory, verifies every
checksum and runs PRAGMA integrity_check. It NEVER writes to the Production data
volume (it refuses if --dest is inside DATA_DIR). It performs NO Production DB
writes and does not touch the live app.

Usage:
  python3 restore_backup.py --list
  python3 restore_backup.py --run 20260115T060000Z --dest /tmp/restore_check
Requires the same R2 env the app uses (read scope is enough).
"""
import os, sys, argparse, boto3
from botocore.client import Config as BotoConfig
import ps_backup


REQUIRED_ENV = ("R2_BACKUP_ENDPOINT", "R2_BACKUP_ACCESS_KEY_ID",
                "R2_BACKUP_SECRET_ACCESS_KEY", "R2_BACKUP_BUCKET")

def _require_backup_env():
    """Backup V2 restores use the DEDICATED R2_BACKUP_* credentials/bucket ONLY — never the
    operational R2_* creds. Fail loudly (no silent fallback) when any are missing."""
    missing = [k for k in REQUIRED_ENV if not (os.environ.get(k) or "").strip()]
    if missing:
        raise SystemExit("Missing required env for Backup V2 restore: %s\n"
                         "Set the dedicated staging backup token vars (R2_BACKUP_*), "
                         "not the operational R2_* ones." % ", ".join(missing))

class R2Store:
    def __init__(self, bucket):
        _require_backup_env()
        self.bucket = bucket
        self.c = boto3.client("s3", endpoint_url=os.environ["R2_BACKUP_ENDPOINT"],
                              aws_access_key_id=os.environ["R2_BACKUP_ACCESS_KEY_ID"],
                              aws_secret_access_key=os.environ["R2_BACKUP_SECRET_ACCESS_KEY"],
                              config=BotoConfig(signature_version="s3v4",
                                                connect_timeout=5, read_timeout=60,
                                                retries={"max_attempts": 3, "mode": "standard"}),
                              region_name="auto")

    def put_fileobj(self, key, fh): self.c.upload_fileobj(fh, self.bucket, key)
    def put_bytes(self, key, data): self.c.put_object(Bucket=self.bucket, Key=key, Body=data)
    def get_bytes(self, key): return self.c.get_object(Bucket=self.bucket, Key=key)["Body"].read()
    def size(self, key): return self.c.head_object(Bucket=self.bucket, Key=key)["ContentLength"]
    def delete(self, key): self.c.delete_object(Bucket=self.bucket, Key=key)
    def list_keys(self, prefix):
        out, tok = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
            if tok: kw["ContinuationToken"] = tok
            r = self.c.list_objects_v2(**kw)
            out += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"): break
            tok = r.get("NextContinuationToken")
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--run")
    ap.add_argument("--dest", default="/tmp/ps_restore_check")
    ap.add_argument("--bucket", default=os.environ.get("R2_BACKUP_BUCKET"))
    a = ap.parse_args()
    store = R2Store(a.bucket)
    if a.list:
        for r in ps_backup.list_runs(store): print(r)
        return
    if not a.run:
        ap.error("--run RUN_ID required (or --list)")
    guard = os.environ.get("DATA_DIR") or os.path.join(os.path.expanduser("~"), "PackingStationData")
    rep = ps_backup.restore_run(store, a.run, a.dest, data_dir_guard=guard)
    print("RESTORE OK" if rep["ok"] else "RESTORE FAILED")
    for f in rep["files"]:
        print("  %-28s checksum=%s integrity=%s" % (f["name"], f["checksum_ok"], f["integrity_ok"]))
    sys.exit(0 if rep["ok"] else 1)


if __name__ == "__main__":
    main()
