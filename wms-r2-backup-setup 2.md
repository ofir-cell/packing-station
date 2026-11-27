# R2 Staging Backup Readiness — Setup Instructions & Blockers

## 1. Commit & bundle facts (verified)
- Test commit **`629ff0c`** — parent = **`3394cd8`** (the PR #15 tip, which is in `origin/staging` `793f2ad`).
- Bundle on record: **`cycle7prep-backup-validated-629ff0c.bundle`**.
- This session also added `r2_oneoff_validate.py` → latest branch tip **`724afa7`**, bundle **`cycle7prep-backup-r2ready-724afa7.bundle`** (delta from PR #15).

## 2. Is `629ff0c` test-only? YES
`git show --stat 629ff0c` = **1 file changed, +31 lines**: `tests/test_cycle7_backup_status.py` only. **No change to `app.py`, `templates.py`, `ps_backup.py`, or `restore_backup.py`.** Zero production/runtime behavior change — it only adds an admin-auth + no-secret-leak test for `/api/ops/backup-status`.

## 3. Create a bucket-scoped S3 API token (Cloudflare dashboard)
R2 → **Overview** → Account Details → **API Tokens** → **Manage** → **Create Account API token**:
1. **Permissions:** select **Object Read & Write** (see §6 — this is the minimum that can write; R2 has no "write-only").
2. **Scope to buckets:** choose **Apply to specific buckets only** → select **only** `packing-station-staging-backups`.
3. (Optional) set a TTL / expiration.
4. **Create** → copy the **Access Key ID** and **Secret Access Key** once (the Secret Access Key is the SHA-256 of the token value). Store them in your secret manager — **do not paste them into chat**.
5. For the restore/verification operator, optionally create a second token with **Object Read only** scoped to the same bucket.

The S3 endpoint is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` (per the R2 docs).

## 4. Exact env var names the code reads (set the values in your secret store, not chat)
From `app.py`:
- `R2_BACKUP_BUCKET` → `packing-station-staging-backups`
- `R2_BACKUP_ENDPOINT` → `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
- `R2_BACKUP_ACCESS_KEY_ID`
- `R2_BACKUP_SECRET_ACCESS_KEY`

Behavior flags (not secrets): `BACKUP_V2` (leave unset/off for now), `BACKUP_PRUNE_IN_APP`, `BACKUP_ALERT_EMAIL`, `BACKUP_MAX_AGE_SEC`. (If `R2_BACKUP_*` are unset, the code falls back to the main `R2_*`; for isolation, set the dedicated ones.)

## 5. One-off LIVE-R2 backup + restore with Safe Mode kept ON
Safe Mode only blocks the **deployed app's own** threads; a separate process is unaffected. So run the validation **outside** the app — no Safe Mode change, no real Staging data, synthetic only:
1. On a trusted machine/one-off shell (local, or `railway run` against staging — your call), export the four `R2_BACKUP_*` values for the **staging backup token**.
2. Run `python3 r2_oneoff_validate.py` (in the bundle). It writes SYNTHETIC SQLite under the isolated `validation/` prefix, then: upload → `verify_run` (manifest + object sizes) → isolated restore + `PRAGMA integrity_check` → corruption detection → best-effort cleanup.
3. Expect `RESULT: PASS`. It never touches `db-backups/`, operational prefixes, real data, or the running app.

To additionally confirm the **deployed app** path later (separate, requires enabling V2 on staging), set `BACKUP_V2=1` + the vars and check `/api/ops/backup-status` → `enabled:true, last_ok:true, stale:false` — that is a deploy/approval step, not part of this one-off.

## 6. Token permissions vs. code — compatibility (important correction)
The code's S3 operations by path:
- `run_backup` → **PutObject** + **HeadObject** (post-upload size verify).
- `verify_run` → **GetObject** (manifest) + **HeadObject**.
- `list_runs` → **ListObjectsV2 / ListBucket**.
- `restore_run` → **GetObject**.
- `retention_prune` (only if `BACKUP_PRUNE_IN_APP=1`) → **ListBucket** + **GetObject** + **HeadObject** + **DeleteObject**.

**A write-only credential is NOT sufficient, and R2 doesn't offer one.** R2 dashboard token scopes are `Object Read only` (read+list), `Object Read & Write` (read+write+list+**delete**), and the admin variants — there is no write-without-read or write-without-delete scope. Therefore:
- **Simplest:** one **`Object Read & Write`** token scoped to the backup bucket → supports upload, size-verify, list, restore, and in-app prune (`BACKUP_PRUNE_IN_APP=1`).
- **Least-privilege without app delete:** set `BACKUP_PRUNE_IN_APP=0` and let **R2 handle retention** (§7). The app still needs read+write+list, so the dashboard minimum is still `Object Read & Write`; to truly deny delete you must use an **actions-scoped temporary credential** = `["PutObject","GetObject","HeadObject","ListBucket"]` (R2 temporary-credentials support per-action lists). Operator restore uses a separate `Object Read only` token.

## 7. Versioning / Object Lock / Lifecycle — what R2 actually supports (docs, Oct 2026)
- **Bucket Lock = supported** (dashboard / Wrangler / API): WORM-style retention by age or indefinite, optionally per prefix — real protection against deletion/overwrite. Use it on `db-backups/` (e.g. retain ≥ your weekly horizon). This is the correct "accidental-deletion protection."
- **Object Lifecycle rules = supported**: age-based expiry — use for automatic retention cleanup instead of in-app delete.
- **Object versioning:** not confirmed in the docs I checked; **do not rely on it** — use **Bucket Lock + Lifecycle** as the supported alternative.
- **Interaction to respect:** Bucket Lock will **deny** deletes within the retention window. If you enable Lock, set `BACKUP_PRUNE_IN_APP=0` and tune a Lifecycle expiry ≥ the lock period (otherwise in-app prune delete calls get denied — the code catches and continues, and the last-known-good guard means no data loss, but you'd get noisy errors).
- **Setup path:** dashboard (bucket → Settings → Bucket lock rules / Object lifecycle rules) or `npx wrangler r2 bucket lock add` / `r2 bucket lifecycle add`. My available R2 tooling is management-plane (create/list/get bucket) only — I cannot set Lock/Lifecycle or issue tokens; those need the dashboard/Wrangler and touch security policy (your action).

## 8. Minimal validation checklist (observable PASS/FAIL)
| # | Check | How | PASS |
|---|---|---|---|
| 1 | Token is bucket-scoped | dashboard token shows only `packing-station-staging-backups` | only that bucket listed |
| 2 | Upload works | run `r2_oneoff_validate.py` | `PASS upload+manifest` + a run_id |
| 3 | Manifest + size verify | same run | `PASS verify: ok` |
| 4 | Restore + integrity | same run | `PASS restore+integrity` |
| 5 | Corruption detected | same run | `PASS corruption detected` |
| 6 | Overall | same run | `RESULT: PASS` |
| 7 | Isolation | R2 browser | objects only under `validation/` (and later `db-backups/`), never operational prefixes |
| 8 | Shared buckets untouched | `r2 buckets list` | `packing-station` + `packing-station-hr` unchanged |
| 9 | Deletion protection live | bucket Settings | a Bucket Lock rule on `db-backups/` is present |
| 10 | App status (after V2 enabled on staging) | `GET /api/ops/backup-status` | `enabled:true, last_ok:true, stale:false` |

## Remaining blockers (all require your authorized action; none are code)
1. **Create the bucket-scoped S3 token** (§3) — dashboard; secret, not shareable to me.
2. **Set the `R2_BACKUP_*` env** on the runner/Staging (§4) — I must not set Railway vars or handle secrets.
3. **Run `r2_oneoff_validate.py`** with that token (§5) — needs the secret; I have no R2 data-plane creds, so I cannot execute the live run (I will not claim it passed until you do and share the output).
4. **Enable Bucket Lock + Lifecycle** on the backup bucket (§7) — dashboard/Wrangler; security policy.
5. **Enabling `BACKUP_V2` on Staging** and the deploy of follow-up commits — your push/deploy approval.

I created the dedicated bucket and verified the commit/code; everything above is the exact handoff. No Production/Railway/push/merge/deploy changes were made, Safe Mode was not touched, no credentials were requested or exposed.
