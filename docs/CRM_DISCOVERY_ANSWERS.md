# GETWHATNOT → lightweight CRM — discovery answers (current system)

Answered against the code as it stands on `feature/responsive-pass`. For each item: **Today** (what exists), **Where** (table / endpoint / screen), **Effort** to expose via REST API.

Effort key: **XS** ≤1h · **S** ≤½ day · **M** ~1–2 days · **L** ~3–5 days. All estimates assume the same single-file Flask pattern, per-org SQLite, and the existing bearer-key auth the Returns module already uses.

---

## A. Customers / buyers

**1. Is there a customer/buyer entity?**
Today: No dedicated `customers` table. A "customer" is a **derived view**: we `GROUP BY buyer_username` over `shipments`. Buyer fields live on each shipment row.
Where: table `shipments` (`buyer_username`, `buyer_name`, `address_full`, `postal_code`); `shipment_items` also has `buyer_city`, `buyer_state`. Screen `/customers` + endpoints `/api/customers/search`, `/api/customers/<username>`.
Effort to expose: **XS** — `GET /api/customers/<username>` already returns full history as JSON. A clean public read is basically done.

**2. How is a buyer identified / cross-linked across HERA, 5SEC, TikTok?**
Today: Identified by **platform username** (`buyer_username`) + name. **Not linked across accounts.** Each org (HERA BEAUTY, 5SEC BEAUTY, Peach Beauty) is a **separate SQLite database** — by design a user of org A can never read org B's data, so there is no cross-org buyer identity today. The same person on Whatnot vs TikTok is two different usernames with no join key (no email/phone stored).
Where: multi-tenant `sdb(org)`; buyer identity = `shipments.buyer_username` within one org DB.
Effort: cross-account linking is **L** and a real product decision — it breaks the tenant-isolation invariant, so it needs a deliberate "customer graph" layer (match on normalized name+address, or a shared contact store in `platform.db`). Within one account, nothing to do.

**3. Buyer history stored (orders, totals, first/last, shows, addresses)?**
Today: Yes, all derivable. `/api/customers/<username>` returns: every shipment with items + per-order events, total shipments, total items, shows count, first/last show date, all addresses used, and cross-referenced packing recordings (video/photo/worker/duration from `packing_log.csv`).
Where: `shipments` + `shipment_items` + `packing_log.csv`; endpoint `/api/customers/<username>`.
Effort: **XS** — exists. Adding "total $ spent" = sum `shipment_items.revenue`, a one-line add (**XS**).

**4. Buyer contact / location (city/state/country)?**
Today: Partial. We store `address_full`, `postal_code` (shipments) and `buyer_city`, `buyer_state` (shipment_items). **No email, no phone, no country field.** PII note: for Whatnot, address/recipient data only arrives via CSV import — the Whatnot API account is **not PII-approved**, so the API itself returns `buyer=null`.
Where: `shipments`, `shipment_items`.
Effort: **XS** to expose what we have; email/phone would require the platform's PII scope (not available today).

**5. Notes / tags / flags / blocklist on buyers?**
Today: **None at the buyer level.** No buyer notes, tags, or blocklist exist. (Notes/tags exist only on the new Returns cases.)
Where: n/a.
Effort: **S** — add a small `customer_notes` table (username, org, note, tag, flag, author, ts) + `POST /api/customers/<username>/notes`. This is the single biggest CRM gap.

---

## B. Orders & shows

**6. Order fields stored per platform?**
Today: `shipment_id` (PK = package/parcel id), `tracking_code`, `buyer_username`/`buyer_name`, `address_full`, `postal_code`, `total_items`, `status`, `platform`, `import_label` (the show), `show_date`, `shipping_fee`, `ship_by`, `tt_status` (TikTok order status), `label_url`/`manifest_url`. Per line: `shipment_items` = `order_id`, `sku`, `product_name`, `quantity`, `revenue`, `picked`, `cancelled`, `cancel_reason`, `pack_scanned_qty`, weights.
Where: `shipments`, `shipment_items`.
Effort: **XS** to expose. Note: "pull #" / sticker # lives in `show_product_map` (sticker_sku → product_sku), joined per show, not on the order row. **Payout/net is not stored** — we store sale revenue and our COGS, not platform payout.

