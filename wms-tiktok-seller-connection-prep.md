# TikTok Shop — Seller Account Connection (prep)

The OAuth connect flow already exists (`/api/tiktok/connect` → TikTok consent → `/api/tiktok/callback` stores tokens in `tiktok_shops`, per-org). Here's exactly what's needed to connect a live seller account.

## Important constraint (where the connection must happen)
Token exchange (`_tt_token_exchange`) runs through `_tt_request`, which **short-circuits to `SAFE_MODE` in staging**. So a real seller account **cannot be connected on Safe-Mode staging** — the authorize + token exchange only complete where external calls are allowed, i.e. **Production**. This is by design (Safe Mode blocks all outbound TikTok calls). Product/SKU sync was therefore built and tested in staging with mocked calls; it goes live against a real seller once connected in Production after the Cycles 1–6 release.

## Server prerequisites (Production env — names only, set values in your secret store)
- `TIKTOK_APP_KEY`, `TIKTOK_APP_SECRET` — your Partner Center app credentials.
- `TIKTOK_SERVICE_ID` — custom-app service id (or set `TIKTOK_AUTHORIZE_URL` to the exact authorize URL TikTok gives you).
- Redirect URL registered in Partner Center must be **`https://getwhatnot.com/api/tiktok/callback`** (exact match — this is what the callback route expects).
- Required scopes (approve in Partner Center): seller shop info, **product read**, order read, and webhook — product read is what the new Product/SKU sync needs.

## Connection steps (you perform the consent — I cannot enter your credentials)
1. Confirm the env vars above are set on Production and the redirect URL is registered + scopes approved.
2. As an admin, open **`/api/tiktok/connect`** in the app → it redirects to TikTok's authorize portal.
3. Sign in to the TikTok Shop seller account and approve the scopes.
4. TikTok redirects back to `/api/tiktok/callback`; the app exchanges the code, resolves `shop_cipher`, and stores tokens for your org in `tiktok_shops`.
5. Verify: `GET /api/tiktok/status` shows the shop connected with a valid token expiry.
6. Then trigger the first catalog sync: `POST /api/tiktok/products/sync` → check `GET /api/tiktok/products` (matched vs unmatched SKUs).

## Org isolation (preserved)
Tokens, shops, products, and orders are all keyed by `org_id`; the connect flow uses a per-org `state`, and every sync/query filters by the current org. One seller account connects to exactly one org.
