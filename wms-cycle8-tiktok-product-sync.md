# Cycle-8 — TikTok Product/SKU Sync (Staging) + LIVE API findings

Built, tested, and bundled on an **isolated staging branch** (`tiktok/product-sync`, commit `9a5b3cb`, based on `origin/staging` `bd3fb63`). **Nothing pushed, merged, or deployed. Production untouched.** All TikTok calls are reads and are **inert under staging Safe Mode** (they short-circuit in `_tt_request`).

## 1. What I built (Product/SKU synchronization)
Reuses the existing order-sync plumbing end-to-end — the signed `_tt_request`, OAuth token refresh (`_tt_valid_token`), `shop_cipher` resolution (`_tt_ensure_cipher`), and the flock-elected single-worker loop. No new auth or credential paths.

- **`_tt_products_once(org_filter=None)`** — for each connected shop, paginates `POST /product/202309/products/search` (same versioned path style as `/order/202309/orders/search`), collecting all products. Idempotent.
- **`tiktok_products` cache** (lazily created in `platform.db`, keyed by org+shop+product+sku) — upserts title, SKU, seller_sku, status, price, currency, stock, and a **catalog-match flag**.
- **SKU mapping** — each TikTok `seller_sku` is matched against our own catalog (`sku_weights` + `products`) and flagged `matched_sku`, so you immediately see which live SKUs map to packing weights and which are orphans.
- **Defensive parser (`_tt_extract_skus`)** — tolerates several field spellings (price as nested object or bare string, inventory as `inventory[]` or `stock_infos[]`, `seller_sku`/`sellerSku`) so a live-shape difference degrades gracefully instead of dropping data. Field names will be confirmed against a real sandbox/live response before any production use.
- **Automatic refresh** — an **hourly** product tick inside the existing sweep loop (idle-only, never during a live sale burst), on the same single elected worker.
- **Admin endpoints:** `POST /api/tiktok/products/sync` (trigger now; Safe-Mode → explicit no-op), `GET /api/tiktok/products` (list, with `?unmatched=1` and `?q=` filters, plus matched/unmatched counts).

## 2. Tests — full suite **137 passed / 0 failed**
New `tests/test_cycle8_tiktok_products.py` (9 tests), all with a mocked `_tt_request` (no network): parser correctness, alt-shape tolerance, catalog match-flagging, two-page pagination, idempotent re-sync (upsert not duplicate), Safe-Mode inertness, the admin list route + unmatched filter, admin-only access, and the Safe-Mode sync no-op.

## 3. LIVE auction / bidding API — honest findings
I could not reach the authoritative endpoint tables (the Partner Center API reference is login-gated / client-rendered; I did not route around that). From the **official Partner Center changelog**, TikTok Shop's open platform provides:
- **Auction products inside the Product API** — support for fixed-price *and* LIVE auction selling formats, a field that controls auction-product support, and regular create/read/update/delete for auction products. So auction *products* are reachable through the same Product API this cycle targets.
- **Two LIVE analytics endpoints** (LIVE performance/analytics), consistent with the analytics-style data we already pull.

What I did **not** find any official evidence for: a real-time per-bid or live-bidding event stream (individual bids as they happen). Treat that as **unconfirmed** until the gated reference is checked while signed in. I did not invent endpoints. Next step on LIVE is to confirm the exact auction-product and LIVE-analytics paths/versions from the signed-in Partner Center reference, then extend the same `_tt_request` infra — I'll do that once you can share the reference or approve a signed-in browse.

## 4. Next (continuing autonomously on Staging, no production impact)
1. Validate `_tt_products_once` field parsing against a real sandbox/staging product response; adjust the parser if the live shape differs.
2. Confirm official auction-product + LIVE-analytics endpoint paths from the signed-in Partner Center reference.
3. Surface the cached catalog + match status in the admin UI (orphan-SKU worklist).

Bundle: `cycle8-tiktok-product-sync-9a5b3cb.bundle` (delivered). Branch `tiktok/product-sync` retained locally in your repo.

Sources: [New APIs for TikTok LIVE — Partner Center changelog](https://partner.tiktokshop.com/docv2/page/sv0xa2r6), [Partner Center affiliate integration (202405 examples)](https://partner.tiktokshop.com/docv2/page/affiliate-integration)