**7. Show/live name + date per order?**
Today: Yes. `import_label` = show name, `show_date` = date, `platform` = which platform. Per-show screens already exist.
Where: `shipments.import_label`, `.show_date`; screens `/admin/shows`, `/admin/show` (health), `/api/shows`, `/api/show/health`.
Effort: **XS**.

**8. How is each platform synced?**
Today:
- **TikTok**: real OAuth API integration (`open-api.tiktokglobalshop.com`, v202309) with webhooks + polling — but **currently paused** (you paused ingestion to avoid duplicating the CSV). Authorized scopes today cover **order read** (`/order/.../orders`, `/orders/search`), **fulfillment** (`shipping_documents`), **analytics** (`shop_lives/performance`), **authorization/shops**. Status captured as `tt_status`.
- **Whatnot**: **CSV import** per live (manual upload on `/admin/shows`), normalized in the import route; a connected Whatnot Seller API (MCP) exists and can replace the CSV for pick/pack/cancellations, but **not** address/label/buyer-name (PII not approved on this account). `import_label` = the show name the import is tagged with.
Where: TikTok helpers `_tt_*` (~line 15700–18900); Whatnot `/api/shipments/import` + `_norm_whatnot`.
Effort: n/a (ingestion exists). Switching Whatnot off CSV onto API = separate project, gated on PII approval.

**9. How far back does data go?**
Today: Whatever has been imported — the DB holds all shipments since the org went live; nothing is auto-purged. Packing **videos** are kept ~30 days (R2) unless flagged.
Where: `shipments.imported_at`.
Effort: n/a.

---

## C. Shipping & packing

**10. Per shipment: carrier, tracking, label date, status, last scan, delivered?**
Today: `tracking_code`, `status` (our fulfilment status), plus **live USPS delivery tracking** via the official USPS v3 API: `delivery_status` (bucketed PRE_TRANSIT/IN_TRANSIT/DELIVERED…), `delivery_detail` (last scan text), `delivered_at`, `tracked_at`. Label URLs stored for Whatnot (`label_url`, `manifest_url`); UPS labels stored too.
Where: `shipments.*`; USPS sync `_usps_track_v3` (needs `USPS_CLIENT_ID/SECRET`).
Effort: **XS** to expose. Carrier is inferred (USPS tracking + UPS labels); there is no single `carrier` column — **S** to add one explicitly.

**11. Packing video linked per order?**
Today: Yes, by tracking number. `packing_log.csv` maps `tracking_number → video_file, photo_file, worker, station, date, duration`. Videos live in Cloudflare R2, served through **short-lived presigned URLs** (`/media/video/<fn>`), so access is token-gated and expires.
Where: `packing_log.csv`; routes `/media/video/<fn>`, `/api/recordings`; already surfaced inside `/api/customers/<username>` as `recordings[]`.
Effort: **S** — expose a `GET /api/orders/<tracking>/video` that returns a fresh presigned URL. The Returns module already does exactly this pattern for return photos (`/return-photo/<id>` accepts the AI bearer key), so it's a copy.

**12. USPS / carrier tracking sync, or only label data?**
Today: **Real USPS sync**, not just labels — see Q10. Runs as a background sweep; progress never moves backward automatically.
Where: `_usps_track_v3`, `/api/warp/track` and the tracking sweep.
Effort: n/a.

---

## D. Returns, refunds, disputes

