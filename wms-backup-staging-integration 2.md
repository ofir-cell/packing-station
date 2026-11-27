# Backup Module — Staging Integration & Validation

Branch `cycle7prep/backup` @ **3394cd8** (on `origin/staging` c2b4088) · Bundle `cycle7prep-backup-staging-3394cd8.bundle`.
Gates: `py_compile` ✅ · `check_js` ✅ (63/63) · full suite **112 passed** (99 app + 13 backup).
**Nothing enabled, deployed, uploaded, or changed in Production/Railway/R2.** `BACKUP_V2` defaults **OFF** — merging/deploying this branch keeps the legacy backup behavior exactly as today until you set the flag.

## 1. Legacy thread transition (no duplicate schedulers)
The scheduler is now **selected**, never doubled:
- `BACKUP_V2=on` → start `_backup_v2_loop`, **do not** start the legacy `_backup_loop`.
- `BACKUP_V2` off (default) → start the legacy loop only (unchanged).
- Either way, both are gated by `not STAGING_SAFE` and by a `flock` leader (`.backupv2.guard` / `.backup.guard`), so only one worker runs it. No path starts both.

## 2. Feature flag (explicit, default-disabled)
`BACKUP_V2` (`1/true/yes` to enable). Verified default-off in code. Enabling is a deliberate env change (never automatic).

## 3. Six-hour scheduler + cross-process leader
`_backup_v2_loop`: `flock(LOCK_EX|LOCK_NB)` leader election; re-checks every 10 min, runs when `>6h` since the `.backupv2_last` marker → **every 6 hours**, one worker only.

## 4. Monitoring + alerts
- `GET /api/ops/backup-status` (admin, read-only, **no secrets/paths/creds**): `{enabled, bucket_configured, last_run_id, last_ok, last_error, last_finished_utc, files, age_seconds, max_age_seconds, stale}`.
- **Failure alert:** a failed run emails `BACKUP_ALERT_EMAIL` (if set) and logs `[backup-v2] FAILED`.
- **Age/missing alert:** `stale=true` when the newest run is older than `BACKUP_MAX_AGE_SEC` (default 7h) — your external monitor polls the endpoint and alerts on `stale` or `last_ok=false`.

## 5. Coverage — included vs documented exclusions
**Included:** `platform.db`, `users.json`, `stations.json`, and per-tenant `shipments.db` + `giveaways.db` (consistent online-backup snapshots; JSON copied byte-for-byte).
**Documented exclusions (by design):** R2-hosted media (videos/photos/documents/labels) are **already durable objects in R2** and are not re-copied; per-org `documents.json`, `packing_log.csv`, and `.login_attempts.json` are operational/ephemeral and excluded. If you want media/these JSONs in the DR set, say so and I'll extend `_backup_targets` — it's a one-line-per-file change.

## 6. Temp snapshots cannot exhaust `/data`
`_backup_v2_run_once` snapshots to `TMPDIR` (container-ephemeral) and **explicitly redirects to the system temp if `TMPDIR` resolves under `DATA_DIR`**, streams to R2 via `upload_fileobj`, and deletes the temp immediately (test `test_tmp_not_on_data_volume`). No whole-file-in-memory for the upload path.

