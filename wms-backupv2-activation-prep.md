# Backup V2 — Staging Activation Preparation

Live R2 validation (your Mac, synthetic data, bucket `packing-station-staging-backups`): **RESULT: PASS** (upload+manifest, verify, restore+integrity, corruption detection). Recorded as the real data-plane proof.

**No Production/Railway/Safe-Mode/deploy change was made. No secrets requested or printed.**

## 1. Latest staging revision & code — VERIFIED
- `origin/staging` = **`793f2ad`** (Merge PR #15). Backup V2 code present (`BACKUP_V2_ENABLED`, `_backup_v2_loop`, `_R2BackupStore`).
- Not yet in staging (local only, delivered as bundles): `629ff0c` (admin-status test) and `724afa7` (`r2_oneoff_validate.py`). These are optional follow-ups; activation does not require them.

## 2. Bucket Lock / lifecycle / deletion / coverage — AUDIT
- **Coverage (code `_backup_targets`):** `platform.db`, `users.json`, `stations.json`, and per-tenant `shipments.db` + `giveaways.db`. **Documented exclusions:** R2-hosted media (videos/photos/documents/labels — already durable R2 objects), per-org `documents.json`, `packing_log.csv`, `.login_attempts.json` (operational/ephemeral). Extendable on request.
- **Bucket Lock / lifecycle:** supported by R2 but **not yet configured** on `packing-station-staging-backups` (I can only create/list/get buckets via my tooling — not set lock/lifecycle or tokens). Must be set via dashboard/Wrangler before "real operation."
- **Deletion permissions:** in-app `retention_prune` issues DeleteObject only under `db-backups/`; `select_retained`+`verify_run` protect the newest and refuse to prune unless a VERIFIED known-good run remains.

## 3. Safe Mode cannot be bypassed by BACKUP_V2 — VERIFIED (important)
`_R2BackupStore()` is instantiated **only** inside `_backup_v2_run_once()`, called **only** from `_backup_v2_loop()`, which is started **only** by `if BACKUP_V2_ENABLED and not STAGING_SAFE`. Therefore, with Safe Mode ON:
- the V2 loop never starts, the store is never constructed, **zero external backup writes occur**;
- setting `BACKUP_V2=1` alone changes nothing externally — it is inert until Safe Mode is off.
**Conclusion:** enabling the flag cannot weaken or bypass Safe Mode. ✅

## 4. Validating the actual 6-hour scheduler — the key tension + safe design
**By design, the in-app V2 scheduler will NOT run while Staging Safe Mode is ON** (same gate as above). So "validate the real in-app 6h scheduler on staging" and "keep Safe Mode on" are mutually exclusive under the current code. Two honest paths:

- **(A) Validate cadence/leader/idempotence WITHOUT the app or touching Safe Mode (recommended now):** run `r2_oneoff_validate.py` (which exercises the *same* `ps_backup.run_backup/verify/restore/prune` code the scheduler calls) from an **external** 6-hour schedule for ~24–48h — e.g., a laptop `cron`, or a **Railway cron/one-off job that is a separate service** (not the web app), with the dedicated `R2_BACKUP_*` staging token + synthetic data under `db-backups/`. This proves 6h cadence, single-writer (point the job at one runner), retention tiers, last-known-good protection, and health — with Safe Mode untouched and the live app unchanged.
- **(B) Run the in-app scheduler on staging (requires a decision — approval boundary):** the scheduler only activates with Safe Mode off, which you've prohibited. The clean long-term fix is a **reviewed Cycle-7 code change**: allow the V2 backup loop to run even under `STAGING_SAFE` **only** when it uses the dedicated `R2_BACKUP_*` creds + dedicated bucket (backups to an isolated bucket with isolated least-priv creds can't reach prod data or customers, so they are legitimately "safe"). This is a security judgment + code change — **I will not implement it without your explicit approval.**

Recommendation: do **(A)** now to validate the scheduler behavior safely; decide on **(B)** as a small, reviewed Cycle-7 change if you want in-app scheduled staging backups.

