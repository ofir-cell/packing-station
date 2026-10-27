"""ps_backup — consistent, verifiable SQLite + file backups to an object store.

Storage-agnostic: callers inject a `store` object exposing put_fileobj(key, fh),
put_bytes(key, data), get_bytes(key), list_keys(prefix), delete(key). Production
wires this to R2 (boto3); tests use an in-memory fake. NOTHING here starts a thread,
touches Production, or uploads real data on import — it is pure library code.

Design goals (see runbook): consistent snapshots via the SQLite Online Backup API,
a dedicated backup prefix separate from operational uploads, a per-run manifest with
sizes + SHA-256 + app revision + timestamp, upload-size verification, tiered
retention (6-hourly / daily / weekly), and an isolated restore that never overwrites
Production. Temp snapshots are written to a caller-chosen tmp dir (NOT the data volume).
"""
import os, sqlite3, hashlib, json, tempfile, datetime

BACKUP_PREFIX = "db-backups"          # dedicated; never under operational media prefixes
MANIFEST_NAME = "manifest.json"


def sha256_fileobj(fh, chunk=1 << 20):
    h = hashlib.sha256()
    for block in iter(lambda: fh.read(chunk), b""):
        h.update(block)
    return h.hexdigest()


def snapshot_sqlite(src_path, dst_path):
    """Consistent snapshot via the Online Backup API, then PRAGMA integrity_check.
    Raises ValueError if the snapshot is not 'ok'. Returns dst_path."""
    s = sqlite3.connect(src_path)
    try:
        d = sqlite3.connect(dst_path)
        try:
            with d:
                s.backup(d)
            res = d.execute("PRAGMA integrity_check").fetchone()
            if not res or res[0] != "ok":
                raise ValueError("integrity_check failed for %s: %r" % (src_path, res))
        finally:
            d.close()
    finally:
        s.close()
    return dst_path


def run_backup(targets, store, app_revision="unknown", now=None, tmp_dir=None):
    """targets: list of (logical_name, path). .db files are snapshotted; other files
    are copied byte-for-byte. Uploads each to <prefix>/<run_id>/<name> and writes a
    manifest. Verifies uploaded size == source size. Returns the manifest dict.

    run_id is a UTC timestamp 'YYYYMMDDThhmmssZ'. tmp_dir MUST NOT be the data volume."""
    now = now or datetime.datetime.utcnow()
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    tmp_dir = tmp_dir or tempfile.gettempdir()
    os.makedirs(tmp_dir, exist_ok=True)
    entries = []
    for name, path in targets:
        if not os.path.exists(path):
            continue
        is_db = path.endswith(".db")
        snap = None
        try:
            if is_db:
                fd, snap = tempfile.mkstemp(suffix=".db", dir=tmp_dir); os.close(fd)
                snapshot_sqlite(path, snap)
                upload_path = snap
            else:
                upload_path = path
            size = os.path.getsize(upload_path)
            with open(upload_path, "rb") as fh:
                digest = sha256_fileobj(fh)
            key = "%s/%s/%s" % (BACKUP_PREFIX, run_id, name)
            with open(upload_path, "rb") as fh:
                store.put_fileobj(key, fh)            # streamed; no whole-file in memory
            uploaded = store.size(key)
            if uploaded != size:
                raise IOError("size mismatch for %s: local=%d uploaded=%d" % (name, size, uploaded))
            entries.append({"name": name, "key": key, "bytes": size,
                            "sha256": digest, "is_db": is_db})
        finally:
            if snap and os.path.exists(snap):
                os.remove(snap)
    manifest = {"run_id": run_id, "created_utc": now.isoformat() + "Z",
                "app_revision": app_revision, "files": entries,
                "file_count": len(entries),
                "total_bytes": sum(e["bytes"] for e in entries)}
    store.put_bytes("%s/%s/%s" % (BACKUP_PREFIX, run_id, MANIFEST_NAME),
                    json.dumps(manifest, indent=2).encode())
    return manifest


