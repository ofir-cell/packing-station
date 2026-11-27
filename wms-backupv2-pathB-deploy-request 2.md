# Backup V2 — Path B (backup-only Safe Mode exception): Deployment Approval Request

Implemented on an isolated branch, fully tested. **Nothing merged, deployed, pushed to a protected branch, or changed in Railway/R2/Production. Safe Mode logic unchanged except the narrow, fail-closed backup carve-out below. No secret values handled or printed.**

## Exact commit & PR
- **Branch:** `cycle7/backup-safe-exception` · **tip commit `714cc8a`** (based on deployed staging `793f2ad`).
- **PR contents (origin/staging..branch), 3 additive commits:** `714cc8a` (the carve-out), `724afa7` (`r2_oneoff_validate.py`), `629ff0c` (admin-status test).
- **PR not opened by me:** this sandbox has read-only GitHub (push returns `could not read Username`) and no `gh`. Verified bundle delivered: **`cycle7-backup-safe-exception-714cc8a.bundle`**. To create the PR targeting `staging` (your push rights):
  ```bash
  cd packing-station
  git fetch /path/to/cycle7-backup-safe-exception-714cc8a.bundle cycle7/backup-safe-exception:cycle7/backup-safe-exception
  git push origin cycle7/backup-safe-exception
  # open a PR: base = staging, compare = cycle7/backup-safe-exception
  ```

## What the carve-out does (requirements 1–4, 11)
- **STAGING_SAFE stays enabled at all times** — the global flag is untouched; `_SafeR2` still wraps the operational R2 client; TikTok/carrier/email/customer paths stay blocked.
- A single gate `_backup_v2_permitted() -> (allowed, reason)` is the **only** thing that may run an external write under Safe Mode, and it is **fail-closed**. It returns allowed **only when all** hold: `BACKUP_V2` on; `R2_BACKUP_BUCKET` set and **different** from `R2_BUCKET`/`R2_HR_BUCKET`; dedicated `R2_BACKUP_ACCESS_KEY_ID`/`SECRET`/`ENDPOINT` all present; and those creds **differ** from the operational R2 creds. Any missing/mismatched value → `(False, reason)` and **no scheduler starts**.
- `_R2BackupStore` now **requires** the dedicated creds (no fallback to operational creds/bucket) and raises otherwise.
- **Pruning default is now OFF** (`BACKUP_PRUNE_IN_APP=0`) — review Bucket Lock + lifecycle before enabling in-app deletes (requirement 8).
- **Production behavior preserved:** production runs with Safe Mode off → the selector starts the **legacy** backup loop exactly as before unless V2 is both enabled and fully configured; the legacy loop is unchanged and remains the fallback (requirement 11).

## Test results (requirement 9) — full suite **122 passed / 0 failed**
- Gates: `py_compile` + `check_js` (63/63) clean.
- Fail-closed permission matrix (7): all-good → permitted; and each of disabled / no bucket / bucket==operational / missing creds / creds==operational → refused with the right reason.
- Store fail-closed: `_R2BackupStore()` raises without dedicated creds.
- Scheduler mutual exclusion + 6h cadence + flock leader: verified in code and by the existing ps_backup scheduler-logic tests; one scheduler per interval across processes via `flock(LOCK_EX|LOCK_NB)` on `.backupv2.guard`, and a `.backupv2_last` 6h marker (requirement 5).
- Consistent snapshots / manifest / checksums / integrity (requirement 6): the 18-check live-path runner + ps_backup unit tests (online-backup snapshot, SHA-256, `PRAGMA integrity_check`, verify_run).

## Safe Mode isolation proof (requirement 2) — automated, in the suite
`tests/test_cycle7_safe_mode_isolation.py` boots `app.py` in a subprocess with `APP_ENV=staging` + the dedicated backup config and asserts, from the running app:
```
staging_safe = True          # Safe Mode armed
permitted     = (True,'ok')  # backup-only exception granted
tt            = 'SAFE_MODE'  # _tt_request STILL blocked
can_buy       = False        # carrier label purchase STILL blocked
```
→ the exception unblocks **only** backups; every other external path stays blocked. PASS.

