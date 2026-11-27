# Backup V2 Staging Activation — Status & PASS/FAIL

**I must STOP before activation.** Two independent prerequisites are not satisfiable by me: (a) I cannot verify the R2 credential rotation/scope (no secret access, by rule), and (b) I have **no Railway access**, so I cannot set the Staging variables or read the live `/api/ops/*` endpoints. I verified everything else that's reachable. No Production/`main`/operational-bucket/Safe-Mode change was made; no secrets printed or requested.

## PASS / FAIL

| Area | Result | Evidence / why |
|---|---|---|
| **Deployment (PR #16 in staging)** | **PASS** | `origin/staging` = `4f7e55e` ("Merge PR #16"); carve-out `714cc8a` is an ancestor. Re-verified via fresh read-only clone. |
| **Production untouched** | **PASS** | `origin/main` = `63181d1` (unchanged); no V2 code on main. |
| **Credential security (rotation + revocation + bucket-scope)** | **BLOCKED — cannot verify** | No token-introspection tool; I never retrieve secrets. Must be confirmed by you (exact steps below). |
| **R2 protection policies (lock 7d + lifecycle 45d on `db-backups/`)** | **USER-REPORTED — not tool-verifiable by me** | You configured them and the dashboard screenshot showed them being added; my R2 tools are management-plane only (`bucket_get` exposes no lock/lifecycle fields). |
| **Railway Staging variables** | **BLOCKED — no access** | No `railway` CLI, no `RAILWAY_*` token, no Railway MCP in this environment. Cannot set vars. |
| **Safe Mode still active** | **PENDING (code-guaranteed, needs live check)** | Code: scheduler can't unblock anything but backups; `/api/ops/safe-mode` must be checked in an admin session (I can't auth). |
| **Exactly one scheduler running** | **PENDING activation** | Code-verified single-leader (flock) + mutual exclusion; needs the live run to observe. |
| **First real backup to the bucket** | **NOT DONE** | Requires activation; I will not claim success from local/synthetic tests. |
| **Restore from a real Staging backup** | **PENDING** (synthetic restore already PASS) | Real-backup restore runs after the first live run. |
| **Monitoring / failure alerts** | **PENDING activation** | `/api/ops/backup-status` + `BACKUP_ALERT_EMAIL`; verify after activation. |
| **First backup timestamp** | **N/A — none yet** | No real run has occurred. |

## Access determination (requirement 4)
Railway access is **NOT available** here: no CLI, no API token, no connected Railway tool. Therefore steps 5, 7, 8, 9, 10, 11 cannot be executed by me. Cloudflare access is **management-plane only** (can't read lock/lifecycle or tokens). GitHub is **read-only** (verified via clone/fetch).

## The exact actions required from you (shortest secure path)
1. **Confirm credential security** (no secrets in chat): in R2 → Manage API Tokens, verify the **old token is revoked/absent** and the **new token is scoped to `packing-station-staging-backups` only**. Non-secret runtime proof: a cross-bucket `head-bucket packing-station` with the new token must return **403**.
2. **Set these Staging-only Railway variables** (service `authentic-curiosity`), values from your secret store:
   ```
   BACKUP_V2=1
   R2_BACKUP_BUCKET=packing-station-staging-backups
   R2_BACKUP_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
   R2_BACKUP_ACCESS_KEY_ID=<new staging backup token key>
   R2_BACKUP_SECRET_ACCESS_KEY=<new staging backup token secret>
   BACKUP_ALERT_EMAIL=<approved recipient>
   BACKUP_MAX_AGE_SEC=25200
   BACKUP_PRUNE_IN_APP=0
   ```
   Keep `APP_ENV=staging`; do **not** set `STAGING_ALLOW_EXTERNAL`.
3. **Post-deploy checks** (in an admin session):
   - `GET /api/ops/safe-mode` → `staging:true, safe_mode:true, external_calls_blocked:true`.
   - `GET /api/ops/backup-status` → `enabled:true, permitted:true, backup_only_exception_active:true, safe_mode:true, prune_in_app:false`.
   - Logs show exactly one `[backup-v2] scheduler started …` (no legacy line).
4. **First run + evidence:** the scheduler runs every 6h. Either wait for the first tick or observe the first `[backup-v2] ok run=<ts> files=N`; confirm `db-backups/<run_id>/` + `manifest.json` appear in the bucket; then `python3 restore_backup.py --run <run_id> --dest /tmp/check` → `RESTORE OK`. Send me the `run_id`/timestamp + the two endpoint JSONs and I'll complete the verification table with real evidence.

**Alternatively**, provision a scoped **Railway API token** (and I'll use `npx @railway/cli`) and read access to the live endpoints, and I can drive steps 5/7/8/9 directly — but that's your credential decision; I won't request the secret in chat.

## Remaining blockers (ranked)
1. **Credential rotation/scope unverified** → confirm (step 1). *Hard gate.*
2. **No Railway access** → set vars (step 2) or grant me a scoped token. *Hard gate.*
3. R2 lock/lifecycle not tool-verifiable → your screenshot/confirmation stands as evidence.

Until 1 and 2 are resolved, Backup V2 is **NOT activated** and no real backup has run. I did not relax any security control, change Production, or disable Safe Mode.
