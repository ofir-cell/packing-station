# Security baseline — mobile app, before outside sellers and before a no-2FA demo account

- Date: 2026-11-10 · Reviewer: security-reviewer · Code: `main` at `b032603` · Not a PR review.
- Question: what MUST be fixed before external sellers are let in, and before a demo/reviewer account without 2FA can exist?
- Method: Flask test client against the throwaway database of `tests/conftest.py`, two extra orgs, every role (worker, picker, host, cs, manager, admin). No request left this machine; every outbound transport was replaced by a recorder. Swift was read, not run.
- Tests: `tests/test_security_mobile_baseline.py` — 6 passing guards (`test_holds_*`) and 14 strict-xfail demonstrations. Run the demonstrations for real with `python3 -m pytest -q tests/test_security_mobile_baseline.py --runxfail` (14 fail, each for the stated reason).
- Suite: `python3 -m pytest -q tests` → **376 passed, 14 xfailed** (was 370 passed before this review).

## Verdict

**BLOCK for outside sellers and BLOCK for the demo account**, for a short and specific list. The core that the 2026-07 audit called the go/no-go gate is sound: tenant isolation holds on every endpoint the app calls.

| Severity | Findings |
|---|---|
| BLOCK-EXTERNAL | SEC-1, SEC-2, SEC-5, SEC-6 |
| BLOCK-DEMO | SEC-3, SEC-4, SEC-7 |
| FIX SOON | SEC-8 … SEC-16 |
| NOTE | SEC-17 … SEC-20 |

### What was verified and holds (tests pass)

| Claim | Test |
|---|---|
| Org B, in every role, cannot read or change org A's order through `/api/shipment`, `/api/pick/<id>`, `/api/pick/complete`, `/api/pick/issue`, `/api/shows`, `/m/api/pick/extras`, `/api/upload` | `test_holds_cross_org_mobile_endpoints` |
| Org B cannot fetch org A's packing video with the exact file name; media keys start with the owning org; playback is admin/cs only | `test_holds_cross_org_packing_video` |
| Session cookie is `HttpOnly; Secure; SameSite=Lax`; every POST without `X-CSRF-Token` is 403; signed-out requests get nothing; `/api/mobile/session` sends no CORS header | `test_holds_session_csrf_and_cookie_flags` |
| Label purchase on the shared carrier account is refused for non-owner orgs | `test_holds_label_purchase_fenced_to_owner_orgs` |
| An admin who has not enrolled 2FA is held at the gate; a suspended org's live sessions get 402 and cannot sign in | `test_holds_unenrolled_admin_and_suspended_org_are_held` |
| Support tickets are per org | `test_holds_support_tickets_are_per_org` |

Role matrix measured on the mobile endpoints (own org): worker / picker / cs / manager / admin → 200 on all Pick endpoints; host → 403 on `/m/pick`, `/m/api/pick/extras`, `/api/shows`, `/api/pick/*`; `/media/video/*` → admin, cs, manager only. The exceptions are SEC-8.

Why isolation holds: each org has its own SQLite files, selected from `session["org"]` only (`app.py:117-145`, `sdb()` `app.py:1248`). Item ids repeat across orgs, so a guessed id lands in the caller's own database.

## Findings

### SEC-1 — BLOCK-EXTERNAL — Admin powers through `extra_roles` skip mandatory 2FA
- Repro: `test_sec1_extra_role_admin_must_enroll_2fa`. An admin creates a user with `role: worker, extra_roles: ["admin"]`; that user signs in with a password only, `must_setup_2fa` is false, and `/api/users` (true-admin only) answers 200.
- Evidence: `_twofa_required` looks at `role` only (`app.py:764-770`); the role decorators use the full role set (`app.py:4136-4160`); `extra_roles` accepts `admin` (`app.py:12633-12634`, `12667-12668`). A Warehouse Manager (near-admin, can request label rates and most admin screens) is also never asked for 2FA.
- Fix: require 2FA when `admin` (and decide: `manager`) is anywhere in the effective roles; apply the same rule in `_finalize_login`. Owner: **programmer**.

