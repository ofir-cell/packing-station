# Production TikTok Integration Audit & Safe Rollout Plan (READ-ONLY)

Prepared before Cycle 7. **No code, Git remote, Railway, env, DB, carrier, or TikTok change was made.** This is analysis only.

## Scope & honesty boundary
I have **no access to the Production runtime** — no Railway logs, no live database, no API telemetry, and the remote `origin/staging` (the PR #13 revision actually deployed) is **not fetched into this environment**. Therefore:
- Everything about **live behavior** (volumes, latency, actual intervals, error/429 rates, token refresh events, which scopes are actually granted) is **UNVERIFIED** and marked so. I do **not** infer runtime behavior from code.
- All **code/Git facts** below are verified against the local repository: Production `main` = `origin/main` = **`63181d1`**; the improvement stack tip = **`cycle6/work` @ 2a6360e**; 26 commits separate them.
- `origin/staging` locally resolves to `b6f3c37` (stale clone-time ref). The actually-deployed staging from PR #13 could differ; treat staging-diff claims as "based on the local cycle branches the bundles were built from," pending a fetch.

---

## Deliverable 1 — Current Production TikTok API capability matrix (from `main` @ 63181d1 code)

| Capability | In production code? | Read/Write | Notes |
|---|---|---|---|
| OAuth token exchange / refresh | Yes (`_tt_token_exchange`, `_tt_token_refresh`, `_tt_valid_token`) | external read | **No** retry/backoff on 429/5xx (added only in Cycle 6) — UNVERIFIED live impact |
| Request signing (HMAC-SHA256) | Yes (`_tt_sign`) | — | identical scheme to staging |
| List shops / shop_cipher | Yes (`_tt_get_shops`, `_tt_ensure_cipher`) | external read | — |
| Order search (poll) | Yes (`/order/202309/orders/search`, `_tt_sweep_once/_loop`) | external read | flock leader; fast ~5s window after an event, periodic safety net; honours cutover |
| Order get-by-id | Yes (`/order/202309/orders`, `_tt_ingest_order`) | external read | triggered by webhook + backfill |
| Webhook receive | Yes (`/api/tiktok/webhook`) | inbound | **signature NOT enforced — see Risk P-1** |
| Order → shipment mapping | Yes (`_tt_apply_order`) | local write | idempotent; preserves local pick/pack status; SKU via `show_product_map` |
| Cancellation / status update ingest | Yes (reads TikTok `status`, `delivery_status`) | local write | inbound only |
| Combine / package merge | Local-only (shared `shipment_id`/label) | local | no TikTok combine API |
| Label creation | Carrier (ShipStation/UPS) | **external write** | not TikTok labels |
| Tracking push to TikTok | **No** | — | orders never marked shipped back to TikTok |
| Carrier idempotency (`label_purchases`) | **No** (table absent in main) | — | added R4/R5 — not in production |
| Background jobs | cleanup, tracking, backup, welcome-email, TikTok sweep | mixed | all pre-exist in main; no new workers added by Cycles 2–6 |

---

## Deliverable 2 — Actual vs assumed Production behavior

| Question | Evidence | Status |
|---|---|---|
| Which TikTok APIs are called | code in `main` (above) | VERIFIED (code) / UNVERIFIED (live calls) |
| Polling vs webhooks | **both** — webhook hint + `_tt_sweep` poll (code) | VERIFIED (code) |
| Actual polling interval | code implies ~5s fast / periodic safety net, gated by `_tt_last_event` | **UNVERIFIED** (needs runtime) |
| Order volume & sync latency | — | **UNVERIFIED** (needs Railway logs / telemetry) |
| API errors / rate limits / retries | main has **no** TikTok retry/backoff | code VERIFIED; live 429 rate **UNVERIFIED** |
| Token refresh behavior | `_tt_valid_token` refreshes near expiry | code VERIFIED; live refresh success **UNVERIFIED** |
| Cancellation / status updates work | `_tt_apply_order` handles CANCELLED + delivery status | code VERIFIED; live **UNVERIFIED** |
| TikTok product/SKU → WMS mapping | sticker SKU → `show_product_map` → catalog `product_sku` | VERIFIED (code) |
| Picking/packing/combine/label/tracking | local pick/pack; local combine; carrier labels; **no** tracking push | VERIFIED (code) |
| Granted scopes | stored on `tiktok_shops.granted_scopes` (live value) | **UNVERIFIED** (needs live read) |
| Read-only vs external writes | reads: orders/shops/tokens; writes: **carrier labels only** (+ inbound local writes) | VERIFIED (code) |
| Active background jobs | 5 daemon threads (above) | VERIFIED (code); live liveness **UNVERIFIED** |

**To verify the UNVERIFIED rows (read-only, no secrets), run in the Railway dashboard / a read-only session:** deploy logs for `_tt_log` lines (sweep counts, "ingest failed", refresh errors), the `/api/tiktok/status` admin endpoint (shops, event_count, cutover, paused — no tokens exposed), and `SELECT COUNT(*),MAX(received_at) FROM tiktok_events` per tenant for webhook arrival evidence.

---

## Deliverable 3 — Production vs Staging change comparison (`63181d1` → `cycle6/work`)

26 commits; 21 files; +2399 / −222. Grouped by logical wave with operational properties:

| Wave | Commits (purpose) | API behavior? | Schema? | Inventory/fulfillment state? | New env? | Migration? | Rollback-safe? | Independently releasable? |
|---|---|---|---|---|---|---|---|---|
| **W1 — TikTok sync safety (R1–R3)** `860d999` | Enforce webhook signature; preserve warehouse progress on sweep; non-destructive regroup (relabel) | **Yes** (rejects unsigned webhooks) | none | protects state (prevents clobber) | none | none | Yes | Yes (base of stack) |
| **W1b — iPad nav + dup-event tests** `64b02dc,2ffa455` | Back/Home nav; regression tests | no | none | none | none | none | Yes | Yes |
| **W2 — Safe Mode** `c38f214,97f7cf0` | Block external side-effects in staging only; admin read-only status | gated by `APP_ENV`/`STAGING_*` | none | none | `STAGING_ALLOW_EXTERNAL` (default safe) | none | Yes | Yes — **and inert in production** (only arms when `APP_ENV=staging`) |
| **W3 — Carrier idempotency + atomic inventory (R4/R5)** `97b59ce,c991cc4,bb3ca2f` | Atomic label claim; uncertain outcomes never auto-retry; atomic deduct-once; reconcile endpoints | no TikTok change; carrier calls gain idem key | **NEW table `label_purchases`** (additive) | **hardens** inventory (prevents double-deduct) | none | additive (`CREATE TABLE IF NOT EXISTS`) | Yes (orphan table if rolled back) | Depends on W1 base; yes after |
| **W4 — P0 auth (manager/CS escalation)** `8f808c6,c91a858,6179784,…` | `req_true_admin` server-side gate; blocklist expansion; hire-role guard; temp-pw redaction | no | none | none | none | none | Yes | Depends on prior |
| **W5 — Cycle 2** `4e7459c,2f0f78e` | repair-videos org-scope; CSV depletion-marker preserve; pack issue-guard; pick cancelled-guard; label reclaim atomic; R2 timeouts; 44px targets | no | none | **hardens** (marker preserve) | none | none | Yes | Depends |
| **W6 — Cycle 3** `cc8a3e6,d8568ce,c2373a3` | shared pack resolver; cancel restore+close; pick-complete issue-guard; atomic `_receive_stock`; admin label resolve; **session revocation**; hire-delete login revoke; pack alert→screen | no | none | **hardens** (resolver, restore) | none | none | mostly (session revocation changes auth flow) | Depends |
| **W7 — Cycle 4** `5445426` | e2e/access harness; pick-complete single-winner | no | none | **hardens** (single winner) | none | none | Yes | Depends |
| **W8 — Cycle 5** `14d5bc7` | **no-plaintext temp-pw** + one-time issue endpoint + **purge migration**; **shared rate limiter** (`rate_hits`); tracking-leader lock; UPS idem; **conn teardown** | no | **NEW table `rate_hits`** (additive) | none | `TIKTOK_WEBHOOK_ALLOW_UNSIGNED` (must stay unset), `STAGING_ALLOW_EXTERNAL` | additive table + **one-way data purge** of `provisioned_password` | schema yes; **purge irreversible** (removes unused secret only) | Depends |
| **W9 — Cycle 6** `2a6360e` | TikTok 429/5xx retry+backoff | hardens reads (safe retries) | none | none | none | none | Yes | Yes (trivial, additive) |

**Schema delta summary (vs production):** two NEW additive tables (`label_purchases`, `rate_hits`); all via `CREATE TABLE IF NOT EXISTS`. Inventory columns `depleted_qty/depleted_sku/stock_moves` **already exist in production** — cycles only change the logic around them. One **one-way data migration**: `UPDATE new_hires SET provisioned_password=NULL` (removes an unused, already-redacted plaintext secret; not recoverable, not needed).

---

## Deliverable 4 — Dependency & migration risk assessment

- **The 26 commits are a linear, interdependent chain** (later cycles edit the same functions and depend on earlier fixes; W4–W9 build on W1–W3). **They are NOT cleanly independently cherry-pickable** without creating untested intermediate revisions. Attempting to split them post-hoc risks merge conflicts and partial states that were never validated as a unit.
- **Migrations are additive & idempotent** (`IF NOT EXISTS` / `ADD COLUMN`) → forward-safe; older code ignores the new `label_purchases`/`rate_hits` tables, so **code rollback is schema-safe**.
- **Irreversible step:** the `provisioned_password` purge. It only deletes an unused secret (post-AUDIT#6 the API never returned it). Not a data-integrity concern, but note it cannot be undone and take a DB backup first regardless.
- **No new background workers** are introduced (tracking/sweep/backup/cleanup all pre-exist in main) → no new concurrency surface beyond the already-running jobs.
- **New env vars are optional and default-safe.** Production must **NOT** set `APP_ENV=staging` or `STAGING_ALLOW_EXTERNAL`, and must **NOT** set `TIKTOK_WEBHOOK_ALLOW_UNSIGNED` (leaving it unset enforces webhook signatures — the correct production posture).

---

## Deliverable 5 — Recommended staged rollout plan

**Option A (one combined release of the staging-validated revision) vs Option B (post-hoc split into waves).**

**Recommendation: Option A — promote the already-integrated, staging-soaked revision as a single release.** Evidence: the commits are a linear dependency chain validated together (99 tests green) and already deployed to staging via PR #13. Splitting them now produces intermediate revisions that were **never tested in that combination**, which is *higher* risk than shipping the validated whole. The wave table in D3 is for understanding content, not a prescription to physically split.

Execute as **one wave with a canary wrapper** (all steps are yours to run; I do not push/deploy):

**Release wave — promote staging → `main`**
- *Included:* the staging revision (PR #13 content = Cycles 1–5) + Cycle 6 (`2a6360e`) as a trivial additive follow-up. Confirm the staging HEAD SHA before promoting.
- *Prerequisites:* confirm production `main` SHA (`git rev-parse origin/main`); confirm staging smoke is green; schedule outside a LIVE selling window.
- *Backups & restore checks:* snapshot the Railway volume / copy every tenant `shipments.db`, `platform.db`, `giveaways.db`, and `users.json`; verify the snapshot opens read-only and row counts match before proceeding.
- *Pre-deployment tests:* full suite 99/99 on the release revision; `py_compile` + `check_js`; confirm `APP_ENV` in production is **not** `staging` and `TIKTOK_WEBHOOK_ALLOW_UNSIGNED` is **unset**.
- *Post-deployment smoke:* see Deliverable 6.
- *Monitoring & thresholds:* see Deliverable 7.
- *Rollback:* redeploy the prior production image/commit (`63181d1`). Schema is additive so rollback is safe; the `provisioned_password` purge does not reverse (acceptable). Keep the pre-release backup for 14 days.
- *GO/NO-GO criteria:* GO only if — backup verified; staging smoke green; off-peak window; on-call present; webhook-signature enforcement confirmed active post-deploy within 10 min; order ingestion observed continuing (event_count rising, sweep logs clean) within 30 min. NO-GO if any smoke check fails or ingestion stalls.

If you insist on splitting for extra caution, the only defensible split is **W1 (webhook-auth + progress preservation) first** as a security hotfix, then the remainder as one wave — because W1 is the base, is independently valuable (closes P-1 and P-2 below), and everything else depends on it anyway.

---

## Deliverable 6 — Production smoke-test checklist (read-only; no fulfillment/label/cancel writes)

1. **Webhook auth active:** send a deliberately **unsigned** POST to `/api/tiktok/webhook` from a test tool → expect **401** (production today would wrongly return success — this is the key regression to confirm fixed). Do *not* send a signed forged payload.
2. **Ingestion alive:** `/api/tiktok/status` (admin) → shops active, `event_count` increasing, `paused=false`, expected `cutover`.
3. **Sweep healthy:** deploy logs show `sweep ingested N order(s)` and no repeated `sweep failed` / token-refresh errors.
4. **Order mapping:** pick one known recent order id → appears as a shipment with correct buyer/SKU, status not regressed.
5. **Inventory integrity:** spot-check one product `on_hand` before/after a test pack of a sandbox order (or verify no unexpected `stock_moves`). Do not alter real orders.
6. **Auth gate:** a manager session cannot reach `/api/users` / `/api/profit` (expect 403).
7. **Rate limiter table present:** `platform.db` has `rate_hits`.
8. **Safe-mode inert in prod:** `/api/ops/safe-mode` → `staging:false` (production is intentionally NOT safe-moded).
9. **No new error class** in logs for 30 min post-deploy.

---

## Deliverable 7 — Monitoring & rollback strategy

**Monitor (first 24–48h):**
- Webhook 401 rate (should be ~0 from TikTok; a spike = signature mismatch → investigate before it blocks ingestion).
- TikTok 429/5xx rate and retry log lines (Cycle-6 backoff should absorb; sustained 429 = lower poll rate / ask William).
- Sweep cadence & "ingest failed" count; token-refresh failures (alert immediately — silent ingestion stop).
- Order ingestion lag: `MAX(received_at)` on `tiktok_events` and newest shipment vs wall clock.
- SQLite "database is locked" occurrences (should drop vs baseline thanks to C4-2 teardown + busy_timeout).
- Inventory anomaly: any `on_hand < 0` or double `stock_moves` for one shipment (should be impossible post-R5).

**Alert thresholds (suggested):** webhook-401 > 5/min; token-refresh failure ≥ 1; sweep failures ≥ 3 consecutive; ingestion lag > 10 min during a LIVE; any negative `on_hand`.

**Rollback:** flip the Railway deployment back to `63181d1`; additive schema makes this safe. Forward-recovery preferred for data issues (the sweep re-ingests from TikTok idempotently). Keep backups 14 days.

---

## Deliverable 8 — Unresolved questions for William (blocking production *fulfillment*, not this promotion)
Carried from the Cycle-6 draft (unchanged): LIVE order availability/latency; webhook event completeness + dedup id + 3s ack SLA; recommended polling frequency; exact Orders/Fulfillment rate limits + Retry-After; missing-order reconciliation look-back; required scopes for read/ship/label/combine; Mark-Package-As-Shipped correctness for US seller shipping; Create-Packages label flow for US; **US** combine/uncombine availability; multiple orders sharing one tracking number; sandbox/test-shop. These gate *new* fulfillment features (Cycle 7), **not** the promotion of Cycles 1–6.

---

## Deliverable 9 — Final GO / NO-GO recommendation

**GO to prepare and promote Cycles 1–6 to Production as one validated release — conditional on the gates below.** This is strongly advisable because production today carries two code-level security defects that the stack fixes:

- **P-1 (Critical):** Production `main` computes the webhook signature but **does not enforce it** — a forged webhook could deactivate the shop (`type 6`, halting all order ingestion) or trigger ingests. Fixed by W1 (R1).
- **P-2 (High):** Production has the manager blocklist but **not** the `req_true_admin` server-side gate — handler-level admin escalation (AUDIT #6/#7) is unmitigated in production. Fixed by W4.
- Plus: no carrier idempotency (double-buy risk), no atomic deduct-once (R5), no shared rate limiter, no session revocation, no 429 backoff — all live hardening absent from production today.

**Hard gates before the deploy (all must be true):** verified volume backup; production `APP_ENV≠staging` and `TIKTOK_WEBHOOK_ALLOW_UNSIGNED` unset; staging smoke green on the exact revision; off-peak (no active LIVE); on-call present; rollback to `63181d1` rehearsed.

**NO-GO conditions:** any smoke-test failure; inability to take/verify a backup; no runtime visibility to confirm webhook-auth enforcement and continued ingestion post-deploy; or a LIVE selling session in progress.

**Explicitly NOT in this promotion (defer to Cycle 7, needs William + approval):** tracking push to TikTok, TikTok labels, combine via TikTok API. Those involve live external writes and unverified API behavior.

---
*Prepared read-only. I did not modify Production, Git remotes, Railway, env vars, databases, carriers, or TikTok settings, and made no live API calls. Awaiting your review before any Cycle 7 implementation.*