def list_runs(store):
    """Return run_ids (sorted ascending) that have a manifest."""
    runs = set()
    for k in store.list_keys(BACKUP_PREFIX + "/"):
        parts = k.split("/")
        if len(parts) >= 3 and parts[-1] == MANIFEST_NAME:
            runs.add(parts[1])
    return sorted(runs)


def select_retained(run_ids, now, keep_6h=8, keep_daily=7, keep_weekly=6):
    """Decide which run_ids to KEEP under tiered retention. Returns a set.
    - keep_6h: the most recent N runs (covers the 6-hourly window)
    - keep_daily: one run per calendar day (the latest that day), N most-recent days
    - keep_weekly: one run per ISO week (the latest), N most-recent weeks
    """
    def parse(rid):
        return datetime.datetime.strptime(rid, "%Y%m%dT%H%M%SZ")
    valid = sorted([r for r in run_ids if _safe_parse(r)], key=parse)
    keep = set(valid[-keep_6h:]) if keep_6h else set()
    # daily: latest run per day
    by_day = {}
    for r in valid:
        by_day[parse(r).date()] = r      # later overwrites -> latest that day
    for d in sorted(by_day)[-keep_daily:]:
        keep.add(by_day[d])
    # weekly: latest run per ISO (year, week)
    by_week = {}
    for r in valid:
        iso = parse(r).isocalendar()
        by_week[(iso[0], iso[1])] = r
    for w in sorted(by_week)[-keep_weekly:]:
        keep.add(by_week[w])
    return keep


def _safe_parse(rid):
    try:
        datetime.datetime.strptime(rid, "%Y%m%dT%H%M%SZ"); return True
    except Exception:
        return False


def retention_prune(store, now=None, keep_6h=8, keep_daily=7, keep_weekly=6, dry_run=False):
    """Delete backup runs not selected for retention. Returns (kept, deleted)."""
    now = now or datetime.datetime.utcnow()
    runs = list_runs(store)
    keep = select_retained(runs, now, keep_6h, keep_daily, keep_weekly)
    deleted = []
    for r in runs:
        if r in keep:
            continue
        if not dry_run:
            for k in list(store.list_keys("%s/%s/" % (BACKUP_PREFIX, r))):
                store.delete(k)
        deleted.append(r)
    return sorted(keep), deleted


def restore_run(store, run_id, dest_dir, data_dir_guard=None):
    """Download a run's files into dest_dir (ISOLATED), verify every SHA-256 and run
    PRAGMA integrity_check on each DB. NEVER overwrites Production: refuses if dest_dir
    is (or is inside) data_dir_guard. Returns a report dict; raises on verification failure."""
    dest_dir = os.path.abspath(dest_dir)
    if data_dir_guard:
        g = os.path.abspath(data_dir_guard)
        if dest_dir == g or dest_dir.startswith(g + os.sep):
            raise ValueError("refusing to restore into the Production data dir (%s)" % g)
    os.makedirs(dest_dir, exist_ok=True)
    man = json.loads(store.get_bytes("%s/%s/%s" % (BACKUP_PREFIX, run_id, MANIFEST_NAME)).decode())
    report = {"run_id": run_id, "app_revision": man.get("app_revision"), "files": [], "ok": True}
    for e in man["files"]:
        data = store.get_bytes(e["key"])
        got = hashlib.sha256(data).hexdigest()
        checksum_ok = (got == e["sha256"])
        out = os.path.join(dest_dir, e["name"].replace("/", "__"))
        with open(out, "wb") as fh:
            fh.write(data)
        integrity_ok = True
        if e.get("is_db"):
            try:
                c = sqlite3.connect(out)
                integrity_ok = (c.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
                c.close()
            except Exception:
                integrity_ok = False
        ok = checksum_ok and integrity_ok
        report["files"].append({"name": e["name"], "checksum_ok": checksum_ok,
                                "integrity_ok": integrity_ok, "path": out})
        report["ok"] = report["ok"] and ok
    if not report["ok"]:
        raise ValueError("restore verification FAILED: %s" % report)
    return report
