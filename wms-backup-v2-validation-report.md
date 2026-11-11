# Backup V2 — Autonomous Setup & Staging Validation Report

Honest scope first: I did **not** perform a live-R2 backup/restore. I have **no S3 data-plane credentials** (none in my environment; I will not extract or expose Production keys), and Staging Safe Mode correctly blocks the live app from writing to R2. So the end-to-end lifecycle was executed **for real against an isolated local object store with synthetic SQLite data** (not mocked externals — real SQLite online-backup, real SHA-256, real bytes, real retention/prune), and the dedicated R2 bucket was created via the Cloudflare management API. I make no claim of a live-R2 run.

## 1. What I completed autonomously
- **Phase 1 — verified deployed Staging from code/git:** `origin/staging` = `793f2ad` = **Merge PR #15**; BACKUP_V2 present. Confirmed: `BACKUP_V2` **default OFF**; the scheduler selector starts **exactly one** loop (`if BACKUP_V2 and not STAGING_SAFE → v2; elif not STAGING_SAFE → legacy; else none`) — never both; **Safe Mode blocks all external backup writes** (both branches require `not STAGING_SAFE`; the `_R2BackupStore` uses a fresh client but the v2 thread never starts under Safe Mode, and the legacy path's `r2` is the `_SafeR2` write-blocking wrapper).
- **Phase 2 — created the dedicated Staging backup bucket** `packing-station-staging-backups` (ENAM, Standard) via Cloudflare R2 API. Confirmed the two shared buckets (`packing-station`, `packing-station-hr`) are **untouched** (unchanged creation dates). New bucket is **empty** (no objects uploaded — no data-plane creds, and no Production data copied).
- **Phase 3 — executed the full backup/restore lifecycle (18/18 real checks)** via an isolated runner with synthetic multi-tenant data: upload + manifest + checksums; run verification; isolated restore with `integrity_check` + row-count proof; restore **refuses** the data dir; **corruption / missing / incomplete** all detected; retention tiers + **last-known-good protection** (prune refused to delete when the only retained candidate was corrupt, leaving older verified runs intact).
- **Phase 4 — QA/security:** added an admin-only + no-secret-leak test for `/api/ops/backup-status`; ran the **full suite: 114 passed** (112 + 2 new); gates clean. Prepared the restore runbook and Production enablement steps (below).