### SEC-2 — BLOCK-EXTERNAL — A badge scan alone opens an admin session
- Repro: `test_sec2_badge_login_never_yields_admin`. A worker with a badge is promoted to admin; the badge still works and `/api/badge-login` returns `role: admin` with no password and no 2FA (`must_setup` is false too). The same happens for a worker with `extra_roles: ["admin"]`, who is issued a badge at creation.
- Evidence: `api_badge_login` builds the session without any 2FA or role check (`app.py:12744-12775`); `api_user_roles` keeps the badge on promotion (`app.py:12660-12681`); the badge is printed on a card and is limited only to 40 failures / 5 min per IP.
- Fix: badge sign-in only for accounts whose effective roles are floor roles (worker/picker); remove the badge when a user gains admin/manager/cs; otherwise send the badge user through password + 2FA. Owner: **programmer**.

### SEC-3 — BLOCK-DEMO — `twofa_exempt` works in any company
- Repro: `test_sec3_twofa_exempt_only_inside_a_sandbox_org`. An admin record with `"twofa_exempt": true` in an ordinary paying org signs in with a password and has full admin.
- Evidence: `app.py:767-769`. The flag is a bare field in the shared `users.json`; nothing ties it to a demo org, and `ios/APP_STORE.md:63` tells Ofir to set it by hand on an **admin** account.
- Fix: honour the exemption only when the user's org is flagged as the demo/sandbox org in `platform.db`; refuse it everywhere else. Owner: **programmer**.

### SEC-4 — BLOCK-DEMO — No per-company outbound fence
- Repro: `test_sec4_sandbox_org_sends_nothing_outside`. As admin of a fresh non-founding org: `POST /api/email/test {"to": "someone@outside.example"}` sends from the platform's sender; `POST /api/label/rates` reaches the owner's carrier account.
- Evidence: the only global switch is `STAGING_SAFE` / `IS_STAGING`, which is per process, not per org (`app.py:60-74`, `1126`). Carrier, email, AI and barcode credentials are single platform-wide environment values (`app.py:961-1007`, `2256-2283`, `8539`).
- Outbound side effects a signed-in user of any org can reach today (static call-graph of `app.py` + the tests above):

| Effect | Routes | Roles | Fenced per org today? |
|---|---|---|---|
| Buy shipping label (money) | `/api/label/buy`, `/api/label/buy-multi`, `/api/giveaway/<id>/buy-label` | admin, cs, manager | **Yes** — `_can_buy_labels()` (`app.py:2289-2294`) |
| Carrier rate / carrier list calls on the owner's account | `/api/label/rates`, `/api/label/rates-multi`, `/api/giveaway/<id>/rates`, `/api/ship/carriers`, `/api/ship/carriers/prefer` | admin, cs, manager | No (SEC-5) |
| Email to any address | `/api/email/test`, `/api/hires` (invite), `/api/hires/<id>/send-invite` | admin, cs, manager | No |
| TikTok Shop API (incl. combine / ship-package / documents once a shop is connected) and starting a shop connection | `/api/tiktok/connect`, `/api/tiktok/pull`, `/regroup`, `/batch/prepare`, `/delivery-refresh`, `/combinable`, `/live-sessions`, `/live-detail`, `/debug`, `/api/shipping/backfill` | admin (some cs) | Only by "no shop connected" |
| WARP freight quote / **book (charges a card)** / track | `/api/warp/quote`, `/book`, `/verify`, `/track` | admin (quote/track: cs, manager) | Per-org key in settings; a demo admin can paste a key |
| USPS tracking | `/api/tracking/refresh` | admin, cs | No |
| Anthropic (order/address/invoice/product text leaves the server; costs money) | `/api/giveaway/parse-address`, `/api/po/extract-invoice`, `/api/products/import-pdf`, `/api/scanit/product/<id>/scripts` | admin, cs, host | No |
| Barcode lookup service | `/api/barcode/lookup/<code>`, `/api/scanit/scan`, `/api/live/scan`, `/api/live/match`, `/api/live/kit/add` | admin, cs, host, worker, picker | No |
| Support ticket / plan request to the platform owner | `/api/support/tickets`, `/api/billing/request-plan` | any | No |
| Public new-hire links that collect ID documents | `/api/hires` | admin, cs | No |
| R2 writes (videos, photos, product images, invoices, attachments) | `/api/upload` and others | any | Namespaced by org, not capped |
| SMS, PrintNode, outbound webhooks | — | — | None exist in the code today |

