# TikTok Shop ⇄ Packing Station — Integration Audit (read-only)

Audited against the **actual deployed code**. No code was modified or deployed.

**Reference points (verified this session):**
- **Production** = `origin/main` @ `25f0f21` — **running on Railway** (service `authentic-curiosity`, env `production`, deployment `963928d9` SUCCESS, 2026-10-29 03:20 UTC). Cycles 1–6 + Backup V2 are LIVE.
- **Staging** = `origin/staging` @ `bd3fb63` (service `authentic-curiosity`, env `Staging`, `APP_ENV=staging` → Safe Mode ON).
- **Dev branch (not deployed)** = `tiktok/product-sync` @ `61d387e` — product/SKU sync + webhook product refresh. Exists only here; **not in staging or production**.

Legend: **LIVE** (deployed+running) · **IMPL-NOT-DEPLOYED** (in a branch only) · **PARTIAL** · **NOT-IMPL**.

---

## 1. Current architecture — **LIVE**
Single-file Flask app (`app.py`, ~16k lines; HTML/JS in `templates.py`). Multi-tenant: per-org SQLite under `DATA_DIR/orgs/<org>/` — `shipments.db` (`sdb()`), `giveaways.db` (`gdb()`) — plus a shared `platform.db` (`pdb()`). Daemon threads elected across gunicorn workers via `fcntl.flock`.

**TikTok connection (OAuth), code path:**
- `GET /api/tiktok/connect` (`api_tiktok_connect`, admin-only) → redirects to TikTok authorize portal with a per-org `state` (`_tt_state`).
- `GET /api/tiktok/callback` (`api_tiktok_callback`) → `_tt_token_exchange(code)` → `_tt_get_shops(access_token)` → stores tokens + `shop_cipher` in **`tiktok_shops`** (keyed `org_id, shop_id`).
- Token lifecycle: `_tt_valid_token` (auto-refresh via `_tt_token_refresh` when <5 min to expiry), `_tt_ensure_cipher` (lazy `shop_cipher` fetch).
- Signing/transport: `_tt_request(method,url,...,signed=True)` — HMAC-SHA256 (`_tt_sign`), 429/5xx retry with backoff, timestamp re-computed per attempt. **Returns `{"code":"SAFE_MODE"}` and makes no network call when `STAGING_SAFE` is on.**

**The complete set of outbound TikTok calls (verified — all READS, no writes):**
1. `GET /authorization/202309/shops`
2. `GET /order/202309/orders` (single-order fetch)
3. `POST /order/202309/orders/search` (bulk sweep)
4. `GET /analytics/202509/shop_lives/performance` (LIVE sessions — note the **202509** version)
5. `GET /auth/api/v2/token/get`
6. `GET /auth/api/v2/token/refresh`

**DB tables (platform.db):** `tiktok_shops`, `tiktok_orders` (key `org_id,order_id`), `tiktok_events` (webhook audit + idempotency), `tiktok_live_sessions` (key `org_id,session_id`), `tiktok_control` (per-org pause). **Per-tenant (shipments.db):** `shipments`, `shipment_items`, `sku_weights`, `products` (catalog), `inbound_shipments`.

**Data flow (LIVE):** TikTok webhook / poll → `_tt_ingest_order` parks the order in `tiktok_orders` → `_tt_apply_order` materializes it as a `shipments` + `shipment_items` row in the tenant DB (same tables the CSV importer uses, so every existing packing screen works unchanged) → orders bound to a LIVE session by time window (`import_label` = show name).

---

## 2. Order synchronization — **LIVE**
**Entry paths (two, both idempotent):**
- **Webhook** `POST /api/tiktok/webhook` (`api_tiktok_webhook`): signature-verified (`_tt_webhook_verify`, HMAC in `Authorization`). **Unsigned requests cannot change state** — they're rejected 401 unless `TIKTOK_WEBHOOK_ALLOW_UNSIGNED=1`, in which case an unsigned push is treated only as a "go fetch this order" hint (the order is still fetched with our own token, so a forged payload can't inject data). Topic **1** = order status change → `_tt_ingest_order`; topic **6** = seller deauth → marks shop inactive. Every verified event is logged to `tiktok_events`.
- **Background poller** `_tt_sweep_loop` / `_tt_sweep_once` (single flock-elected worker): wide safety sweep every ~5 min (`window_sec=7200`); when a sale arrived in the last 7 min, fast ~5s polling (`window_sec=180`); idle ~30s. Uses `POST /order/202309/orders/search` with `update_time_ge`, paginates up to 30 pages via `next_page_token`.

**Sync cadence summary:** near-real-time during a live (webhook + 5s poll), ~5 min safety net otherwise.

