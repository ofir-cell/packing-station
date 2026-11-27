# Production Backup & Disaster Recovery Plan

Prepared against the deployable revision `origin/staging` = `c2b4088`. **No Production DB/R2/Railway access or writes, no live jobs started, no data uploaded.** Delivered as reviewable local code + this plan. New files: `ps_backup.py`, `restore_backup.py`, `tests/test_ps_backup.py` (8 tests). They are **not wired into app startup** — deploying this branch changes nothing until you explicitly enable it. Full suite 107/107.

## 1. Existing backup capability assessment (from code, `c2b4088`)
A backup thread exists (`_backup_all` / `_backup_loop`, started when `not STAGING_SAFE`):
- ✅ Uses the **SQLite Online Backup API** (`s.backup(d)`) → consistent snapshots.
- ✅ Backs up `platform.db`, `users.json`, and per-org `shipments.db` + `giveaways.db`.
- ✅ One-worker leader via `flock`; no-op-safe when R2 is absent (writes local).
- ⚠️ Cadence is effectively **once per day** (loop sleeps 6h but gates on `>20h since last`), **not every 6h**.
- ⚠️ Retention = 7 **day-of-week** slots that **overwrite weekly** → max 7-day history; a fault persisting >7 days overwrites all good copies; no weekly archive.
- ⚠️ Stored under `backups/<dow>/` in the **same R2 bucket as operational uploads** (videos/photos/documents/labels) — no isolation, no deletion protection.
- ⚠️ Reads each snapshot **fully into memory** before upload.
- ❌ **No manifest**, **no checksums**, **no app-revision** recorded.
- ❌ **No post-upload integrity/size verification**; snapshot not `integrity_check`ed.
- ❌ **No alerting** on failure/missing (only a log print).
- ❌ **No restore tooling / no restore test.**
- ❌ Non-DB coverage partial: `users.json` only; **not** `stations.json`, per-org `documents.json`, `packing_log.csv`; media relies on being operational R2 objects.

**Verdict:** active but **incomplete** — not sufficient for reliable DR or the pre-deployment guarantee.

## 2. Missing functionality & risks
| Gap | Risk |
|---|---|
| Daily, not 6-hourly | up to ~24h data loss window (a full LIVE day) |
| 7-day overwrite retention | silent corruption older than 7 days becomes unrecoverable |
| Shared bucket, no isolation/lock | an errant admin tool (e.g. repair-videos) or deletion can hit backups |
| No manifest/checksum/revision | can't prove a backup is complete or know which code wrote it |
| No verification | a truncated/partial upload looks "done" |
| No alerting | a silently failing backup is discovered only during a disaster |
| No restore procedure | unrehearsed restore during an incident = extended outage |

## 3. Proposed backup architecture (implemented in `ps_backup.py`)
- **Consistent snapshots** via Online Backup API + `PRAGMA integrity_check` before upload.
- **Dedicated prefix `db-backups/<run_id>/`** (run_id = UTC `YYYYMMDDThhmmssZ`), separate from all operational media prefixes. **Recommended: a dedicated bucket `R2_BACKUP_BUCKET`** with **object versioning + a lifecycle/Object-Lock retention rule** and a **separate, least-privilege R2 token** (write-only for the app, no delete; deletes done by a scoped lifecycle rule or an operator token) → protection against accidental/malicious deletion.
- **Per-run `manifest.json`**: `{run_id, created_utc, app_revision, files:[{name,key,bytes,sha256,is_db}], total_bytes}`. App revision from `RAILWAY_GIT_COMMIT_SHA` (fallback "unknown").
- **Verification**: SHA-256 per file; uploaded object size asserted == source size; restore re-checks SHA-256 + `integrity_check`.
- **Tiered retention** (`select_retained` / `retention_prune`): keep last **8 six-hourly** runs + **7 daily** (latest per day) + **6 weekly** (latest per ISO week). True time-depth without unbounded growth. At ~321MB/run that's well within 1GB only if backups go to a **separate bucket** (they must — do not keep many runs on the 1GB operational volume).
- **No large temp on `/data`**: snapshots go to a caller-chosen `tmp_dir` (container-ephemeral `TMPDIR`, never `DATA_DIR`), streamed to R2 via `upload_fileobj`, then deleted. (Test `test_tmp_not_on_data_volume` enforces this.)
- **Alerting**: on any failed/short run, send via the existing `_send_email`/Resend path and expose an admin `/api/ops/backup-status` endpoint (last run_id, time, file_count, ok) so monitoring can alert if the newest run is older than ~7h.
- **6-hourly schedule**: driver runs every 6h behind the existing flock leader + a `>5h since last` marker.