## 5. Railway variables & credential separation
Set on **Staging only** (values via your secret store, never chat):
- `R2_BACKUP_BUCKET=packing-station-staging-backups`
- `R2_BACKUP_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
- `R2_BACKUP_ACCESS_KEY_ID`, `R2_BACKUP_SECRET_ACCESS_KEY` (the **bucket-scoped staging token** you created)
- `BACKUP_ALERT_EMAIL`, `BACKUP_MAX_AGE_SEC=25200`, `BACKUP_PRUNE_IN_APP` (0 if using lifecycle/lock; see §2)
- `BACKUP_V2` — leave **unset/off** until you choose path (B) and approve.

**Must remain separate from Production:** the `R2_BACKUP_*` token must be scoped to the **staging** backup bucket only and must NOT be a Production R2 token; the staging backup bucket must be distinct from Production's backup bucket (create a separate prod one later). Staging must keep `APP_ENV=staging` and must not receive Production TikTok/carrier creds for this work.

## 6. Health / alerts / restore / last-known-good — VERIFIED (sandbox + live upload path)
- `/api/ops/backup-status` is admin-only and leaks no secrets (tested: unauth≠200, worker 403, admin 200 with only flags/ids; test asserts no secret-ish strings).
- Failure alert → `_send_email(BACKUP_ALERT_EMAIL, …)`; staleness → `stale=true` when newest run older than `BACKUP_MAX_AGE_SEC`. Email is suppressed under `IS_STAGING`, so validation sends no real messages.
- Restore: `restore_backup.py` / `restore_run` download into an **isolated dir**, verify SHA-256 + `PRAGMA integrity_check`, and **refuse** the app data dir. Your live run confirmed restore+integrity and corruption detection PASS.
- Last-known-good: `retention_prune` always protects the newest run and refuses to delete unless a VERIFIED run remains (unit-tested + exercised in the 18-check runner).

## 7. Remaining security risks — ACTION REQUIRED
- **Previously exposed staging API token:** I have no record in my context of which token this was (I have never printed secrets), so I cannot confirm rotation. **Treat as a hard gate:** rotate any staging credential that was ever exposed (R2 staging token, and any TikTok/carrier/SMTP staging creds that may have been shared), confirm the old one is **revoked** in the provider dashboard, and ensure the new value exists only in Railway staging + your secret store. Do not reuse it in Production. Confirm completion before activation.
- The new `R2_BACKUP_*` token should be verified **bucket-scoped** (only `packing-station-staging-backups`) and **not** account-wide.

## 8. Activation checklist & GO/NO-GO

**Pre-activation (all must be observably true):**
- [ ] Staging safe-mode endpoint still `staging:true, safe_mode:true, external_calls_blocked:true`.
- [ ] `r2_oneoff_validate.py` live run = `RESULT: PASS` (done ✅).
- [ ] `R2_BACKUP_*` token confirmed **bucket-scoped** to the staging backup bucket; **not** a Production token.
- [ ] **Exposed staging token rotated + old one revoked** (point 7) — confirmed by you.
- [ ] Bucket Lock rule on `db-backups/` (retention ≥ weekly horizon) **and** a lifecycle expiry ≥ lock period configured on the staging backup bucket.
- [ ] `BACKUP_PRUNE_IN_APP` set consistently with the lock (0 if lock/lifecycle handles deletion).
- [ ] Decision recorded on path (A) external-scheduler vs (B) in-app carve-out.

**GO / NO-GO:**
- **GO — set the staging `R2_BACKUP_*` + `BACKUP_ALERT_EMAIL`/age vars and run validation path (A)** (external 6h runner, synthetic data): low-risk, Safe Mode stays on, app unchanged, no deploy. This proves the scheduler behavior for real.
- **NO-GO — enabling the in-app scheduler on live staging (path B)** until: you approve the reviewed carve-out code change (or accept running staging with Safe Mode off, which you've prohibited); token rotation is confirmed; and Bucket Lock + lifecycle are in place. Enabling `BACKUP_V2=1` with Safe Mode on is harmless but a **no-op** (won't actually back up), so it is not "real operation."
- **NO-GO — any Production activation:** separate prod bucket + prod least-priv token + prod Bucket Lock + the one-time pre-deploy backup + a real prod restore test, none of which are done.

**What needs your authorized action (none are code I can run):** rotate+revoke the exposed token; create Bucket Lock + lifecycle on the staging backup bucket; set the staging Railway vars; choose path (A)/(B); and — only if (B) — approve the carve-out change. I will prepare the carve-out as a reviewed, flagged change on request, but will not implement, deploy, enable scheduled external writes, or disable Safe Mode without your explicit go.
