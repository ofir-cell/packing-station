# Cycle 6 — TikTok API Audit, Operational Readiness & Combine/Shipping Feasibility

Baseline: deployed Cycle-5 (`14d5bc7`, staging deploy `eba11dbf`, PR #13). Work branch: `cycle6/work` @ `2a6360e` · Bundle: `cycle6-review-2a6360e.bundle`.
Gates: `py_compile` ✅ · `check_js` ✅ (63/63) · full suite **99 passed / 0 failed** (96 prior + 3 new).
No push / merge / deploy / Railway / live-TikTok / live-carrier / production action taken. Staging Safe Mode untouched.

Honesty note: all tests are automated **sandbox** with external calls mocked. **No live TikTok or carrier API call was made.** Findings labelled REQUIRES TIKTOK CONFIRMATION are exactly that — do not treat them as verified until William or a live sandbox confirms.

---

## A. Executive summary

**What works (verified in code, and consistent with official docs):**
- **Order ingestion from TikTok** via `/order/202309/orders/search` (poll) and `/order/202309/orders` (by id), with correct **HMAC-SHA256 request signing**, `x-tts-access-token` header, `app_key`/`timestamp`/`sign` params, shop_cipher handling, pagination via `next_page_token`, and `update_time` windowing.
- **Webhook security** — signature scheme (`HMAC-SHA256(app_secret, app_key + raw_body)`, read from the `Authorization` header, verified against the **raw** body before parsing) **matches the current official scheme**. Unsigned pushes cannot mutate state; at most they act as a "go re-fetch this order" hint, and the order is then pulled with our own token — a forged payload cannot inject data.
- **Overwrite protection** — a TikTok order update can **never** clobber warehouse progress: `picked / issue / packed / shipped / cancelled` are preserved; only a real TikTok `CANCELLED` overrides. Non-API (CSV) shipments are off-limits to the API path. This is the single most important operational-safety property and it is solid.
- **Idempotent apply** — `_tt_apply_order` is safe to call repeatedly; dedupes an order across CSV and API by order id, tracking, and package id; migrates its own synthetic `TT-<id>` placeholder to the real package id without double-counting.
- **Inventory integrity, concurrency, SQLite reliability, carrier idempotency, staging safety** — hardened and regression-covered across Cycles 1–5 (99 tests).

**What is new in Cycle 6:** `_tt_request` now **retries 429/5xx and transient network errors** with bounded backoff, honouring `Retry-After`, re-signing each attempt (TikTok's documented guidance). 3 new tests.

**What is broken / missing for real fulfillment (structural, not bugs):**
1. **No tracking push back to TikTok.** We import orders but never call TikTok to mark a package shipped or submit our tracking number. Orders packed in the WMS are **not** reflected as shipped in TikTok Seller Center unless a human does it there. **This is the #1 gap for going live.**
2. **No TikTok combine / package API.** "Combine" today is **local only** (several orders share one internal `shipment_id`/label). TikTok's own Search-Combinable-Packages → Combine-Package → Ship-Package flow is **not** called.
3. **No TikTok-generated shipping labels.** Labels come from our own ShipStation/UPS integration, not TikTok Shipping.

**What is unverified:** everything about live TikTok timing/latency, LIVE-sale pre-order events, US-market combine eligibility, and exact rate limits — see §D and the William message (§G).

---

## B. TikTok API inventory

| Capability | Endpoint (version) | Code location | Scope (assumed) | Freq | Error handling | Status |
|---|---|---|---|---|---|---|
| Token exchange | `GET /api/v2/token/get` (auth.tiktok-shops) | `_tt_token_exchange` | — | on connect | returns body | VERIFIED (code), NEEDS VALIDATION (live) |
| Token refresh | `GET /api/v2/token/refresh` | `_tt_token_refresh`, `_tt_valid_token` | — | on expiry | now retries 429/5xx | NEEDS VALIDATION |
| List shops | `GET /authorization/202309/shops` | `_tt_get_shops`, `_tt_ensure_cipher` | `seller.shop` | on connect / cipher fill | retry+backoff | VERIFIED (code) |
| Search orders | `POST /order/202309/orders/search` | `_tt_sweep_once` | `seller.order` | poll (fast ~5s after event, else periodic; ≤30 pages×100) | code-break + retry | VERIFIED (code) |
| Get order(s) | `GET /order/202309/orders` | `_tt_ingest_order`, `_tt_backfill_delivery`, `_tt_refresh_stored_statuses` | `seller.order` | per webhook / backfill | retry+backoff | VERIFIED (code) |
| Webhook receive | `POST /api/tiktok/webhook` (ours) | `api_tiktok_webhook`, `_tt_webhook_verify` | — | inbound | sig-verify, 401 on bad sig | VERIFIED (scheme matches docs) |
| Request signing | n/a | `_tt_sign` | — | every signed call | — | VERIFIED |
| **Mark package shipped / submit tracking** | `POST /fulfillment/202309/packages/{id}/...` (Mark Package As Shipped) | **absent** | `seller.fulfillment` | — | — | **MISSING** |
| **Create package / buy TikTok label** | `POST /fulfillment/202309/packages` | **absent** | `seller.fulfillment` | — | — | **MISSING** |
| **Get shipping document (label)** | `GET /fulfillment/202309/.../shipping_document` | **absent** | `seller.fulfillment` | — | — | **MISSING** |
| **Search combinable / Combine / Uncombine** | `POST /fulfillment/202309/.../combine`, `.../packages/{id}/uncombine` | **absent** | `seller.fulfillment.package.write` | — | — | **MISSING** (local combine only) |
| **Get shipping providers** | `GET /logistics/202309/shipping_providers` | **absent** | — | — | — | **MISSING** (needed for seller tracking) |

Scopes are marked "assumed" because the granted-scope set lives on the connected shop record (`tiktok_shops.granted_scopes`) and must be confirmed against the live authorization — a NEEDS-VALIDATION item.

---

## C. Integration architecture (current data flow)

```
TikTok Shop
  │  (1) ORDER_STATUS_CHANGE webhook  ── Authorization: HMAC(app_secret, app_key+body)
  ▼
/api/tiktok/webhook  ──verify sig──▶ log event ──▶ _tt_ingest_order(GET /order/202309/orders)
  │                                   (never trusts payload body for data)
  │  (2) background poller _tt_sweep_loop (flock leader): POST /order/202309/orders/search
  ▼       fast ~5s window after an event, periodic safety-net otherwise; honours cutover
_tt_apply_order ──▶ shipments / shipment_items  (import_batch='tiktok-api')
  │   preserves picked/packed/shipped/cancelled; dedupes vs CSV; idempotent
  ▼
Warehouse: pick (/api/pick/complete) → scan (/api/shipment/<code>) → pack (/api/upload)
  │   inventory depleted atomically; local combine = shared shipment_id/label (relabel, not delete)
  ▼
Carrier labels: ShipStation / UPS direct (_ship_buy, atomic idempotent claim)
  ▼
Tracking status IN: _tt_apply_order reads TikTok's own delivery_status (IN_TRANSIT/DELIVERED…)
  ▼
✗ Tracking status OUT: nothing is pushed back to TikTok  ← GAP #1
✗ TikTok labels / combine / package API           ← GAPS #2, #3
```

---

## D. Shipping & Combine feasibility (official docs + our code)

Classified per the required buckets. Endpoint names/versions from TikTok Partner Center docs (sources below); request/response schemas and **US-market** eligibility still need confirmation.

**Possible via API today (per docs) — not yet built by us:**
- **Seller Shipping — submit our own tracking:** *Mark Package As Shipped* (`/fulfillment/202309/...`) uploads shipping-provider id + tracking number to TikTok. Needs *Get Shipping Providers* for the `shipping_provider_id`. → closes GAP #1. **NEEDS VALIDATION** (exact path/body, US availability).
- **TikTok Shipping — buy TikTok label:** *Create Packages* (`POST /fulfillment/202309/packages`, scope `seller.fulfillment.basic`, region-specific to US) → then *Get Shipping Document* for the label. → GAP #3. **NEEDS VALIDATION.**
- **Combine packages:** *Search Combinable Packages* → *Combine Package* → *Ship Package*; *Uncombine Packages* = `POST /fulfillment/202309/packages/{id}/uncombine` (scope `seller.fulfillment.package.write`). Docs describe this flow for **SEA/LATAM**; **US combine behaviour is unclear**. → GAP #2. **REQUIRES TIKTOK CONFIRMATION** (US eligibility, buyer/address constraints, deadline rules).
- **Multiple orders sharing one tracking number:** our local model already does this (shared `shipment_id`); whether TikTok's API accepts one tracking number across several orders without the official Combine flow is **REQUIRES TIKTOK CONFIRMATION**.

**Requires TikTok confirmation (docs/permissions insufficient):**
- LIVE auction sales *before* order creation; whether any webhook/API exposes per-auction sales pre-order; latency from LIVE purchase → Orders API visibility. Official docs do not clearly expose a pre-order LIVE sales feed → **REQUIRES TIKTOK CONFIRMATION** (do not assume real-time pre-order data exists).
- Exact Orders/Fulfillment **rate limits** for our region/app (docs show per-endpoint 1-min window + 429/Retry-After, no published Orders QPS).

**Safe Combine Engine design (documented, not implemented — preserves all invariants):**
- Keep every original TikTok **order_id** as a row in `shipment_items.order_id`; a combined box is one `shipment_id` carrying ≥1 order_ids (today's model).
- Combine only when buyer id **and** ship-to address match, and no order is cancelled/hold/ship-by-passed.
- Inventory movements stay per-order (depletion markers are per item/order; already preserved on regroup).
- Record an audit row per combine/uncombine (who/when/which orders) — add a `combine_log` table.
- Reversible: uncombine restores each order to its own package; never deletes order history (mirrors the existing relabel-not-delete R3 rule).
- Only AFTER William confirms US combine semantics do we wire the TikTok Combine/Ship endpoints behind Staging Safe Mode.

---

## E. Operational risk register (ranked by operational impact)

| ID | Risk | Sev | Prob | Impact | Mitigation / status |
|----|------|-----|------|--------|---------------------|
| R-01 | **Orders packed in WMS are not marked shipped in TikTok** (no tracking push) → late-shipment penalties, buyer confusion | **High** | High (at go-live) | Fulfillment SLA breaches | Build Mark-Package-As-Shipped after William confirms; until then, staff mark shipped in Seller Center. |
| R-02 | Webhook ack blocks on a **synchronous order fetch**; TikTok requires 200 within ~3s → slow fetch = TikTok marks delivery failed and retries | Med | Med | Duplicate processing, missed webhooks | Poller already recovers; recommend acking 200 first, ingest async. Documented; not changed this cycle (threading in request path — needs care). |
| R-03 | **US combine semantics unknown** — building combine on SEA/LATAM assumptions could corrupt fulfillment | Med | Med | Rework, bad labels | Blocked on William; design is reversible + audited. |
| R-04 | No **tts_notification_id dedup** on webhooks | Low | Med | Redundant re-fetches only (apply is idempotent) | Add dedup key; low urgency because ingestion is idempotent. |
| R-05 | **Rate limits** for our region/app unknown; burst polling (≤30 pages ×100) could hit 429 | Med | Low | Throttling during big LIVEs | Cycle-6 retry/backoff + Retry-After now in place; confirm limits with William. |
| R-06 | **Token refresh failure handling** unproven against live expiry | Med | Low | Ingestion stops silently | Retry added; add alerting on refresh failure (roadmap). |
| R-07 | LIVE pre-order data assumed available | Med | Med | Feature built on nonexistent API | Treated as REQUIRES CONFIRMATION; nothing built. |
| R-08 | Production runs **outside Safe Mode** — real carrier/TikTok writes live | High | — | Accidental live actions | Gate all new write paths behind an explicit prod flag + confirmation. |

---

## F. Code changes & test results

**Changed:** `app.py` — `_tt_request` now retries 429/5xx + transient network errors with bounded exponential backoff, honours `Retry-After`, re-computes `timestamp`+`sign` each attempt. No other behaviour changed.
**Added:** `tests/test_cycle6_tiktok.py` — 3 tests (retry-then-succeed; give-up-after-max returns parsed error, no raise; signature recomputed/fresh per attempt). urlopen fully mocked — no live call.
**Result:** full suite **99 passed / 0 failed**; `py_compile` + `check_js` clean. Branch `cycle6/work` @ `2a6360e`; verified bundle delivered.
**Deliberately NOT changed:** no TikTok fulfillment/combine/label/ship write code added (unverified live behaviour — documented instead, per instructions).

---

## G. Message to William (draft — not sent)

> Subject: TikTok Shop API — fulfillment, combine & LIVE order questions for our warehouse integration
>
> Hi William,
>
> We run a custom warehouse management system for our TikTok Shop LIVE selling. Today we: receive `ORDER_STATUS_CHANGE` webhooks at our HTTPS endpoint (verifying the `Authorization` HMAC-SHA256 over `app_key`+raw body), and poll `POST /order/202309/orders/search` + `GET /order/202309/orders` with signed requests (`x-tts-access-token`, `app_key`/`timestamp`/`sign`), using `shop_cipher`. We map orders to internal picking/packing and buy carrier labels through our own ShipStation/UPS accounts. We do **not** yet call any `/fulfillment/202309/...` endpoints.
>
> We'd like to confirm a few things that we can't determine from the docs alone:
>
> 1. **LIVE orders & latency:** During a LIVE, what is the typical delay between a buyer's purchase/auction win and the order becoming visible in `/order/202309/orders/search`? Is there any API or webhook that exposes individual LIVE/auction sales *before* the order is created, or is the Orders API the earliest reliable signal?
> 2. **Webhook completeness & timing:** Which event topics should we subscribe to for complete order coverage (we currently handle topic 1 / `ORDER_STATUS_CHANGE` and 6 / deauthorization)? What is the delivery SLA and retry policy, and is there a stable dedup id (e.g. `tts_notification_id`) we should key idempotency on? Our endpoint acknowledges 200; is the ~3s ack window firm?
> 3. **Recommended polling frequency** for a US shop during active LIVEs vs idle, to stay within limits.
> 4. **Rate limits:** What are the per-endpoint QPS/か minute limits for `orders/search`, `GET orders`, and the fulfillment endpoints for our app/region? Do you return `Retry-After` on 429? (We've implemented backoff that honours it.)
> 5. **Missing-order reconciliation:** If a webhook is missed and a poll window lapses, what's the recommended backfill (we page `orders/search` by `update_time`)? Any max look-back?
> 6. **Scopes:** Which exact authorization scopes do we need for (a) reading orders, (b) Mark Package As Shipped with our own tracking, (c) Create Packages / TikTok labels, (d) combine/uncombine?
> 7. **Seller Shipping — submit our own tracking:** Is *Mark Package As Shipped* (`/fulfillment/202309/...`) the correct endpoint to push our carrier + tracking number back to TikTok for a US shop, and do we first call *Get Shipping Providers* for `shipping_provider_id`? Any constraints on timing vs the ship-by deadline?
> 8. **TikTok Shipping labels:** For US, is *Create Packages* (`POST /fulfillment/202309/packages`) + *Get Shipping Document* the right flow to generate and retrieve a TikTok label, and can we print it directly?
> 9. **Combine / package merge:** Is the *Search Combinable Packages → Combine Package → Ship Package* flow available for **US** shops via API (the docs read SEA/LATAM)? What are the eligibility rules (same buyer, same address, deadline, status) and does combine preserve all original order IDs?
> 10. **Multiple orders, one tracking number:** Can several orders share a single tracking number through the API without the official Combine flow, or must they be combined first?
> 11. **Testing / sandbox:** Is there a sandbox or test-shop environment where we can exercise fulfillment, combine, and label endpoints without affecting real orders or buyers?
>
> Thank you — we want to integrate these correctly rather than guess at behaviour.

Only questions not answerable from our code + public docs are included; endpoint names/versions are stated where known.

---

## H. Production GO / NO-GO checklist

**Current: NO-GO for production fulfillment automation** (staging functionality itself is healthy). Gates:

- [ ] **R-01 resolved:** tracking push (Mark Package As Shipped) built, tested in a TikTok sandbox, and verified to mark orders shipped — OR an explicit manual Seller-Center process accepted for launch.
- [ ] William answers §G (esp. scopes, rate limits, US combine, seller-shipping endpoint).
- [ ] Granted scopes on the live shop confirmed to cover the endpoints we'll call.
- [ ] Webhook ack latency (R-02) addressed or accepted (poller recovery verified under load).
- [ ] Staged rollout: one shop, low-volume LIVE, with Safe Mode semantics mirrored by a production write-guard flag on any new TikTok/ carrier write path.
- [ ] Monitoring: alert on token-refresh failure, webhook 401 rate, 429 rate, sweep errors, and "packed but not shipped-to-TikTok" backlog.
- [ ] Rollback: new write paths behind a feature flag defaulting off; revert = flip flag (no deploy).
- [ ] Outstanding live validations: real-iPad pack pass; live-carrier label in a controlled window; combine flow in sandbox before any real buyer.

**GO for:** promoting `cycle6/work` (the 429/5xx retry hardening) to staging — low-risk, additive, 99/99 green.

---

## I. Recommended Cycle 7 roadmap (by business impact)

1. **Tracking push to TikTok (Seller Shipping)** — build *Get Shipping Providers* + *Mark Package As Shipped*, behind a prod write-guard, tested in sandbox. Closes R-01, the top launch blocker. *(High impact.)*
2. **Webhook ack-then-ingest-async** (R-02) + `tts_notification_id` dedup (R-04). *(Reliability for continuous LIVE.)*
3. **Combine Engine (phase 1, local-safe)** — formalize the audited `combine_log`, buyer/address guards, reversible uncombine; wire TikTok Combine endpoints only after William confirms US semantics. *(High business value: shipping-cost savings.)*
4. **TikTok Shipping labels (optional)** — Create Packages + Get Shipping Document, if cheaper/required vs our carriers. *(Medium.)*
5. **Observability** — token-refresh/429/sweep alerting + a "packed-but-not-shipped-to-TikTok" dashboard. *(Medium, de-risks launch.)*
6. **UI/UX (Agent H)** — combine-order visibility on the pack screen, one-tap label print, clearer bilingual EN/HE error recovery, scanner-focus retention. *(Throughput.)*

---

### Sources (official TikTok Shop Partner Center unless noted)
- Create Packages (202309): https://partner.tiktokshop.com/docv2/page/650aa132bace3e02b75d40d8
- Fulfillment flow overview: https://partner.tiktokshop.com/docv2/page/650b2044f1fd3102b93c9178
- Mark Package As Shipped (202309): https://partner.tiktokshop.com/docv2/page/mark-package-as-shipped-202309
- Get Package Detail (202309): https://partner.tiktokshop.com/docv2/page/get-package-detail-202309
- Uncombine Packages (202309): https://partner.tiktokshop.com/docv2/page/650aa960f1fd3102b92ceb0e
- Batch Ship Packages (202309): https://partner.tiktokshop.com/docv2/page/650aa3ebbace3e02b75d8bd4
- APIs overview: https://partner.tiktokshop.com/docv2/page/tts-api-concepts-overview
- Order Combination (Seller University): https://seller-us.tiktok.com/university/essay?knowledge_id=5369161871132458&lang=en
- Webhook scheme/events (third-party, verify w/ TikTok): https://hookdeck.com/webhooks/platforms/guide-to-tiktok-shop-webhooks-features-and-best-practices
- Rate limits (TikTok dev docs / third-party): https://developers.tiktok.com/doc/tiktok-api-v2-rate-limit · https://www.getphyllo.com/post/tiktok-api-rate-limits-in-2026-quotas-errors-workarounds