- Fix: one `sandbox` flag on the organization, checked at the transport layer (`_send_email`, `_ss`, `_ups`, `_usps_*`, `_tt_request`, `_warp_api`, `_barcode_lookup_online`, the Anthropic client, `api_tiktok_connect`), returning a canned success so screens still work. Owner: **programmer**.

### SEC-5 — BLOCK-EXTERNAL — The owner's carrier account is exposed to every company
- Repro: `test_sec5_owner_carrier_account_not_disclosed_to_other_orgs`. `GET /api/ship/carriers` as admin, cs or manager of another org returns the platform owner's UPS account number in `carrier_id` and `name`.
- Evidence: `app.py:15379-15391`; rate routes are not behind `_can_buy_labels()` (`app.py:15150`, `15420`, `15638`), so any org can quote on, and learn the negotiated prices of, the owner's ShipStation/UPS account. A carrier account number is enough for third-party-billing fraud.
- Fix: put every carrier route (list, prefer, rates) behind the same per-org gate as buying, and never return the account number. Owner: **programmer**.

### SEC-6 — BLOCK-EXTERNAL — Deleting a company leaves its data behind
- Repro: `test_sec6_org_wipe_removes_platform_rows_and_media`. Last admin sends `POST /api/account/delete {"wipe_org": true}` → `org_deleted: true`, but the org's `tiktok_shops` row (access and refresh tokens) is still in `platform.db`, and storage is never asked to delete anything.
- Evidence: `_delete_org_data` removes the local folder, the `organizations` row and the users only (`app.py:4797-4815`). Not removed: R2 objects under `<org>/videos|photos|labels|documents|products|invoices`, hire documents in the HR bucket, `tiktok_shops` / `tiktok_orders` / `tiktok_events`, tickets and attachments, billing requests, backups. A later company created with the same org id would inherit the old R2 prefix.
- Also: deleting one user removes the login only; the person's name stays on orders (`picked_by`, `packed_by` — measured), in `packing_log.csv`, the audit log, and their voice in packing videos. That may be legitimate business-record retention, but the policy does not say so (see Privacy).
- Fix: delete every platform row and every storage prefix of the org (and revoke TikTok tokens), refuse reuse of a deleted org id, and state in the policy what is kept after a single user is deleted. Owner: **programmer**.

### SEC-7 — BLOCK-DEMO — Account and company deletion need only the session cookie; the demo account can delete itself
- Repro: `test_sec7_account_delete_requires_password` (a worker deletes the account with no password). Measured in the exploration run: the last admin of an org gets 409 `need_org_confirm`, repeats with `wipe_org: true`, and the whole company is gone — no password, no 2FA code.
- Evidence: `app.py:4817-4845`; the route is also open during the 2FA-setup gate and the billing gate (`app.py:3893`, `3918`). The reviewer notes tell Apple to test "Delete my account" (`ios/APP_STORE.md:70`): with a shared admin demo login that deletes the demo login, and one more tap wipes the demo company, in the middle of review. There is no reset.
- Fix: require the current password (and a 2FA code when enrolled) for deletion; in the sandbox org make deletion a simulated success followed by an automatic re-seed. Owner: **programmer**.

### SEC-8 — FIX SOON — A Host can read any order and mark it packed
- Repro: `test_sec8_host_cannot_pack_or_read_orders`. Host is 403 on `/m/pick`, yet `GET /api/shipment/<code>` returns the whole row (`address_full`, `postal_code`, `shipping_fee`, buyer names) and `POST /api/upload` sets `status='packed'` and deducts stock.
- Evidence: `@req_login` only on `api_shipment_lookup` (`app.py:6662-6664`, returns `dict(row)` at `6722`), `api_upload` (`app.py:5088-5090`), `api_giveaway_mark_added` (`app.py:14852-14854`).
- Fix: `req_role` with the packing roles on all three; return a named field list instead of the row. Owner: **programmer**.

### SEC-9 — FIX SOON — `/api/upload` stores any bytes as a packing video
- Repro: `test_sec9_upload_rejects_non_video` — an HTML file is accepted and saved as `IOS_<tracking>.webm`.
- Evidence: `app.py:5104-5116` (a missing header is only logged); the whole body, up to 250 MB, is read into memory per request (`app.py:5106`, `3852`).
- Fix: reject anything that is neither MP4 (`ftyp`) nor WebM (EBML), cap packing videos well below 250 MB, stream to storage. Owner: **programmer**.

