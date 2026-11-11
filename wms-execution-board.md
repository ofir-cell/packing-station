# WMS Chief-of-Staff — Execution Board

## Cycle 5 — close remaining P0/P1 risks (hardening before features)

Baseline: deployed **Cycle-4** code (`cycle4/qa` @ 5445426; live safe-mode endpoint confirmed staging=true, safe_mode=true, external_calls_blocked=true).
Consolidated release branch: **`cycle5/app` @ 14d5bc7** · Bundle: `cycle5-review-14d5bc7.bundle`
Gates: `py_compile` ✅ · `check_js` ✅ (63/63) · **full suite 96 passed / 0 failed** (89 prior + 7 new).

No push / merge / deploy / Railway change / real-carrier / real-TikTok / real-customer action taken.

### Scope of testing — sandbox vs. live
**Automated sandbox (what I ran):** all 96 tests against a throwaway per-run SQLite `DATA_DIR`, external services never contacted. Includes a **15-station concurrency simulation** (15 threads: duplicate pick + duplicate pack per order) asserting every order ends `packed` with exactly one unit deducted — no double-deduct, no lost deduction.
**Live Staging (what I did NOT do):** no tests against live Staging; no Staging/production data read or written. Only live evidence remains the safe-mode endpoint you reported.

---

### Remaining P0/P1 risks — now CLOSED

| # | Was | Severity | Fix shipped on this branch | Owner | Evidence |
|---|-----|----------|----------------------------|-------|----------|
| **S2** | Temp password stored **plaintext at rest + in R2 backups**, and (post-AUDIT#6) never shown → handoff silently broken | **P1** | No plaintext is persisted anywhere; users.json keeps only the bcrypt hash. New true-admin `POST /api/hires/<id>/issue-temp-password` reveals a fresh password **once** for the handoff; UI button replaces the dead field. Boot migration **purges legacy plaintext** from existing rows (and future backups) | Security | `test_issue_temp_password_once_and_not_stored`, `test_issue_temp_password_requires_true_admin`, `test_boot_migration_purges_legacy_plaintext` |
| **E5** | Public (lead/apply) rate limiter was **in-memory per worker** → 4 workers = 4× the intended limit on unauthenticated endpoints | P2 | Backed by a shared `rate_hits` table in platform.db under a cross-process lock; in-memory fallback only if the DB is briefly unavailable | Integrations | `test_rate_limiter_blocks_at_limit`, `test_rate_limiter_is_db_backed_shared` |
| **E6** | `_tracking_loop` leader election had a **TOCTOU** — two workers could both pass the staleness check and double-run the batch | P2 | Check-and-claim of the marker now happens inside one cross-process `_flock`, so exactly one worker runs it | Integrations | code (daemon; not unit-tested — see risks) |
| **E-ups** | `_ups_buy` accepted an idempotency key but **ignored it** | P2 (verify) | Key is stamped into UPS `CustomerContext` for retry correlation; documented that UPS has no native idempotency, so the authoritative no-double-buy guarantee remains the DB claim in `_buy_label_idempotent` (already tested) | Engineering | code + existing `test_label_idempotency` |
| **C4-2** | A handler raising **mid-transaction without rollback** could hold the SQLite write lock until GC (stalling other workers up to the 60 s busy-timeout) — 37 handlers committed with no `finally`/`except` | P2 | Request-scoped connection tracking (`sdb`/`gdb`/`pdb` register on `g`) + a `teardown_request` that rolls back and closes anything left open on the error path. Systemic — covers all 37 | Engineering | `test_teardown_closes_leaked_connection` |

Carrier idempotency + uncertain outcomes (the earlier A-workstream): re-confirmed intact — the DB-level atomic claim and the admin-authoritative `/api/label/resolve` (Cycle 3) remain the guarantees; UPS/ShipStation now both thread the idem key.

---

### Unresolved risks (nothing P0/P1 open)

- **E6 verification gap (P3):** the tracking-loop fix is in a daemon thread and is covered by code review only — no automated multi-process test here. Recommend observing staging logs after deploy to confirm a single leader per cycle.
- **E-ups (P3):** UPS lacks true idempotency; our guarantee is the DB claim. If UPS later exposes an idempotency header, thread it through. Live verification needs a real UPS sandbox (not done; no live carrier calls authorized).
- **UI polish (P2/P3):** remaining worker strings outside the ES `t()` dictionary; a few native `confirm()` dialogs; hardcoded hex in Match-Live.
- **Device regression (P2):** the Q1 pack resolver and the new pack error screen are covered by automated/logic tests; a real-iPad scan session is still unverified here.

---

## GO / NO-GO assessment

### Staging — **GO**
Low-risk, hardening-only cycle on top of already-deployed Cycle-4: one new admin endpoint, one security redesign that *removes* stored secrets, three concurrency/limiter hardenings, and a systemic rollback safety net. 96/96 green incl. a 15-station race. Recommend promoting `cycle5/app` @ 14d5bc7 to Staging and watching: safe-mode endpoint still true; tracking-loop logs show a single leader; issue-temp-password returns a password and login works with it.

### Production — **NO-GO (conditional)** until the following are satisfied:
1. **Soak on Staging** of this build (recommend ≥ 48 h) with real multi-worker traffic, confirming no lock-stall warnings and correct inventory under live packing load.
2. **S2 operational rollout:** confirm the admin "Issue temporary password" flow with a real hire, and confirm the legacy-plaintext purge ran against the production hire table (check `provisioned_password IS NULL` for all rows) — then rotate any R2 backups that still contain old plaintext.
3. **Device pass on a real iPad** for pick→scan→pack incl. the Q1 resolver and the pack error screen.
4. **A deliberate go-live safety-mode review:** production is NOT in STAGING-SAFE, so external side effects (USPS/UPS/ShipStation, TikTok, R2, emails) are LIVE. A final review that the idempotency/uncertain-outcome paths behave against real carriers (in a controlled, low-volume window) is required before trusting label purchases at scale.

None of the four are code blockers on this branch — they are deployment/validation gates appropriate to production.

---

## Exact release steps (run where the repo has push rights)

```bash
cd packing-station
# stack prior RCs if staging isn't already at them:
git fetch /path/to/cycle3-review-c2373a3.bundle cycle3/review:cycle3/review
git fetch /path/to/cycle4-review-5445426.bundle  cycle4/qa:cycle4/qa
# this cycle:
git fetch /path/to/cycle5-review-14d5bc7.bundle  cycle5/app:cycle5/app
git log --oneline cycle4/qa..cycle5/app        # review the single hardening commit + tests
git push origin cycle5/app                      # opens/updates the PR -> Railway auto-deploys staging
# post-deploy smoke (read-only):
#   GET /api/ops/safe-mode -> staging:true, safe_mode:true, external_calls_blocked:true
#   Hire detail -> "Issue temporary password" -> returns a password; log in with it once
#   platform.db has a rate_hits table; lead/apply endpoints throttle across workers
#   tracking-loop logs show one leader per cycle
```

Nothing ships without your approval.
