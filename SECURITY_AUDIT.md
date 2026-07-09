# Security Audit — LiveOpsHub / getwhatnot.com

_Reviewed: July 2026 · Flask on Railway · SQLite · Cloudflare R2_

## Bottom line

The app is in **better shape than most self-built web apps**. The authentication, session,
password, and header fundamentals are done correctly. There is **one critical gap that only
matters once you onboard a second company** (multi-tenant data isolation), and a handful of
worthwhile hardening steps. Nothing here suggests the app is currently exposed or breached.

Priority order for what to do: **P0 (before any external customer) → P1 (soon) → P2 (nice to have).**

---

## What's already good ✅

| Area | Status |
|---|---|
| **Secret key** | Required from env, must be ≥32 chars, app refuses to boot without it. No hardcoded fallback. |
| **Passwords** | bcrypt with 12 rounds; legacy SHA-256 hashes auto-migrate on next login; constant-time compare; dummy-hash timing equalizer so attackers can't tell "user exists" from response time. |
| **Login brute-force** | Rate limiting per IP+user with a window and lockout after N fails. |
| **Session cookies** | `HttpOnly`, `Secure`, `SameSite=Lax`, 7-day lifetime. |
| **SQL injection** | None found. Every query uses parameterized `?` placeholders — even the dynamic `IN (...)` builds placeholders, not values. |
| **Security headers** | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and a real Content-Security-Policy on every response. |
| **Clickjacking** | Blocked twice (`X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`). |
| **File uploads** | `secure_filename` on every upload, extension allow-list on hire docs, CSV validated by extension, 250 MB size cap. |
| **Tokens** | Badge tokens and doc/onboarding IDs use the `secrets` module (cryptographically secure), not `random`. |
| **Debug** | `debug=False` in production. |

---

## P0 — Fix before onboarding any second company 🔴

### 1. Multi-tenant data is NOT isolated
This is the single most important finding.

- The `shipments` table (and order items, giveaways, videos, customers) **has no `org_id` column.**
- Data queries **do not filter by the logged-in user's organization.**
- `session["org"]` is currently used **only for branding** (logo/color), not for scoping data.

**Impact:** With one company (5 Second Beauty) today, this is invisible and harmless. But the
moment a second paying company logs in, **they will see each other's orders, buyers, addresses,
and packing videos.** For a SaaS this is the #1 thing that ends the business.

**Fix (do this before customer #2):**
1. Add `org_id` to every data table: `shipments`, `shipment_items`, `giveaways`, `sku_weights`, `sku_catalog`, `inbound_shipments`, users, settings, etc.
2. Backfill existing rows to `DEFAULT_ORG`.
3. Add `AND org_id = ?` (bound to `session["org"]`) to **every** SELECT / UPDATE / DELETE.
4. Set `org_id` on every INSERT from the session.
5. Add a helper like `current_org()` and route all queries through a small data layer so no future query can forget the filter.
6. Test: log in as org A, confirm you cannot see or fetch any org B record by guessing an ID.

This is a meaningful refactor — worth doing carefully and deliberately, not the night before a launch.

### 2. Enforce object ownership on every ID lookup
Even within one org, confirm that endpoints like `/shipment/<id>`, video links, label PDFs,
and customer detail **check the record belongs to the caller** rather than trusting the ID in
the URL (IDOR — insecure direct object reference). Combine this with the `org_id` filter above.

---

## P1 — Do soon 🟠

### 3. Add CSRF protection on state-changing POSTs
Right now the only CSRF defense is `SameSite=Lax` cookies. Lax blocks most cross-site POSTs, so
you're **not wide open** — but it's not a complete defense (some request shapes and older
browsers slip through). For a money/inventory app, add real CSRF tokens.

- Easiest path: add **Flask-WTF** (`CSRFProtect`) and include the token in your fetch/form POSTs.
- Or set the session cookie to `SameSite=Strict` for the app (note: Strict can log users out when
  following external links into the app, so test the badge/login flows).

### 4. Add HSTS (force HTTPS)
No `Strict-Transport-Security` header today. Add it so browsers refuse to talk to the app over
plain HTTP:
```python
resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
```
(Railway already serves HTTPS, so this is safe to turn on.)

### 5. Fix client IP behind Railway's proxy
Railway sits in front of the app, so `request.remote_addr` is probably the **proxy's** IP, not
the real user's. That means your login rate-limiter may be keying many users to one IP. Add
Werkzeug's `ProxyFix` and read the real client IP from `X-Forwarded-For`:
```python
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
```

### 6. Verify R2 media isn't publicly guessable
Packing videos contain buyer names/addresses on labels. Confirm the Cloudflare R2 bucket is
**private** and media is served through **short-lived signed URLs** (or proxied through an
authenticated Flask route) — not via a public bucket URL that anyone could enumerate.

---

## P2 — Hardening / good hygiene 🟡

- **Tighten CSP:** it currently allows `'unsafe-inline'` for scripts/styles (because templates
  embed JS/CSS inline). This weakens XSS defense. Long-term, move to CSP nonces or external
  files. Not urgent, but it's the ceiling on your XSS protection.
- **Automated dependency scanning:** run `pip-audit` (or enable GitHub Dependabot) so you're
  alerted when Flask/Werkzeug/etc. get a CVE.
- **Backups:** confirm the SQLite DBs (`/data`) are backed up off Railway on a schedule, and that
  you've actually tested a restore. WAL mode is on, which is good.
- **Audit log:** for a business handling money, log admin actions (imports, deletes, commission
  changes, user creation) with who/when. Helps forensics and disputes.
- **Least-privilege review:** you recently opened CSV import to `cs`. Periodically re-check that
  each role has exactly the routes it needs and nothing more.
- **2FA for admin:** optional, but worth it for the admin role given the financial data.
- **Secret rotation plan:** document how to rotate `SECRET_KEY`, R2 keys, and EasyPost keys if one
  ever leaks (rotating `SECRET_KEY` logs everyone out — that's fine, just know it).

---

## Suggested sequence

1. **Now:** HSTS header (5 min), ProxyFix (10 min), confirm R2 is private/signed (P1 #4, #5, #6).
2. **This month:** CSRF tokens (P1 #3), object-ownership checks (P0 #2).
3. **Before selling to any outside company:** full `org_id` isolation (P0 #1) — treat this as a
   go/no-go gate for the SaaS.
4. **Ongoing:** dependency scanning, backups test, audit log.

_This review covers application-level security. It does not cover Railway account security,
Cloudflare account/DNS security, or your own laptop/credentials — enable 2FA on all three of those
accounts too._