### SEC-10 — FIX SOON — Issued sessions cannot be ended
- Repro: `test_sec10_password_reset_revokes_old_sessions`; measured too: a session cookie copied before `/logout` still works after it.
- Evidence: sessions are client-side signed cookies, valid 7 days (`app.py:3857`); `_session_revocation` reacts only to a deleted user or a role change (`app.py:3939-3963`).
- Fix: a per-user session version in `users.json`, stored in the session and bumped on password change, 2FA change, sign-out-everywhere and logout. Owner: **programmer**.

### SEC-11 — FIX SOON — Login throttle has no per-account cap
- Repro: `test_sec11_login_lockout_is_per_account` — 30 wrong passwords for one user from 30 addresses, never a 429. From one address it is correct: 8 failures, then 429 (measured).
- Evidence: key is `ip|username` (`app.py:845`, `879-896`); the 2FA code step uses the same key (`app.py:4928`).
- Fix: add a per-username counter (and one for the 2FA step) independent of IP, with back-off. Owner: **programmer**.

### SEC-12 — FIX SOON — TikTok shop connection is not bound to the browser that started it
- Repro: `test_sec12_tiktok_callback_needs_the_initiating_session` — a state minted for org A, opened by a signed-out browser, attaches the authorising seller's shop to org A.
- Evidence: `_tt_state` signs org + time + nonce only (`app.py:16444-16458`); `api_tiktok_callback` needs no session (`app.py:17298-17307`); a shop may be attached to several orgs (`ON CONFLICT(org_id,shop_id)`, `app.py:16466-16469`). An admin of one company can send their connect link to another seller and receive that seller's orders and buyers.
- Fix: keep the nonce in the initiating session and require the callback to arrive with that session as an admin of the same org; refuse a shop already attached to another org. Owner: **programmer**.

### SEC-13 — FIX SOON — New-hire document reader falls back to the founding company's files for every org
- Repro: `test_sec13_hire_doc_legacy_fallback_only_for_founding_org`. Precondition stated honestly: the row was inserted directly; it needs an upload row in org B whose own object is missing and whose hire id / step id / field / file name match a pre-namespacing object. I did not find a UI path that produces that state.
- Evidence: `_hire_upload_key_candidates` drops the org segment for any org (`app.py:11950-11958`), unlike `_r2_resolve`, which limits the legacy key to the founding org (`app.py:258-273`). These are ID photos and I-9 evidence.
- Fix: legacy fallback only when the org is the founding org. Owner: **programmer**.

### SEC-14 — FIX SOON — Creating a company from the Organizations console returns 500
- Repro: `test_sec14_platform_owner_can_create_an_org`.
- Evidence: `@app.route("/api/orgs/create")` and `@req_super` sit on the helper `_create_tenant` instead of the view `api_orgs_create` (`app.py:13365-13367`, view at `13422`). The intake provisioning path still works because it calls the helper inside a super-admin request.
- Fix: move the two decorators to `api_orgs_create`. Owner: **programmer**.

### SEC-15 — FIX SOON — iOS: sign-in host list is a suffix match (by reading)
- Evidence: `isAuthFlow` uses `h.hasSuffix("tiktok.com")` etc. (`ios/LiveOpsHub/Web/DashboardWebView.swift:113-117`), so `eviltiktok.com` loads inside the signed-in web view instead of Safari. Our own hosts are matched correctly (`isOurHost`, line 109-111: exact, apex, or `.getwhatnot.com`).
- Fix: `h == d || h.hasSuffix("." + d)`. Owner: **ios-engineer**.

### SEC-16 — FIX SOON — iOS: the bridge accepts messages from host-less frames (by reading)
- Evidence: `isOurs` returns true when the URL has no host (`DashboardWebView.swift:102-105`) and the bridge check uses it on `message.frameInfo.request.url` (line 274); sub-frames of any host are allowed to load (line 140) and the site CSP allows `frame-src https:` (`app.py:4024`). An `about:blank` / `srcdoc` child of a third-party frame could call `scan`, `pack`, `haptic`. Impact is small — the bridge exposes only those three actions, none reads data, and `scan` needs the user to scan — but the rule in the role file is "our own hosts only".
- Fix: accept bridge messages only from the main frame with `frameInfo.securityOrigin.host` passing `isOurHost`. Owner: **ios-engineer**.