## 7. Retention + last-known-good protection
Tiered keep (8×6-hourly, 7 daily, 6 weekly). Hardened `retention_prune`:
- always protects the **newest** run id;
- **refuses to delete anything unless at least one retained run is VERIFIED known-good** (`verify_run`: manifest parses + every object present at the manifest's size). A partial/corrupt latest upload can never trigger deletion of the last good backup. (tests `test_prune_protects_last_known_good_when_latest_corrupt`, `test_prune_deletes_nothing_if_no_verified_run`.)

## 8. Restore validated against corrupted / missing / incomplete
`restore_run` + `verify_run` tested for: healthy round-trip; tampered object (checksum → raises); missing object (raises); missing manifest (detected); size-mismatch/incomplete (detected). Restore always writes to an **isolated dir** and **refuses the Production data dir**.

## 9. Least-privilege credentials
`_R2BackupStore` uses a **separate client** and optional **separate creds** `R2_BACKUP_ENDPOINT/_ACCESS_KEY_ID/_SECRET_ACCESS_KEY` (fallback to main R2_*), targeting a **dedicated bucket** `R2_BACKUP_BUCKET`. Recommended: a write-only token (no delete) + set `BACKUP_PRUNE_IN_APP=0` and let an R2 **lifecycle rule** do deletion; or a separate prune token. Backups never use the `_SafeR2` wrapper or the operational media prefixes.

## 10. Tests
13 backup tests + 99 existing = **112 passed**. Isolated restore tests exercise the full round-trip and every failure mode above — all local, in-memory fake store, no real R2.

---

## Exact configuration requirements (Staging validation — set when you authorize)
| Var | Value | Purpose |
|---|---|---|
| `BACKUP_V2` | `1` | enable the new scheduler (off elsewhere) |
| `R2_BACKUP_BUCKET` | a **dedicated** staging backup bucket | isolation from operational media |
| `R2_BACKUP_ACCESS_KEY_ID` / `_SECRET_ACCESS_KEY` / `_ENDPOINT` | least-privilege token (optional; else reuses R2_*) | least privilege |
| `BACKUP_ALERT_EMAIL` | an ops address | failure alerts |
| `BACKUP_MAX_AGE_SEC` | `25200` (7h) | staleness threshold |
| `BACKUP_PRUNE_IN_APP` | `0` if using a write-only token + lifecycle, else `1` | deletion policy |
| external writes | staging must allow R2 (not safe-mode) for the run to execute | so the backup actually uploads |

## Staging validation plan
1. Create a dedicated **staging** backup bucket (+ versioning) and least-privilege token.
2. Set the vars above on the **staging** service; deploy the branch (your approval).
3. Confirm `/api/ops/backup-status` → `enabled:true, bucket_configured:true`.
4. Force a run (wait a cycle or temporarily lower the 6h gate on staging) → status shows `last_ok:true`, a `run_id`, `files≥5`, `stale:false`.
5. Confirm objects appear **only** under `db-backups/<run_id>/` in the dedicated bucket (not in operational prefixes), with a `manifest.json` carrying the app revision.
6. `python3 restore_backup.py --list` then `--run <id> --dest /tmp/restore_check` → **RESTORE OK**, every file `checksum=True integrity=True`.
7. Negative checks: delete one object in the staging bucket → restore of that run raises; confirm `verify_run` reports it; confirm prune refuses when no verified run.
8. Let two cycles run; confirm retention keeps the newest and tiers; confirm no snapshot files linger in `/data`.
9. Confirm the legacy loop did **not** also run (one scheduler only; check logs).

## Production enablement runbook (after staging validation + your approval)
1. Create the **production** dedicated backup bucket with **versioning + Object-Lock/lifecycle** and a **least-privilege** token.
2. Take the one-time verified pre-deploy backup (prior plan §8) first.
3. Set the same vars on Production (`BACKUP_V2=1`, `R2_BACKUP_*`, alert email, age threshold, prune policy).
4. Deploy; confirm `/api/ops/backup-status` healthy; confirm first `db-backups/<run_id>/` + manifest; run `restore_backup.py` once → `RESTORE OK`.
5. Add the monitor alert on `stale=true` or `last_ok=false`.
6. Decommission the legacy `backups/<dow>/` only after ≥1 week of verified V2 runs.

## GO / NO-GO
- **GO** to review/stage this branch — additive, flag-off, 112/112, no live change.
- **NO-GO** to call V2 the production backup until: dedicated bucket + versioning/lock + least-priv token exist; staging validation steps 3–9 pass; one real `restore_backup.py` returns `RESTORE OK` from the staging bucket; and the staleness alert is wired.
- **Needs your authorized access:** creating R2 buckets/tokens/lifecycle; setting Railway vars; the deploy; and running the live restore test. I did none of these.

## What you must personally verify
- [ ] `BACKUP_V2` is **off** in any environment you haven't deliberately configured.
- [ ] The staging backup bucket is **separate** from operational media and from Production's bucket.
- [ ] A real `restore_backup.py --run … ` returns `RESTORE OK` from the staging bucket before trusting it.
- [ ] Only ONE scheduler runs (logs show either `[backup-v2] scheduler started` **or** the legacy line, never both).
- [ ] Monitoring alerts on `stale`/`last_ok:false`.
