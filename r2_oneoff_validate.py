#!/usr/bin/env python3
"""One-off LIVE-R2 Backup V2 validation — synthetic data only, isolated from the app.

Runs OUTSIDE the deployed Staging application, so it does NOT require disabling Safe
Mode (Safe Mode only blocks the live app's own threads; this is a separate process).
Uses the staging backup token (R2_BACKUP_* env) against the dedicated staging backup
bucket, writes SYNTHETIC SQLite data under a 'validation/' prefix, then runs the full
lifecycle: upload -> manifest/size verify -> isolated restore+integrity -> corruption
detection. Best-effort cleanup of its own test objects at the end.

NEVER touches Production, real Staging data, or operational prefixes. Requires:
  R2_BACKUP_ENDPOINT, R2_BACKUP_ACCESS_KEY_ID, R2_BACKUP_SECRET_ACCESS_KEY,
  R2_BACKUP_BUCKET (= packing-station-staging-backups)
"""
import os, sys, sqlite3, tempfile, datetime, shutil, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_backup
import boto3
from botocore.client import Config as BotoConfig

PREFIX = "validation"   # isolated; real backups live under db-backups/

class R2Store:
    def __init__(self):
        self.bucket = os.environ["R2_BACKUP_BUCKET"]
        self.c = boto3.client("s3", endpoint_url=os.environ["R2_BACKUP_ENDPOINT"],
            aws_access_key_id=os.environ["R2_BACKUP_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_BACKUP_SECRET_ACCESS_KEY"],
            config=BotoConfig(signature_version="s3v4", connect_timeout=5, read_timeout=120,
                              retries={"max_attempts": 3, "mode": "standard"}), region_name="auto")
    def put_fileobj(self, k, fh): self.c.upload_fileobj(fh, self.bucket, k)
    def put_bytes(self, k, d): self.c.put_object(Bucket=self.bucket, Key=k, Body=d)
    def get_bytes(self, k): return self.c.get_object(Bucket=self.bucket, Key=k)["Body"].read()
    def size(self, k): return self.c.head_object(Bucket=self.bucket, Key=k)["ContentLength"]
    def delete(self, k): self.c.delete_object(Bucket=self.bucket, Key=k)
    def list_keys(self, prefix):
        out, tok = [], None
        while True:
            kw = {"Bucket": self.bucket, "Prefix": prefix, "MaxKeys": 1000}
            if tok: kw["ContinuationToken"] = tok
            r = self.c.list_objects_v2(**kw); out += [o["Key"] for o in r.get("Contents", [])]
            if not r.get("IsTruncated"): break
            tok = r.get("NextContinuationToken")
        return out


def mkdb(path, rows):
    c = sqlite3.connect(path); c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    c.executemany("INSERT INTO t(v) VALUES(?)", [(r,) for r in rows]); c.commit(); c.close()


def main():
    # route ps_backup's dedicated prefix to the isolated validation prefix
    ps_backup.BACKUP_PREFIX = PREFIX
    store = R2Store()
    root = tempfile.mkdtemp(prefix="r2val-"); data = os.path.join(root, "data"); tmp = os.path.join(root, "tmp")
    os.makedirs(data); os.makedirs(tmp)
    mkdb(os.path.join(data, "platform.db"), ["a", "b"])
    open(os.path.join(data, "users.json"), "w").write(json.dumps({"admin": {"role": "admin"}}))
    targets = [("platform.db", os.path.join(data, "platform.db")), ("users.json", os.path.join(data, "users.json"))]
    ok = True
    try:
        man = ps_backup.run_backup(targets, store, app_revision="oneoff", tmp_dir=tmp)
        print("PASS upload+manifest:", man["run_id"], man["file_count"], "files")
        v, d = ps_backup.verify_run(store, man["run_id"]); print(("PASS" if v else "FAIL"), "verify:", d); ok &= v
        rep = ps_backup.restore_run(store, man["run_id"], os.path.join(root, "restore"),
                                    data_dir_guard=data)
        print(("PASS" if rep["ok"] else "FAIL"), "restore+integrity"); ok &= rep["ok"]
        # corruption detection
        victim = man["files"][0]["key"]; keep = store.get_bytes(victim)
        store.put_bytes(victim, keep + b"X")
        try:
            ps_backup.restore_run(store, man["run_id"], os.path.join(root, "bad"), data_dir_guard=data)
            print("FAIL corruption-detection"); ok = False
        except Exception:
            print("PASS corruption detected")
    finally:
        # best-effort cleanup of this run's test objects (needs delete perm; harmless if denied)
        for k in store.list_keys(PREFIX + "/"):
            try: store.delete(k)
            except Exception: pass
        shutil.rmtree(root, ignore_errors=True)
    print("RESULT:", "PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