### Notes
- **SEC-17 — NOTE — Credentials in logs and at rest.** First boot prints generated initial passwords, and the generated super-admin password, to stdout → Railway logs (`app.py:932`, `3601-3608`). TikTok access/refresh tokens, TOTP secrets and WARP keys are stored unencrypted (`app.py:16466-16478`, `4972`, `7692-7696`) while the privacy policy says "encrypted credentials". No secret was found in the repository (pattern scan of the tree; values not printed). Owner: programmer.
- **SEC-18 — NOTE — iOS housekeeping (by reading).** Downloaded exports stay in `tmp/downloads` (`DashboardWebView.swift:252-260`); cookie sync matches by suffix, so `whatnot.com` cookies are copied to and deleted from the native store (`WebSession.swift:22-30`); there is no native sign-out yet (board item 1). Good: no credential or token in UserDefaults or Keychain, nothing logged, ATS default, no URL scheme, web inspector only in DEBUG, a failed or finished upload deletes the local video. Owner: ios-engineer.
- **SEC-19 — NOTE — Shared control plane.** `users.json` is global, so "Already exists" on user creation tells one company that a username exists in another (`app.py:12644`); `GET /api/stations` returns one station list for all companies (`app.py:5040`). Owner: programmer.
- **SEC-20 — NOTE — Still open from `SECURITY_AUDIT.md`.** CSP allows `'unsafe-inline'` (`app.py:4018`); no dependency scanning in the repo; no documented secret-rotation plan.

## Status of `SECURITY_AUDIT.md` (July 2026) for multi-company use

| Item | Status now |
|---|---|
| P0-1 tenant isolation | Done differently (one database per org). Verified on all mobile endpoints. |
| P0-2 object ownership | Holds by construction on the endpoints tested. Gap: SEC-13. |
| P1-3 CSRF | Done (double-submit, `app.py:3878-3888`). Verified. |
| P1-4 HSTS | Present in code (`app.py:4014`). |
| P1-5 real client IP | `ProxyFix` present (`app.py:3862`). Hop count on Railway not verifiable here; see SEC-11. |
| P1-6 R2 not guessable | Keys namespaced per org, 15-minute signed links (`app.py:221`, `254-273`). Bucket privacy not verifiable here. |
| P2 2FA for admin | Done, with the gaps SEC-1, SEC-2, SEC-3. |
| P2 audit log | Present. |
| P2 CSP, dependency scanning, rotation plan | Open (SEC-20). |
| `MULTITENANT_DEPLOY.md` "hire-uploads folder" | Keys are org-prefixed now; fallback gap SEC-13. |

## Requirements for the demo/reviewer company

The programmer builds to this list; I verify each line with a test before CLEAR.

1. **A flag on the organization**, not on the user: `sandbox` in `platform.db`, set only from the platform console, never by a tenant route. (SEC-3)
2. **2FA exemption only inside that org.** `twofa_exempt` on a user of any other org is ignored. (SEC-3)
3. **Least role.** The reviewer account is not `admin`. A manager-level role that can open Dashboard, Pick, Pack and "Me" is enough; no user management, no billing, no TikTok connect, no settings.
4. **Nothing leaves the server** for a sandbox org: email, carrier (rates and buy), USPS, TikTok (connect included), WARP, Anthropic, barcode lookup, tickets/plan requests to the owner, public hire links. Each returns a canned success. One test per transport, with the transport replaced by a recorder that must stay empty. (SEC-4)
5. **Cannot reach a real company.** The existing isolation tests run with the sandbox org as "org B" against the founding org; impersonation into or out of the sandbox org is refused.
6. **Credentials cannot be changed from inside**: password change, 2FA enrol, user add/delete/role change, badge issue and branding are refused or no-ops for sandbox users, so one reviewer cannot lock out the next.
7. **Deletion is simulated.** `POST /api/account/delete` in the sandbox org answers success, signs the session out, and the account still exists; `wipe_org` never deletes. (SEC-7)
8. **Resettable.** A platform-console action and a nightly job re-seed the fake orders, shows and videos; packing uploads from the sandbox are size-capped and expire.
9. **Seed data is fake**: invented buyers and addresses, tracking numbers that are not real carrier numbers, no copy of a real company's rows.
10. **Bounded**: login throttle per account (SEC-11), a session lifetime shorter than 7 days for the sandbox, a banner that says "Demo company", and every sandbox action in the audit log.
11. **SEC-1 and SEC-2 fixed first** — otherwise a sandbox user with a floor role plus `extra_roles` or a badge re-opens the door.
12. The password lives only in App Store Connect and Railway, never in the repo; `ios/APP_STORE.md` gets the role and wording corrected (release-manager).