## 2. Services I actually accessed
| Service | Access | Evidence |
|---|---|---|
| Local Git repo | read/write (local branches, bundles) | branch `cycle7prep/backup` @ `629ff0c` |
| GitHub (origin) | **read only** (`git fetch` works; I did not push) | fetched `origin/staging` = `793f2ad` (PR #15) |
| Cloudflare R2 | **management plane** (list/create/get buckets) | created `packing-station-staging-backups`; listed 3 buckets |
| R2 S3 data plane (put/get objects) | **none** (no credentials) | all `R2_*` env absent in my environment |
| Railway | **none** (no CLI/MCP) | deploy state inferred from git; live runtime not read |

## 3. Backup bucket & security configuration (no secrets)
- **Bucket:** `packing-station-staging-backups` — **Staging only**, separate from operational media (`packing-station`) and HR (`packing-station-hr`). Prefix layout `db-backups/<run_id>/`.
- **Credentials model (recommended, to be set by you):** a dedicated **least-privilege** R2 token for Staging (`R2_BACKUP_ACCESS_KEY_ID/_SECRET/_ENDPOINT`), write-only (no delete). Deletion handled by an R2 **lifecycle rule** (set `BACKUP_PRUNE_IN_APP=0`), or a separate operator token for in-app prune.
- **Deletion protection:** enable **object versioning + a lifecycle/retention rule** on the bucket. The app-side `retention_prune` additionally refuses to delete unless a VERIFIED known-good run remains, and always protects the newest run.
- **Not configurable via my access:** R2 **token issuance, versioning, and lifecycle rules** are account/security-policy settings not exposed by the bucket management API I have — these need the Cloudflare dashboard (and, per your rules, touch security policy → your action).

## 4. Real backup-and-restore test results (isolated local store + synthetic data)
```
== 1. UPLOAD + MANIFEST + CHECKSUMS ==  5 files (3 db + 2 json); sha256 each; app_revision recorded;
                                         objects only under db-backups/<run_id>/; no temp on data dir
== 2. RUN VERIFICATION ==                verify_run OK (manifest + all object sizes match)
== 3. ISOLATED RESTORE + INTEGRITY ==    restore verified (checksums + PRAGMA integrity_check);
                                         restored shipments.db has the 2 synthetic rows; restore REFUSES the data dir
== 4. CORRUPTION / MISSING / INCOMPLETE ==  tampered object -> restore raises; size mismatch -> verify flags;
                                            missing object -> verify flags
== 5. RETENTION + LAST-KNOWN-GOOD ==      pruned 15 old / kept 6 tiers; newest always protected;
                                          with newest corrupted, prune REFUSED to delete and a verified run still exists
RESULT: 18/18 checks passed
```
Plus the committed pytest suite: **114 passed** (includes 15 ps_backup/backup-status tests). These are automated sandbox results — **not** a live-R2 or live-Staging run.

## 5. Monitoring & alert verification
- `/api/ops/backup-status` is `@req_role("admin")` — tested: unauth ≠200, worker →403, admin →200. Payload is flags/ids only (`enabled, bucket_configured, last_run_id, last_ok, last_error, last_finished_utc, files, age_seconds, max_age_seconds, stale`); a test asserts no `secret/access_key/password/token/aws_` strings appear. 
- Failure alert path (`_send_email` to `BACKUP_ALERT_EMAIL`) and staleness (`stale=true` when newest run older than `BACKUP_MAX_AGE_SEC`, default 7h) verified by code; email is suppressed under `IS_STAGING` so no real messages are sent during staging validation.
- Log lines (`[backup-v2] ok/FAILED`) carry run id / file count / revision only; error text is truncated to 300 chars (may include bucket/endpoint names — never keys). No customer data.

## 6. Remaining blockers (need your authorized action — all cross the approval/access boundary)
1. **R2 least-privilege token + versioning + lifecycle** on `packing-station-staging-backups` — dashboard/security-policy; not exposed to my access.
2. **Set Staging Railway vars** (`BACKUP_V2=1`, `R2_BACKUP_BUCKET=packing-station-staging-backups`, `R2_BACKUP_*` creds, `BACKUP_ALERT_EMAIL`, `BACKUP_MAX_AGE_SEC`, `BACKUP_PRUNE_IN_APP`) — I must not change Railway vars.
3. **A real live-R2 run on Staging** — requires #1/#2 and a way to execute without disabling Safe Mode in the live app. Recommended: run `restore_backup.py`/a one-off backup from a separate runner using the **Staging test token** (never Production creds). I can drive this once you provide an isolated test credential to the sandbox, or you run the one-off.
4. **Deploy of the follow-up test commit** (`629ff0c`, admin-status test) if you want it in staging — needs your push/merge approval (bundle delivered).

## 7. Production GO / NO-GO
- **Backup V2 code: GO to continue** — default-off, mutually-exclusive scheduler, Safe-Mode-respecting, 114/114 green, 18/18 real-lifecycle checks, isolated restore proven, dedicated bucket created.
- **Enable V2 in Production: NO-GO until** — (a) a **real live-R2 backup + `restore_backup.py` → RESTORE OK** has actually run against a dedicated **Production** backup bucket with versioning/lock + least-priv token; (b) the staleness/failure alert is wired to a monitor; (c) ≥1 week of verified Staging V2 runs; (d) the one-time pre-deploy backup (prior plan) is taken. I will not claim these pass until executed.

## Verified restore runbook (isolated; never overwrites Production)
1. With **read** creds for the backup bucket: `python3 restore_backup.py --list` → choose a `run_id`.
2. `python3 restore_backup.py --run <run_id> --dest /tmp/restore_check` → downloads into a disposable dir, verifies every SHA-256 + `integrity_check`; **refuses** if `--dest` is inside `DATA_DIR`. Expect `RESTORE OK`.
3. Inspect restored `*.db` read-only (row counts). For a real recovery (your authorization, app stopped): back up the current volume, copy verified DBs into place, restart. Never copy into a running app's volume.

## Exact steps to enable Backup V2 in Production (later, your approval)
1. Create a **Production** dedicated backup bucket + versioning/Object-Lock + least-priv token.
2. Take the one-time verified pre-deploy backup; confirm `integrity_check=ok`.
3. Set Production vars (`BACKUP_V2=1`, `R2_BACKUP_BUCKET=<prod backup bucket>`, `R2_BACKUP_*`, `BACKUP_ALERT_EMAIL`, `BACKUP_MAX_AGE_SEC=25200`, prune policy).
4. Deploy; confirm `/api/ops/backup-status` → `enabled:true, last_ok:true, stale:false`; confirm `db-backups/<run_id>/` + manifest; run `restore_backup.py` once → `RESTORE OK`.
5. Wire the monitor alert on `stale=true`/`last_ok=false`; decommission legacy `backups/<dow>/` after ≥1 week.

---
*Autonomous, reversible Staging/local work only. No Production code/vars/DB/volume/bucket/integration changed; no pushes/merges/deploys; Safe Mode never disabled; no existing backup objects deleted or overwritten; no credentials or customer data exposed.*