## 4. Safe local implementation (delivered, not activated)
- `ps_backup.py` — storage-agnostic library (inject an R2-backed `store`): `snapshot_sqlite`, `run_backup`, `list_runs`, `select_retained`, `retention_prune`, `restore_run`. Pure library; starts no thread; imports touch nothing live.
- `restore_backup.py` — CLI for isolated restore tests against R2 (read scope); refuses to write into `DATA_DIR`.
- **Not** wired into `app.py` startup — enabling it is a deliberate future step (§7), so merging/deploying this branch leaves current behavior unchanged.

## 5. Automated tests (`tests/test_ps_backup.py`, 8, all local)
consistent snapshot + integrity; manifest correctness (sizes, 64-char sha256, revision) and dedicated-prefix placement; temp dir is never the data volume; restore round-trip verifies checksum+integrity; restore **refuses the Production data dir**; restore **detects corruption** (tampered object → raises); retention tier selection; prune deletes old runs and keeps the right tiers. Full suite with these added: **107 passed**.

## 6. Restore runbook (isolated — never overwrites Production)
1. From any machine with **read** R2 creds: `python3 restore_backup.py --list` → pick a `run_id`.
2. `python3 restore_backup.py --run <run_id> --dest /tmp/restore_check` → downloads to an isolated dir, verifies every SHA-256 + `integrity_check`. Refuses if `--dest` is inside `DATA_DIR`.
3. Inspect: open the restored `*.db` read-only, spot-check row counts vs expectations.
4. **Real recovery (only on your authorization, app stopped):** stop the service, back up the current (bad) volume, copy the verified DBs into `DATA_DIR/orgs/<org>/…` and `platform.db`, restart. Never copy into a running app's volume.

## 7. Exact Production enablement steps (do NOT run without approval)
1. **Create a dedicated backup bucket** `R2_BACKUP_BUCKET` in Cloudflare R2 with **versioning + Object-Lock/lifecycle retention** and a **least-privilege token**.
2. Add Railway vars (no secrets exposed here): `R2_BACKUP_BUCKET`, confirm `RAILWAY_GIT_COMMIT_SHA` is available for the manifest.
3. In a future deploy, wire a 6-hourly driver that calls `ps_backup.run_backup(targets, R2Store(R2_BACKUP_BUCKET), app_revision=…, tmp_dir=TMPDIR)` then `retention_prune(...)`, behind the existing flock leader, and add `/api/ops/backup-status`.
4. Deploy to **staging first**; confirm runs appear under `db-backups/` with valid manifests; run `restore_backup.py --run … --dest /tmp/x` and confirm `RESTORE OK`.
5. Enable in Production; confirm first run + manifest; set a monitor alert if newest run age > 7h.

## 8. One-time verified pre-deployment backup (for the Cycles 1–6 promotion)
Before the production promote, run a **manual, verified** snapshot (no new code needed):
1. On the Production shell/one-off, for each DB: `sqlite3 <db> ".backup '/tmp/predeploy/<name>'"` (platform.db + every `orgs/<org>/shipments.db`,`giveaways.db`; copy `users.json`,`stations.json`).
2. `sqlite3 <backup> "PRAGMA integrity_check;"` → `ok` for each; record `sha256sum` and row counts.
3. Upload the set to `db-backups/predeploy-<ts>/` (dedicated bucket) and verify object sizes.
4. Keep for 14 days. This is the restore point if the promotion must be rolled back.

## 9. GO / NO-GO
- **GO** to review/stage this backup module (additive, isolated, 107/107, nothing live changed).
- **NO-GO** to call the improved backups "production DR" until: the dedicated bucket + versioning/lock + scoped token exist; the 6-hourly driver is wired and validated on staging; one `restore_backup.py` test returns `RESTORE OK` from R2; and the backup-age alert is live.
- **Blockers needing your authorized access:** creating the R2 bucket/token/lifecycle; running the one-time pre-deploy backup on the Production volume; confirming `TMPDIR` is container-ephemeral (not `/data`) on Railway; wiring + deploying the driver (separate approval).

## What you must personally verify
- [ ] A dedicated **backup bucket** (not the operational bucket) with versioning + deletion protection + least-privilege token.
- [ ] Backups do **not** accumulate on the 1GB `/data` volume (they go to R2; local fallback is only for dev).
- [ ] The one-time pre-deploy backup is taken **and** a `restore_backup.py` dry-run verifies it before the Cycles 1–6 promotion.
- [ ] Monitoring alerts if no successful backup in the last ~7 hours.

*Nothing was deployed, activated, or uploaded. Awaiting approval before wiring or enabling any backup job in Production.*