## Privacy answers vs. reality

| Topic | `PrivacyInfo.xcprivacy` | `ios/APP_STORE.md` label table | What the code does |
|---|---|---|---|
| Name, User ID | declared | listed | Collected (session, `/api/mobile/session`). Match. |
| Photos or Videos, Audio | declared | listed | Packing video with microphone audio uploaded to `/api/upload`. Match. |
| Other user content (orders) | declared | listed | Match. |
| **Email address** | declared | **not listed** | New-hire emails are collected on the site shown in the Dashboard tab; staff accounts themselves have a username, no email. The table says "This matches" the manifest — it does not. |
| **Physical address** | declared | **not listed** | Buyer shipping addresses are shown and returned to the app (`/api/shipment/<code>` returns `address_full`). Must be on the label. |
| Purchases / order history of buyers | not declared | only as "other user content" | Order lines per buyer are processed. Decide and declare consistently (app-review). |
| Sensitive / government ID | not declared | not listed | New-hire ID photos and I-9 evidence are uploaded through the same site the Dashboard tab shows. Either declare it or keep that flow out of the app. |
| Diagnostics / usage | not declared | not listed | Server keeps a heartbeat, last-login time and an audit log with IP address (`app.py:639`, `4519`). No third-party analytics SDK in the app. |
| Tracking | false | "none" | Correct: no tracking domains, no ad SDK. |
| Photo library | — | — | `NSPhotoLibraryAddUsageDescription` is declared in `ios/project.yml` but no code writes to Photos. Remove it or use it (app-review will flag it). |
| Required-reason APIs | UserDefaults CA92.1, FileTimestamp C617.1 | — | Plausible for the code read; not checked against a build. |

Privacy policy (`site/privacy.html`) against the code:
- "We do not write to your TikTok Shop" — the app creates TikTok shipping labels / combines packages. Already flagged in `ios/APP_STORE.md`; still open.
- "Encrypted credentials" — stored unencrypted (SEC-17).
- "Account data: name, email" — staff accounts have no email field.
- Subprocessors listed: Railway, Cloudflare R2, ShipStation, USPS, Anthropic, Google. In the code and missing from the list: UPS (direct), WARP, Resend / SMTP provider, the barcode lookup service, TikTok itself. Anthropic is described as "address parsing"; it also receives invoices, product PDFs and product text.
- "Delete or anonymize within 30 days after deauthorization" and "delete their account in-app" — see SEC-6 for what actually remains.
- New-hire documents (ID, I-9, signatures with IP and user agent) are not described at all.

Owners: release-manager for `ios/APP_STORE.md`, ios-engineer for the manifest and `project.yml`, Ofir for the legal text.

## Could not exercise

- **Swift**: every iOS finding and every iOS "good" above is by reading. No device, no simulator.
- **Production configuration**: Railway variables, the real proxy hop count for `ProxyFix`, whether the R2 bucket is private, real signed-URL behaviour, HSTS on the live host. Nothing was sent to getwhatnot.com or Railway.
- **Real third parties**: TikTok, ShipStation, UPS, USPS, WARP, email, Anthropic — only that the call would be made, with the transport replaced.
- **The desktop site as a whole.** The Dashboard tab shows every desktop screen, so the app's real surface is all of `app.py`. I tested the endpoints `pick.js`, `mobile.js` and the Swift client call, plus sign-in, sessions, deletion, uploads and media. The several hundred other routes were not role- or tenant-tested here (existing suites `test_authz.py`, `test_tenant_isolation.py`, `test_cycle4_access.py` cover part of them). They need their own pass before outside sellers.
- **Output escaping** beyond `/m/pick`: one server-side case is covered by the existing `test_m_pick_page_is_the_mobile_screen`; `pick.js` sinks were grep-reviewed (one unescaped value goes to a toast that escapes it), not run in a browser.
- **Webhook signature checks, backups/restore, the label-URL fetcher (`_fetch_label_bytes`, possible server-side request to a stored URL), CI log output, dependency CVEs.**
- **SEC-13** reachability through the UI (see its precondition).