**Duplicate prevention (verified):**
- `tiktok_orders`: `ON CONFLICT(org_id,order_id) DO UPDATE` — upsert, never duplicates.
- `_tt_apply_order`: looks up existing shipment by order_id / tracking / package_id and **leaves it alone if already present** (incl. CSV-imported); migrates its own synthetic `TT-<oid>` placeholder once a real package id appears; **aborts if the target `shipment_id` is not API-owned** (protects manual/CSV rows); preserves local pack progress for statuses in `_TT_KEEP_LOCAL_STATUS` unless the order is cancelled.

---

## 3. Products & SKUs — matching is **IMPL-NOT-DEPLOYED**; order-line SKUs are **LIVE**
- **LIVE today:** order line items carry `seller_sku` + `sku_id`; `_tt_ingest_order` aggregates them to quantities, and `_tt_apply_order` joins to the tenant catalog via `sku_weights` (SKU→weight) for packing. Barcode matching uses the `products` table (`products.barcode`, index `idx_products_barcode`) in the normal packing/scan flow. So SKUs flow through orders and are matched at pack time.
- **NOT deployed — full product-catalog sync:** `_tt_products_once`, `_tt_apply_products`, `_tt_extract_skus`, the `tiktok_products` cache, `_tt_product_detail`, `_tt_refresh_product`, and admin routes `POST /api/tiktok/products/sync` + `GET /api/tiktok/products` exist **only on branch `tiktok/product-sync`**. They paginate `POST /product/202309/products/search`, upsert a per-org product/SKU cache, and flag which TikTok `seller_sku`s map to our catalog (matched/unmatched worklist). **Fully mocked-tested (140 passing) but not in staging or production, and never run against a live shop.**
- **Assumption (not verified):** the `/product/202309/products/search` request/response field shapes are inferred from the versioned-path pattern + changelog, not confirmed against a live response. The parser is deliberately defensive for this reason.

---

## 4. LIVE auctions — **PARTIAL (session-level only)**
- **LIVE today:** `GET /analytics/202509/shop_lives/performance` populates `tiktok_live_sessions` (session name + start/end window). Orders are bound to a session **by time window**, so a live's orders group together under its show name (`import_label`) and drive per-live DUE/prioritization in the packing UI.
- **NOT received / NOT implemented:** individual **bids**, bid-by-bid events, auction winner events, or any real-time per-auction stream. We only get aggregate session performance + the orders that result. There is no auction/bidding endpoint wired.
- **Assumption (not verified):** the TikTok Partner changelog indicates auction *products* are addressable via the Product API, but the exact auction/LIVE endpoints are behind the login-gated Partner Center reference and are **unconfirmed**.

---

## 5. Shipping / fulfillment — inbound tracking **LIVE**; push-back to TikTok **NOT-IMPL**
- **LIVE:** labels are bought via ShipStation V2 (`_ss`, `_ship_buy`, `_buy_label_idempotent`), the tracking number is stored on `shipments.tracking_code` (unique index `idx_ship_tracking`), and supplier/inbound labels record to `inbound_shipments`. Label purchase is gated by `_can_buy_labels()` (org allowlist `_SHIP_LABEL_ORGS`; 403 before any purchase) and blocked entirely in staging.
- **KEY FINDING — NOT-IMPL:** there is **no outbound call that marks an order shipped on TikTok or pushes the tracking number back to TikTok** (no `/fulfillment`, package-ship, or RTS call anywhere — the only outbound TikTok calls are the six reads listed in §1). Fulfillment status on TikTok is therefore **not** updated by this app. **Assumption (to confirm with you):** this is presumably handled by the seller's direct ShipStation↔TikTok connection; if not, TikTok orders are not being marked shipped programmatically by us.

---

## 6. Production vs Staging — what's actually running
| Capability | Production (`25f0f21`) | Staging (`bd3fb63`) | Dev branch (`61d387e`) |
|---|---|---|---|
| OAuth connect / token refresh | **LIVE** | present, but token exchange **inert** (Safe Mode) | — |
| Order webhook + poller sync | **LIVE** | present, external calls **blocked** (Safe Mode) | — |
| Order→shipment materialization | **LIVE** | LIVE (local only) | — |
| LIVE session binding (analytics) | **LIVE** | inert (Safe Mode) | — |
| Label purchase (ShipStation) | **LIVE** (gated to authorized org) | blocked | — |
| Backup V2 (dedicated R2, scheduler, restore) | **LIVE** | LIVE (backup-only Safe Mode exception) | — |
| Cycles 1–6 (security/QA/integration) | **LIVE** | LIVE | — |
| **Product/SKU catalog sync + admin UI** | **NOT present** | **NOT present** | **IMPL-NOT-DEPLOYED** |
| **Single-product detail + webhook product refresh** | NOT present | NOT present | **IMPL-NOT-DEPLOYED** (topic codes env-gated, empty by default) |