**13. Besides the Returns module, are refunds / partials / cancellations / disputes / chargebacks stored?**
Today: **Cancellations** yes — per line `shipment_items.cancelled` + `cancel_reason`, imported from the cancellation CSV (TikTok-only; Whatnot cancellations don't flow this way). **Refund amount / status** now exist but **only on Returns cases** (`return_cases.refund_amount`, `refund_status`). **No disputes/chargebacks** store anywhere. No standalone refunds ledger.
Where: `shipment_items.cancelled`; `return_cases`.
Effort: **S** per new concept (a `disputes` table + endpoint).

**14. Can we pull TikTok return/refund requests (with deadlines) via the existing integration? Which scopes?**
Today: **No.** The authorized TikTok scopes today are order read, fulfillment (shipping docs), analytics, and shops — **the Reverse (return/refund) API is not authorized**, so we cannot pull return requests, refund deadlines, or RMA data from TikTok yet. The Returns module's `platform_request_id` / `platform_deadline` fields are filled **manually or by the AI**, not synced.
Where: TikTok endpoints actually called are listed under Q8; no `/reverse/` calls exist.
Effort: **M** once the **TikTok Reverse API scope is granted** in the TikTok app (a review/authorization step on TikTok's side, not code). Code to call it and map into `return_cases` is M; getting the scope is the gate.

**15. Can a Return case auto-link to buyer + order + packing video?**
Today: **Yes, already.** On receive, `POST /api/returns` matches the scanned tracking to the original outbound shipment → pulls order_id, platform, import_label, customer username+name, and expected items. Buyer history and packing video are reachable from that shipment.
Where: `_resolve_shipment_by_code`, `return_cases`.
Effort: **XS** — done. Adding the video URL directly onto the case payload = **XS**.

---

## E. Customer messages

**16. Does the TikTok integration have CS chat (read/send)? Scopes?**
Today: **No.** No conversation/IM/customer-service-messaging scope is authorized, and no message endpoints are called. We cannot read or send TikTok buyer messages today.
Where: n/a (no `/conversation` or IM calls in the code).
Effort: **M–L** and gated on TikTok granting the **Customer Service / messaging scope** (app-review step). Read-only is the realistic first target; send requires stricter approval.

**17. Any Whatnot message data? If not, cards via API.**
Today: **No Whatnot message access** (the Seller API doesn't expose buyer DMs, and this account isn't PII-approved). Your plan — create **reply cards via API** — is the right path.
Where: n/a.
Effort: **S** — a `reply_cards` table (order/username, channel, inbound text pasted or forwarded, draft, status draft→approved→sent, author) + CRUD endpoints with the AI bearer key able to **draft** but not mark **sent**. This mirrors the Returns decision-gating exactly.

---

## F. Users, roles, permissions

**18. What roles exist? How is screen access controlled?**
Today: Roles = **admin, manager, cs (Customer Service), host, picker, worker, assistant**. CS already exists and already has access to `/customers`, search, and Returns. Access is enforced **server-side** via `@req_role(...)` on every route (never by hiding UI only), plus a per-screen Access-Management layer (`access.json`, PAGES registry) that can grant/deny individual screens per role.
Where: `ROLE_LABELS`, `VALID_ROLES`, `req_role`, `/admin/access`, `/api/access`.
Effort: **XS** to expose a read of roles/permissions.

**19. API keys — per user, revocable, scopes? Can we have an AI key that drafts but can't approve?**
Today: One global **`RETURNS_AI_KEY`** (env var, Railway) used as a bearer token. `_returns_actor()` validates it with `hmac.compare_digest`, labels the actor **"AI"**, and **every AI change is written to the audit log**. It is **not** per-user, has **no granular scopes**, and the "AI drafts but can't approve" rule is enforced **per-field in code** (the AI can set `decision`/notes but the human restock/discard/reship actions are gated).
Where: `_returns_ai_key`, `_returns_actor`, `_req_returns_rw`, `_csrf_protect` bypass for `/api/returns*`.
Effort: **S** to generalize into a small `api_keys` table (key hash, label, scopes[], revoked, created_by) so you get **revocable, scoped keys** (e.g. `returns:write`, `customers:read`, `replies:draft` but never `replies:send`). Recommended before opening more surfaces to the AI.

---

## G. Technical

**20. Stack?**
Flask (single `app.py` + `templates.py`), **gunicorn** multi-worker, **per-org SQLite** (`sdb(org)`) + a platform DB (`pdb()`), hosted on **Railway** (deploy from `main`), media in **Cloudflare R2** (presigned URLs). Secrets in Railway variables. Also a native iOS app (SwiftUI) and `/m/` mobile web.
Effort: n/a.

**21. Existing API endpoints (not only returns).**
~180 routes. The CRM-relevant read/write ones:
- Customers: `/api/customers/search`, `/api/customers/<username>`, `/api/repeat-customers`, `/api/search` (global: orders, customers, products, shows, people).
- Orders/shipments: `/api/shipment/<code>`, `/api/shipments/recent`, `/api/search/<trk>`, `/api/show-detail`, `/api/today`, `/api/show/health`, `/api/shows`.
- Inventory: `/api/products`, `/api/product/<sku>`, `/api/product/lookup/<code>`, `/api/inventory/*`.
- Returns (AI bearer-key enabled): `GET/POST /api/returns`, `/api/returns/<id>`, `/api/returns/search`, `PATCH /api/returns/<id>`, `/api/returns/<id>/notes|items|photo|action`, `/return-photo/<id>`.
- Tracking: `/api/warp/track`; packing media `/api/recordings`, `/media/video/<fn>`.
- Audit: `/api/audit-log`.
Effort: a consolidated `GET /api/...` read layer for the AI is **S** (they mostly exist; they just need bearer-key auth like Returns has).

**22. Webhooks / events (new order, status change)? Can it push on new return/reply card?**
Today: We **receive** webhooks (TikTok order webhooks; Whatnot Standard-Webhooks verified) but we do **not emit outbound** webhooks/events to third parties. There's email (Resend) for some flows. No outbound "a return was created" push yet.
Where: inbound webhook verify helpers; `RESEND_API_KEY` email.
Effort: **S** — add an outbound webhook (fire-and-forget POST with timeout) on `return_cases` insert and on `reply_cards` insert, signed like the inbound ones. This is better than AI polling and I'd recommend it (see H/27).

**23. Search / full-text across buyers & orders?**
Today: **Yes.** `/api/search` already searches orders (tracking, shipment id, buyer, recipient), customers, products, shows, and people in one call. Returns search (`/api/returns/search`) covers tracking/order/username/name. It's `LIKE`-based, not FTS, but fast at current volume with the indexes added in cycle-53.
Where: `/api/search`, `/api/returns/search`.
Effort: **XS** to expose; **S** if you want true FTS5.

**24. Rate limits / performance for an AI polling every few hours?**
Today: Fine. Polling every few hours is trivial load. The real lesson (the outage we fixed) is: **never do synchronous external lookups inside a request on the hot path** — that starved gunicorn workers during a live. For the AI: use `updated_since` filters (Returns already supports it) so each poll is cheap, keep any external call off the request thread, and every outbound call must have a timeout (an existing server invariant).
Where: `/api/returns?updated_since=`; shared rate limiter exists.
Effort: **XS** — prefer a webhook (Q22) over frequent polling.

**25. Audit log — generic or returns-only?**
Today: **Three layers, generic overall.** (1) Global `audit_log` (actor, role, action, detail, ip) for sensitive actions across the app; (2) per-order events `order_events` via `_oev`; (3) Returns `return_log` (actor incl. "AI", action, old→new) per case. The AI's writes are audited in layer 3 today.
Where: `audit_log` + `/api/audit-log` + `/admin/audit`; `order_events`; `return_log`.
Effort: **XS** to expose a read; **S** to route all CRM/AI writes through one generic `audit(actor, entity, entity_id, action, old, new)` helper so customer-note and reply-card edits are audited the same way.

---

## H. Recommendations

**26. Simplest way to add (a) `GET /api/customers/{username}`, (b) a Reply Queue, (c) auto-fill a reply card.**

(a) **Customer endpoint with history + risk stats** — *almost free.* `GET /api/customers/<username>` exists and returns full history. Add: total $ spent (sum `shipment_items.revenue`), return rate (returns cases / shipments), RTS count, cancellation rate → a `risk` block. Add bearer-key auth so the AI can read it. **Effort: S.**

(b) **Reply Queue (draft → owner approve → sent)** — new, but a direct clone of the Returns pattern. One `reply_cards` table (platform, store_account, order_id, username, channel, inbound_text, draft_text, status[draft|approved|sent], author, approved_by, timestamps) + endpoints `GET/POST /api/replies`, `PATCH /api/replies/<id>`. **The AI bearer key may create/draft; only an admin/cs session may set `sent`** (same per-field gate as Returns `decision`). A small `/admin/replies` screen for the owner. **Effort: M.**

(c) **Auto-fill a reply card from order no./username** — reuse `_resolve_shipment_by_code` + `/api/customers/<username>`: given an order/tracking/username, pre-populate the card with customer, order, items, packing video, delivery status, and any open return. **Effort: S** on top of (b).

**27. What I'd build differently / warn you about.**
- **Don't poll — push.** Add outbound signed webhooks on new return / new reply card (Q22). Polling works but a webhook is cheaper and near-real-time.
- **Generalize the API key now (Q19).** Move from one `RETURNS_AI_KEY` to a scoped, revocable `api_keys` table before you give the AI more surfaces. You want to be able to revoke the AI's key in one click and to say exactly what it can touch (`customers:read`, `replies:draft`, never `replies:send`, never money).
- **Cross-account customer identity is a real project (Q2), not a field.** It breaks tenant isolation. If you need "is this the same person on TikTok and Whatnot," design a deliberate contact-matching layer in `platform.db` with its own access rules — don't bolt it onto the org DBs.
- **The AI never approves money or messages-sent.** Keep the human gate on refunds, reship/label spend, and "sent to customer," exactly as Returns gates `decision`. The AI drafts; the owner approves — enforce it server-side per field, not in the UI.
- **PII is the ceiling, not the code.** The biggest unlocks (TikTok return/refund sync, TikTok CS messages, Whatnot buyer address via API) are **authorization/scope approvals on the platform side**, not engineering. Line those up in parallel.
- **Keep external calls off the request thread** (the outage lesson).

**28. Rough effort estimate.**

| Item | Effort | Gated on |
|---|---|---|
| (a) `GET /api/customers/<username>` + risk stats + bearer auth | **S** (~½ day) | — |
| (b) Reply Queue (draft→approve→sent) + `/admin/replies` | **M** (~1–2 days) | — |
| (c) Auto-fill reply card from order/username | **S** (~½ day) | needs (b) |
| Customer notes/tags/flags (Q5) | **S** | — |
| Scoped, revocable API keys (Q19) | **S** | — |
| Outbound signed webhooks on return/reply (Q22) | **S** | — |
| TikTok return/refund sync into cases (Q14) | **M** | **TikTok Reverse scope approval** |
| TikTok CS message read (Q16) | **M–L** | **TikTok messaging scope approval** |
| Cross-account customer identity (Q2) | **L** | product decision |

**Suggested first slice (all code, no platform approval needed):** (a) customer read + risk, (b)+(c) reply queue with AI-drafts/owner-approves, customer notes, and scoped API keys. That gives the AI Chief of Staff a real CRM surface it can read and draft into, with the owner holding every send/approve — and it reuses the exact auth + audit pattern the Returns module already proved in production.
