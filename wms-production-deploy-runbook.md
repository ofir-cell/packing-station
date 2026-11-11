# Production Deployment Readiness Runbook — Cycles 1–6

**Status: NOT AUTHORIZED. Prepared for your review. No push/merge/deploy/Railway/DB/TikTok/carrier change was made.**

## Verified facts (read-only, against the real remote — fetched this session)
- **Production** `origin/main` = **`63181d1`** ("Merge staging: cancellations register on first upload").
- **Deployable revision** `origin/staging` = **`c2b4088`** ("Merge PR #14 from cycle6/work") — **contains all of Cycles 1–6** (R1 webhook-auth `860d999`, security `c91a858`, Cycles 2–5, Cycle 6 `2a6360e` all confirmed ancestors).
- `origin/main` is a **direct ancestor** of `origin/staging` → promotion is a **clean fast-forward** (no divergence, no conflicts, no cherry-pick).
- `c2b4088` is **tree-identical** to the locally validated `2a6360e`; full suite **99/99 PASS**, `py_compile` + `check_js` clean, on the exact deployable tree.

## What this release fixes in Production (from the audit)
- **P-1 Critical:** `main` computes but **does not enforce** the webhook signature → forged webhook can deactivate the shop / trigger ingests. Fixed by R1.
- **P-2 High:** `main` lacks `req_true_admin` (server-side admin gate) → manager/CS escalation. Fixed by W4.
- Plus: carrier idempotency, atomic deduct-once, shared rate limiter, session revocation, 429 backoff, conn-teardown.

## Production data to back up (Railway persistent volume, `DATA_DIR`)
Per code: `DATA_DIR` holds `platform.db`, `users.json`, `stations.json`, `.login_attempts.json`, and per tenant `DATA_DIR/orgs/<org>/` → `shipments.db`, `giveaways.db` (+ media: videos/photos/documents, `packing_log.csv`). **All SQLite DBs run in WAL mode** — a plain file copy can miss the WAL; use the SQLite backup API.