## Required Railway environment variables (Staging only — set values in your secret store, never chat)
| Var | Value | Notes |
|---|---|---|
| `BACKUP_V2` | `1` | enables the scheduler (gated by `_backup_v2_permitted`) |
| `R2_BACKUP_BUCKET` | `packing-station-staging-backups` | must differ from `R2_BUCKET`/`R2_HR_BUCKET` |
| `R2_BACKUP_ENDPOINT` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | dedicated |
| `R2_BACKUP_ACCESS_KEY_ID` / `R2_BACKUP_SECRET_ACCESS_KEY` | the **bucket-scoped staging** token | must differ from operational R2 creds |
| `BACKUP_ALERT_EMAIL` | ops address | failure alerts (email suppressed in staging, so no real sends) |
| `BACKUP_MAX_AGE_SEC` | `25200` | 7h staleness threshold |
| `BACKUP_PRUNE_IN_APP` | leave unset/`0` | keep OFF until Bucket Lock/lifecycle reviewed |
Keep `APP_ENV=staging` (Safe Mode stays on). **Do not** set these on Production. **Do not** set `STAGING_ALLOW_EXTERNAL`.

## Bucket Lock & lifecycle requirements (requirement 8 — before enabling prune)
On `packing-station-staging-backups` (dashboard or `wrangler`, your action — I can't set policies):
- **Bucket Lock** rule on prefix `db-backups/` with a retention ≥ your weekly horizon (protects against deletion/overwrite). R2 supports this.
- **Object Lifecycle** expiry on `db-backups/` ≥ the lock period, to age out old runs.
- Only after both exist, consider `BACKUP_PRUNE_IN_APP=1`; otherwise leave in-app prune OFF and let lifecycle handle deletion (the app's token would then not need delete).

## Credential rotation gate (requirement 10)
I have **no record** of the specific "previously exposed" token (I have never printed secrets) and cannot verify rotation from here. **Hard gate — you must confirm:** the exposed staging credential has been **rotated and the old value revoked** in the provider dashboard, the new value lives only in Railway staging + your secret store, and it is **not** reused in Production. I will not treat activation as GO until you confirm this. (The `R2_BACKUP_*` token should also be verified bucket-scoped, not account-wide.)

## Controlled staging activation plan
1. Confirm credential rotation (above) and that `R2_BACKUP_*` is bucket-scoped.
2. Create the Bucket Lock + lifecycle rules.
3. Merge the PR into `staging` (your approval) → Railway auto-deploys.
4. Set the staging Railway vars above; keep `APP_ENV=staging`.
5. Verify `GET /api/ops/safe-mode` → `staging:true, safe_mode:true, external_calls_blocked:true` (unchanged).
6. Verify `GET /api/ops/backup-status` → `enabled:true, permitted:true, backup_only_exception_active:true, safe_mode:true`.
7. Within ~10 min of the first 6h tick (or temporarily shorten the marker for one observed run), confirm `last_ok:true`, a `run_id`, `files≥5`, `stale:false`, and objects under `db-backups/<run_id>/` only.
8. Run `restore_backup.py --run <id> --dest /tmp/check` → `RESTORE OK`.
9. Confirm TikTok/carrier/email remain blocked (spot-check logs: no external calls) — Safe Mode still enforced.

## Rollback plan
- **Instant disable (no deploy):** set `BACKUP_V2=0` (or unset) on staging → the gate returns `(False,"disabled")`, scheduler stops next boot; or redeploy the pre-merge staging revision `793f2ad`.
- **Code rollback:** revert the PR; the change is additive and flag-gated, so reverting restores prior behavior with no schema impact (ps_backup tables/objects are harmless if left).
- **No data risk:** backups are additive to a dedicated bucket; last-known-good prune protection prevents deleting the only verified run; in-app prune is OFF by default.

## GO / NO-GO
- **GO** to merge this PR to **staging** and activate via the plan above — **conditional on**: (a) credential rotation confirmed; (b) Bucket Lock + lifecycle created; (c) `R2_BACKUP_*` bucket-scoped and distinct from operational. All three are your actions.
- **NO-GO** for Production (separate prod bucket/token/lock, pre-deploy backup, prod restore test — out of scope here).

I implemented, tested, and verified; I did not push to a protected branch, merge, deploy, change Railway/R2 policy, disable Safe Mode, or touch Production.
