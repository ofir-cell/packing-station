# Cycle 7 / Backup V2 — Deployment Readiness (independently verified)

Verified against the real GitHub remote and Cloudflare this session. No merge/deploy/Railway/R2-policy/Production change. No secrets requested or shown.

## GitHub branch & PR
- **Branch (exists on GitHub):** `cycle7/backup-safe-exception` — your push **succeeded**.
- **Verified remote tip SHA:** `714cc8a39f019736d602418e2eabed9ba544036f` (`714cc8a`) — exact match to the reviewed commit.
- **Contains expected content:** PR #15 content (`3394cd8`) is in the branch ancestry; merge-base with staging = `3394cd8`.
- **PR adds 3 commits** over `staging`: `714cc8a` (carve-out), `724afa7` (live-R2 runner), `629ff0c` (admin-status test). Diff = `app.py` (+54/−9, the carve-out only) + `r2_oneoff_validate.py` + 3 test files (291 insertions total).
- **Mergeability:** local throwaway merge into `origin/staging` = **CLEAN, no conflicts** (fast-forward-friendly).
- **PR URL / create (needs you — see access limit):** no PR exists via my tools to confirm, and I cannot open one (no GitHub API/`gh`/connector). Open in one click:
  `https://github.com/ofir-cell/packing-station/compare/staging...cycle7/backup-safe-exception?expand=1`
- **CI:** the repo has **no `.github/workflows`** → **zero configured checks**. This is *not* "CI passing" — there is no CI. The evidence of correctness is the local suite below.

## Test results (branch HEAD `714cc8a`)
- **Full suite: 122 passed / 0 failed.** Gates: `py_compile` + `check_js` (63/63) clean.
- Safe Mode isolation + fail-closed subset: **8 passed** (run explicitly).

## Security & configuration audit
| Item | Status | Evidence / limit |
|---|---|---|
| Staging Safe Mode enabled | **VERIFIED (code) / your report (live)** | isolation proof boots app with `APP_ENV=staging` → `STAGING_SAFE=True`; you confirmed the live endpoint earlier |
| Backup V2 default OFF | **VERIFIED** | `BACKUP_V2` unset → `_backup_v2_permitted()` returns `(False,"disabled")`; scheduler doesn't start |
| Backup-only exception fails closed | **VERIFIED** | 7-case matrix: disabled / no bucket / bucket==operational / missing creds / creds==operational → refused; `_R2BackupStore` raises without dedicated creds |
| Exception unblocks ONLY backups | **VERIFIED** | subprocess proof: under Safe Mode `_tt_request→'SAFE_MODE'`, `_can_buy_labels→False`, `permitted→(True,'ok')` |
| Dedicated R2 staging bucket exists | **VERIFIED** | `packing-station-staging-backups` (ENAM, Standard), created 2026-10-27; distinct from `packing-station` / `packing-station-hr` |
| Bucket Lock present | **CANNOT VERIFY (tool limit) → assume ABSENT** | my Cloudflare tools are bucket create/list/get only; `bucket_get` returns no lock fields |
| Lifecycle policy present | **CANNOT VERIFY → assume ABSENT** | same limit |
| Backup token scoped to the bucket | **CANNOT VERIFY** | no token-introspection tool; you created it bucket-scoped per the dashboard steps |
| Exposed R2 creds rotated & revoked | **CANNOT VERIFY** | no secret access by design; **must be confirmed by you** |
| Railway staging config | **CANNOT VERIFY (no Railway tool)** | no Railway MCP/CLI connected; rely on dashboard + post-deploy `/api/ops/*` |

## Deployment readiness (Phase 3)
- Single-leader scheduling: `flock(LOCK_EX|LOCK_NB)` on `.backupv2.guard`; 6h `.backupv2_last` marker → one backup/interval across processes & restarts. (code-verified; exercised by ps_backup tests)
- Backup integrity/restore/alerts/rollback: consistent online-backup snapshots + manifest + SHA-256 + `integrity_check`; isolated restore refuses the data dir; failure + staleness via `/api/ops/backup-status`; rollback = `BACKUP_V2=0` (no deploy) or revert PR (additive, no schema risk). Your live-R2 run earlier returned `RESULT: PASS`.
- Prune default **OFF** until Bucket Lock + lifecycle exist.

### Exact Railway env for Staging (set values in your secret store, not chat)
`BACKUP_V2=1` · `R2_BACKUP_BUCKET=packing-station-staging-backups` · `R2_BACKUP_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com` · `R2_BACKUP_ACCESS_KEY_ID=…` · `R2_BACKUP_SECRET_ACCESS_KEY=…` · `BACKUP_ALERT_EMAIL=…` · `BACKUP_MAX_AGE_SEC=25200` · `BACKUP_PRUNE_IN_APP` unset/`0`. Keep `APP_ENV=staging`; do **not** set `STAGING_ALLOW_EXTERNAL`; do not set any of these on Production.

## GO / NO-GO
**GO to merge the PR into `staging` and activate — conditional on the 5 approval actions below.** Code is correct, isolated, fail-closed, clean-merging, 122/122. The only unverifiable items are infra protections and rotation, which are your actions.
**NO-GO** for Production (separate prod bucket/token/lock + pre-deploy backup + prod restore test — out of scope).

## Remaining blockers = smallest set of actions requiring you
1. **Open the PR** (compare URL above) — I can't via available tools.
2. **Confirm the previously-exposed R2 credential is rotated + the old one revoked** (dashboard; I can't see secrets).
3. **Create Bucket Lock (prefix `db-backups/`, retention ≥ weekly) + lifecycle expiry** on `packing-station-staging-backups` (dashboard or `wrangler r2 bucket lock add` / `lifecycle add`).
4. **Confirm the `R2_BACKUP_*` token is bucket-scoped** to that bucket (not account-wide).
5. **Approve merge + set the staging Railway vars** (then optionally `BACKUP_V2=1` to activate). Merge/deploy/Railway changes remain yours.

## Access limitations & shortest workarounds
- **No GitHub API / `gh` / connector** → can't open/query the PR. Workaround: the one-click compare URL.
- **Cloudflare tools = bucket management only** → can't read/set Bucket Lock, lifecycle, versioning, or token scope. Workaround: dashboard, or `npx wrangler r2 bucket lock add` / `lifecycle add`.
- **No Railway MCP/CLI** → can't read/set Railway config. Workaround: dashboard; verify post-deploy via `/api/ops/safe-mode` and `/api/ops/backup-status`.
- **No R2 S3 data-plane creds in sandbox** → can't run live backup here (already done on your Mac: PASS).