## Startup side-effects when the new code first boots (be aware, all idempotent/additive)
- `pdb_init()` + per-org `sdb_init`/`gdb_init` run additive `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN` (new: `rate_hits`, `label_purchases` created lazily).
- **One-way data migration:** `UPDATE new_hires SET provisioned_password=NULL` runs per org at boot (removes an unused, already-redacted secret — irreversible, benign).
- Daemon threads start: cleanup, tracking, backup, TikTok sweep (all already run in production today — nothing new).
- No user seeding (only if `users.json` were missing — it isn't in prod).

## Configuration that MUST be correct in Production (verify, do not change blindly)
- `APP_ENV` **unset or ≠ staging** → `STAGING_SAFE=false` → external integrations LIVE (correct for prod).
- `STAGING_ALLOW_EXTERNAL` **unset**. `TIKTOK_WEBHOOK_ALLOW_UNSIGNED` **unset/false** → webhook signatures **enforced** (the P-1 fix).
- Existing live secrets (TikTok, USPS/UPS/ShipStation, R2, Resend, `SECRET_KEY`, `DATA_DIR`) **unchanged**.

---

# ONE-PAGE DEPLOYMENT RUNBOOK (with GO/NO-GO checkpoints)

> Deploy mechanism: Railway auto-deploys the `main` branch. Promotion = fast-forward `main` → `c2b4088` and push. **You run these; I do not.**

**0. Schedule** — off-peak, **no active LIVE selling**, on-call engineer present. ⛔ NO-GO if a LIVE is running.

**1. Pre-flight (read-only)**
- `git fetch origin && git rev-parse origin/main origin/staging` → main=`63181d1`, staging=`c2b4088`.
- `git merge-base --is-ancestor origin/main origin/staging && echo FF-OK` → must print `FF-OK`.
- Confirm staging smoke is green on Railway staging (`/api/ops/safe-mode` → `staging:true`).
- ✅ **GO/NO-GO #1:** ancestry = fast-forward AND staging healthy.

**2. Backup (verifiable; on the Railway volume via a shell/one-off)**
- For each DB: `sqlite3 <file> ".backup '/backups/<ts>/<file>'"` (platform.db, users.json copied as-is, and every `orgs/<org>/shipments.db` + `giveaways.db`).
- Verify each backup: `sqlite3 <backup> "PRAGMA integrity_check;"` → `ok`; and compare key row counts to live (`SELECT COUNT(*) FROM shipments;` etc.).
- Record pre-deploy counts: shipments, shipment_items, products (on_hand sums), tiktok_events MAX(received_at).
- ✅ **GO/NO-GO #2:** every backup `integrity_check=ok` and counts captured. ⛔ NO-GO if any backup fails.

**3. Promote**
- `git checkout main && git merge --ff-only origin/staging` then `git push origin main` (fast-forward only).
- Railway builds & deploys `main`.
- ✅ **GO/NO-GO #3:** build succeeds; app boots; logs show the per-org migrations completing without `OperationalError`.

**4. Smoke tests — first 15 minutes (read-only; NO fulfillment/label/cancel writes)**
- **Webhook auth (the P-1 proof):** send an **unsigned** POST to `/api/tiktok/webhook` → expect **401** (prod previously returned success). Do not send forged signed payloads.
- **Ingestion alive:** `/api/tiktok/status` → shops active, `event_count` rising, `paused=false`, expected `cutover`.
- **Sweep healthy:** logs show `sweep ingested N order(s)`, no `token refresh`/`sweep failed` errors.
- **Auth gate (P-2 proof):** a manager session on `/api/users` and `/api/profit` → **403**.
- **Safe-mode inert in prod:** `/api/ops/safe-mode` → `staging:false`.
- **Inventory sane:** no negative `on_hand`; `rate_hits` table exists in platform.db.
- ✅ **GO/NO-GO #4:** all six pass. ⛔ else → Rollback (step 7).

**5. First 1 hour** — watch: webhook-401 rate (should be ~0 from TikTok), 429/5xx + retry lines, ingestion lag (`MAX(tiktok_events.received_at)` vs now), order→shipment creations continuing, no `database is locked` spike, no negative inventory.

**6. First 24 hours** — token-refresh success (no silent stop), sweep cadence steady, inventory reconciles against TikTok, no new error class, label purchases (if any) show single `label_purchases` rows (no double-buy).

**7. Rollback / forward-recovery**
- **Rollback:** redeploy previous image or `git push origin main --force-with-lease` back to `63181d1`. Schema is additive → old code safely ignores `rate_hits`/`label_purchases`; the `provisioned_password` purge does not reverse (acceptable). Restore a DB from step-2 backup only if data corruption is observed.
- **Forward-recovery (preferred for sync hiccups):** the TikTok sweep re-ingests idempotently; a missed window self-heals on the next poll. Keep backups 14 days.

**Alert thresholds:** webhook-401 > 5/min · token-refresh failure ≥ 1 · ≥ 3 consecutive sweep failures · ingestion lag > 10 min during a LIVE · any `on_hand < 0`.

---

## Remaining blockers that CANNOT be verified without authorized Production access
1. **Live backup execution & integrity** — I cannot touch the Railway volume; you (or DevOps) must run and verify step 2.
2. **Actual production env values** — I can't read Railway env; confirm `APP_ENV`, `TIKTOK_WEBHOOK_ALLOW_UNSIGNED`, `STAGING_ALLOW_EXTERNAL` per the config section.
3. **Runtime confirmation of the P-1/P-2 fixes post-deploy** — the unsigned-webhook→401 and manager→403 checks must be run against the live URL after deploy.
4. **Current production DB health** — pre-deploy `integrity_check` and the `provisioned_password` count are only observable with live DB access.
5. **The deploy/push itself** — requires your explicit authorization; Railway settings and the `git push origin main` are yours to execute.

## What YOU must personally verify before authorizing deployment
- [ ] `origin/main`=`63181d1`, `origin/staging`=`c2b4088`, ancestry = fast-forward (`FF-OK`).
- [ ] Staging is healthy and is the revision you intend to ship (PR #14 merged).
- [ ] A **verified** backup of every production DB exists (`integrity_check=ok`) and pre-deploy counts recorded.
- [ ] Production env: `APP_ENV`≠staging, `STAGING_ALLOW_EXTERNAL` unset, `TIKTOK_WEBHOOK_ALLOW_UNSIGNED` unset.
- [ ] Off-peak window, no active LIVE, on-call present, rollback to `63181d1` understood.
- [ ] You accept that tracking-push, TikTok labels, and TikTok combine are **NOT** in this release (Cycle 7, pending William).

*On your explicit "go", the only action is the fast-forward promote + push of `main` to `c2b4088`; everything else here is verification. I will not push/merge/deploy or change Railway without that approval.*
