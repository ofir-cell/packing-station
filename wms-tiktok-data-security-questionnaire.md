# TikTok Shop — Data Security & Privacy Review answers (Live Ops Hub / Btrade LLC)

Ready answers for the DSPR and US Data Security Questionnaire. The exact questions vary and
appear only when Partner Center opens the review, so these are grouped by the topics TikTok
always covers. Paste the matching answer; adjust wording to the live form. Everything here
reflects what's actually implemented — don't claim controls you don't have.

## Company & contact
- **Legal entity:** Btrade LLC (Florida LLC)
- **D-U-N-S:** 10-114-2825
- **Registered address:** 4322 SW 84th Ter, Davie, FL 33328, USA
- **Data protection / security contact:** Ofir — ofir@5secbeauty.com
- **Privacy policy:** https://liveopshub.com/privacy · **Terms:** https://liveopshub.com/terms

## What data the app accesses (data inventory)
- **Order data** from authorized shops: buyer name, shipping address, order items, order
  status, ship-by deadline. Used to pick, pack, and ship the order.
- **Product/catalog data:** SKUs and product names, for barcode-to-product matching.
- **No payment card data** is accessed or stored. **No consumer login credentials** are accessed.
- Access is limited to shops that have explicitly authorized the app via OAuth.

## Purpose & minimization
- Data is used **only** to fulfill the seller's own orders (pick/pack/ship) and is not sold,
  shared for advertising, or used for any secondary purpose.
- We request the **minimum scopes** needed (order read, product read, webhook; fulfillment
  only if used). No scope is requested that the product does not exercise.

## Where data lives (hosting & subprocessors)
- **Application hosting:** Railway (US region).
- **Backups / object storage:** Cloudflare R2.
- **Shipping:** ShipStation / USPS (for label + tracking on the seller's own shipments).
- **AI assistance (if used):** Anthropic.
- **Spreadsheet/ops integration:** Google Apps Script.
- Each is listed in the public privacy policy's subprocessor table.
- Data is processed and stored in the **United States**.

## Access control
- Multi-tenant isolation: each seller org's data is stored separately (per-org databases);
  one tenant cannot read another's data.
- Application access requires authenticated login; roles (admin / worker) limit what each
  user can see and do. Admin actions are audit-logged.
- TikTok access tokens and shop credentials are stored **encrypted** and are never exposed to
  other tenants or logged in plaintext.

## Encryption
- **In transit:** HTTPS/TLS for all traffic (API calls, webhooks, the console). HSTS enabled.
- **At rest:** TikTok tokens and shop cipher stored encrypted; backups stored in Cloudflare R2.

## Data retention & deletion  ← the section reviewers weight most
- **On deauthorization:** when a seller revokes access (TikTok deauthorization webhook,
  topic 6), the app **immediately** deletes stored access/refresh tokens and shop cipher and
  marks the shop inactive, then **purges or anonymizes** that shop's order data. Buyer
  name/username, address, and postal code on imported shipments are anonymized.
- **Retention window:** remaining data is deleted or anonymized within **30 days**.
- **Self-serve deletion:** a seller can delete their account in-app (Account → Delete my
  account on /me), which deletes the account and triggers data deletion; a last-admin
  deletion can also wipe the organization's data on confirmation.
- **Admin-initiated immediate deletion:** `POST /api/tiktok/forget` removes a shop's data on demand.
- Implemented in: `_tt_mark_deauthorized`, `_tt_purge_shop_data`, `_tt_retention_purge`
  (30-day), `/api/account/delete`, `_delete_org_data`.

## Logging & monitoring
- Application and access logs are kept; admin/security-relevant actions are audit-logged
  (`alog`). Tokens and secrets are not written to logs in plaintext.
- Production is monitored (host metrics + error logs) and backed up (Backup V2 to R2).

## Incident response
- A security contact (ofir@5secbeauty.com) receives reports. On a suspected breach we
  investigate, contain, revoke affected tokens, and notify affected sellers and TikTok as
  required. (If you want, I can draft a one-page written incident-response policy to attach.)

## Vulnerability & secure development
- CSRF protection on all mutating endpoints; security headers (CSP, HSTS, X-Frame-Options)
  on every response; session rotation on login; rate limiting on login and sensitive routes;
  bcrypt password hashing. Changes go through tests before deploy.

## Sub-processing & third-party sharing
- Data is shared only with the subprocessors listed above, strictly to operate the service
  (hosting, backup, shipping). No sale of data; no advertising use.

---
### To strengthen the submission (optional, I can draft any of these)
- A standalone **written Information Security Policy** (1–2 pages).
- A standalone **Incident Response Plan**.
- A **data-flow diagram** (seller → TikTok API → Live Ops Hub → carrier).
These aren't always required, but US-market reviewers sometimes ask. Say the word.