Safe Mode (staging) blocks all outbound TikTok/ShipStation/email/R2 calls except the dedicated backup path, so **a real TikTok seller account can only be connected in Production** — OAuth token exchange runs through the Safe-Mode-gated `_tt_request`.

---

## 7. Current limitations (verified unless marked)
1. **No fulfillment push to TikTok** — tracking is stored locally, never sent back to TikTok (verified: no outbound write call). Biggest functional gap if TikTok isn't being updated elsewhere.
2. **Product/SKU catalog sync not deployed** — exists only on `tiktok/product-sync`, never run live; field schema unconfirmed against a real response (assumption).
3. **No auction/bidding data** — only session-level LIVE performance; no per-bid or winner events (verified: only 6 read endpoints).
4. **Product-webhook topic codes unknown** — the near-real-time product refresh is wired but inert until `TIKTOK_PRODUCT_TOPICS` is set with confirmed topic numbers (assumption: codes exist; unverified).
5. **Partner Center API reference is login-gated** — exact 202309 product request schema + auction/LIVE endpoints couldn't be verified from public sources.
6. **Mixed API versions** — orders/shops on `202309`, LIVE analytics on `202509`; product sync assumes `202309`. Worth confirming the current version for each in the signed-in docs.

---

## ⬇️ COPY-PASTE HANDOFF FOR CHATGPT ⬇️

> **System:** Packing Station — a multi-tenant warehouse/packing app for TikTok Shop LIVE sellers. Single-file Python/Flask (`app.py`) + `templates.py`, per-org SQLite (`shipments.db`, `giveaways.db` + shared `platform.db`), deployed on Railway. Production is live on commit `25f0f21` (Cycles 1–6 + a Backup V2 system). Staging runs with "Safe Mode" that blocks all outbound TikTok/ShipStation/email calls.
>
> **TikTok integration — what EXISTS and RUNS in production:**
> - OAuth seller connect (`/api/tiktok/connect` → `/api/tiktok/callback`), tokens+shop_cipher stored per-org in `tiktok_shops`, auto-refresh. All signed via HMAC-SHA256.
> - Order sync, two idempotent paths: signature-verified webhook (`/api/tiktok/webhook`, topic 1=order, 6=deauth) and a background poller (`_tt_sweep_once`) — near-real-time (~5s) during a live, ~5min safety sweep otherwise, using `POST /order/202309/orders/search`. Dedup via `ON CONFLICT(org_id,order_id)` and `_tt_apply_order` guards that never overwrite non-API/CSV shipments or local pack progress.
> - Orders become `shipments`/`shipment_items` rows; line-item `seller_sku`/`sku_id` matched to the tenant catalog (`sku_weights`, `products.barcode`) at pack time.
> - LIVE data is **session-level only**: `GET /analytics/202509/shop_lives/performance` → `tiktok_live_sessions`; orders bind to a session by time window. **No bid/auction/winner events.**
> - Labels bought via ShipStation (not EasyPost); tracking stored on `shipments.tracking_code`.
>
> **The complete set of outbound TikTok calls is 6, all READ-ONLY:** get shops, get order, search orders, live performance, token get, token refresh.
>
> **What is NOT implemented / NOT deployed:**
> - **No fulfillment/tracking push back to TikTok** — we never mark orders shipped on TikTok (no write endpoints at all). Need to confirm whether a separate ShipStation↔TikTok link handles this.
> - **Product/SKU catalog sync** (`/product/202309/products/search` → a `tiktok_products` cache with catalog match-flagging, admin sync/list routes, single-product detail + webhook-driven refresh) is **built and fully unit-tested on branch `tiktok/product-sync` but NOT deployed and never run against a live shop**. The product request/response field schema is **assumed**, not verified.
> - **No auction/bidding integration.**
> - A real seller account can only be connected in Production (Safe Mode blocks OAuth in staging).
>
> **Open unknowns needing the signed-in TikTok Partner Center docs:** exact `202309` product search request schema + pagination; auction-product and LIVE endpoints; product-change webhook topic codes; current API version per domain (orders 202309 vs analytics 202509).
>
> **Help us plan the next phase without duplicating:** the order pipeline, OAuth, LIVE-session binding, and label/tracking storage are DONE and live. The frontier is: (a) product/SKU catalog sync — verify the official schema, then deploy the existing branch; (b) fulfillment push-back to TikTok (currently missing); (c) deeper LIVE/auction data if the API supports it.

---
*Verified facts are cited to code paths/endpoints. Items marked "assumption" are explicitly unconfirmed (mostly because the TikTok Partner Center reference is login-gated). No code was changed and nothing was deployed during this audit.*
