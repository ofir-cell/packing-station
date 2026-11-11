# Design note — the sandbox (demo) company for App Review (M3; SEC-3, SEC-4, SEC-7; R1, K3)

- Date: 2026-11-10 · Author: architect · Code read: branch `spec/email-2fa-and-sandbox` at `dfd536c` (`app.py` 19,583 lines).
- Status: design for the programmer (builds M3 and the M2 pieces SEC-3 / SEC-4 / SEC-7 from it) and for security-reviewer (verifies it). No product code in this note.
- Sibling spec: `docs/specs/2026-11-10-email-2fa.md` (product-engineer, written in parallel — **not read**; where the two meet is marked "→ email-2FA spec").
- Sources: `docs/security/2026-11-10-mobile-baseline.md` (12-point list, SEC-3/4/7), `docs/mobile/APP_BLUEPRINT.md` rev 2 (flows 4.1, 4.2, 4.7, 4.8, 4.9; N3, N12, N15, N17, N21), `docs/mobile/REVIEW-2026-11-10.md` (R1, K3), `docs/mobile/ROADMAP.md` (M2, M3), `docs/mobile/BOARD.md` "Decided by Ofir".
- Every code claim cites `file:line`. What was not read is listed in §11.

## 0. Decisions this note is built on (Ofir, authoritative)

An isolated demo company for Apple's reviewer signs in without 2FA (D1). Its two logins are a **worker and a manager, no admin** (D2). Nothing can leave it. Everywhere else the second factor is an emailed code or an authenticator; the sandbox never asks for a code and never sends email (D3, blueprint rule 5.11). The app is always indigo (D8). Distribution is unlisted, US only (D5).

Words: **sandbox org** = an `organizations` row with `sandbox=1`. **Real org** = every other org. **Founding org** = `DEFAULT_ORG` (`app.py:49`).

## 1. The sandbox flag

### 1.1 Where it lives

One column on the organization, in the control plane: `organizations.sandbox INTEGER NOT NULL DEFAULT 0` in `platform.db` (table at `app.py:347-365`). Never a field on a user: `users.json` is one global file that any admin route can write for its own org (`app.py:12622-12741`), which is exactly why `twofa_exempt` is unsafe today (`app.py:767-769`).

Plus two small control-plane tables (same file):

| Table | Columns | Purpose |
|---|---|---|
| `sandbox_logins` | `org_id, username PRIMARY KEY, role, name, pw_hash, updated_at, updated_by` | The two reviewer logins as Ofir set them. The bcrypt hash only. Reset restores `users.json` from here, so the seed never contains a password and a reset never needs one. |
| `sandbox_state` | `org_id PRIMARY KEY, seed_version, state ('ready'/'resetting'), state_since, last_reset_at, last_reset_by, last_activity_at, upload_count, upload_bytes` | Reset bookkeeping and upload caps, shared by all gunicorn workers. |

### 1.2 Who can set it — create-only, never toggled

The flag is written by exactly one statement: the `INSERT` of a new sandbox org, issued by one new platform-console action (`POST /api/orgs/sandbox/create`, `@req_super`, `app.py:4162-4169`). There is **no** route that updates the column — not for tenants, not for the platform owner.

Why create-only rather than a switch:
- Turning the flag **on** for an existing real org would silently fake that company's emails, rates and TikTok calls. Impossible by construction.
- Turning it **off** would leave no-2FA users and fake data in a company that can now reach the outside. Impossible by construction.
- "Row exists ⇒ flag correct" survives a `platform.db` restore: a backup either has the row with `sandbox=1` or has no row, and an org with no row cannot sign in (`org_is_active`, `app.py:1965-1972`).
- No cache invalidation problem (§1.3).

The create action refuses unless all hold: caller is the platform owner and **not** impersonating (`req_super` tests `session["role"]=="superadmin"`; impersonation sets the role to `admin`, `app.py:13477`); the org id is new, is not `DEFAULT_ORG`, not `PLATFORM_ORG`, not in `_SHIP_LABEL_ORGS` (`app.py:2289`). It sets `internal=1` in the same insert so the demo is never billing-locked (`org_access`, `app.py:1943-1944` — "active plan", R1). It must **not** go through `_create_tenant` (`app.py:13367-13418`): that helper creates an **admin** user (`13414-13416`), opens a trial, and calls `_seed_default_workflow_if_missing`, whose text is a real company's employee handbook (`onboarding_seed.py:21`) — forbidden by checklist item 9.

Tenant-side writers of `organizations` found: branding (`app.py:10865-10885`, admin), `_delete_org_data` (`4809`). Platform-side: subscription (`13105-13145`), toggle (`13439-13452`), `_create_tenant` (`13402-13408`), `pdb_init` (`451-460`). None of them names the column today; a test keeps it that way (§8, PR-A).

### 1.3 How a request learns it — once, with no new query in the common case

One function is the only reader:

```
org_is_sandbox(org) -> bool            raises SandboxUnknown if platform.db cannot answer
```

1. `org in (None, "", PLATFORM_ORG, DEFAULT_ORG)` or `org in _SHIP_LABEL_ORGS` → **False, without touching the database.** The live warehouse can never be affected by a lookup failure or by a wrong row.
2. In a request: return `g._sandbox` if set.
3. Otherwise one primary-key read: `SELECT sandbox FROM organizations WHERE org_id=?`. No row → False (an unknown org already cannot sign in). Exception → `SandboxUnknown`.

It must **not** be built on `org_get()`: that function answers with the founding org's row when the org is missing or suspended (`app.py:1869-1875`).

Cheap path: every authenticated request already reads this row in the billing gate (`_billing_gate` → `org_access` → `_org_billing`, `app.py:3897-3912`, `1922-1930`). Add `COALESCE(sandbox,0) AS sandbox` to that `SELECT` and have the gate store `g._sandbox`. Paths the gate skips (`_BILLING_OPEN_PATHS`, `app.py:3893-3895`, which include `/api/account/delete`) fall to step 3 — one indexed read.

No cross-request cache, in-process or otherwise (server invariant: no in-process state that must be shared). The flag never changes after creation, but a positive/negative cache would still make a new sandbox org invisible to three of four workers for its TTL. A PK read on a WAL database is the cheaper risk.

### 1.4 How code without a request or session learns the org

Today the org reaches such code as an explicit argument or not at all. The transports themselves (`_send_email`, `_ss`, `_ups`, `_usps_track_batch`, `_tt_request`, `_barcode_lookup_online`, the Anthropic client) take **no** org (`app.py:1123`, `2330`, `2467`, `2142`, `16383`, `8528`, `966`). So the fence needs one resolver:

```
egress_org(explicit=None) = explicit  or  _EGRESS_ORG.get()  or  current_org()
```

- `_EGRESS_ORG` is a `contextvars.ContextVar`, set only by `with org_scope(org):` — a context manager that always resets on exit. It is **not** set in `before_request` (a value left in a sync worker's thread would leak into the next request); inside a request the session/`g.org` answer from `current_org()` (`app.py:117-128`) is enough.
- `_spawn(target, *args, org=None)` is the only way to start a thread from request code: it captures `egress_org()` at the call and runs the target inside `org_scope`. A structural test forbids bare `threading.Thread(` outside `_spawn` and the boot loops listed below.

Every sessionless path found, and where its scope goes:

| # | Path | Where | Org today | Change |
|---|---|---|---|---|
| 1 | TikTok sweep (every 5–30 s) | `_tt_sweep_loop` `app.py:17214-17236`, `_tt_sweep_once` `17164-17212` | `org_id` from each `tiktok_shops` row (`17170-17173`) | `org_scope(org)` around each shop's body; sandbox orgs can never have a row (§3) |
| 2 | TikTok ingest worker | `_tt_ingest_worker` `17134-17144`, queue item `(org, shop_id, order_id)` | in the queue item | `org_scope(org)` around `_tt_ingest_order` |
| 3 | TikTok webhook (no session) | `api_tiktok_webhook` `17420-17470` | resolved from `shop_id` (`_tt_org_for_shop_exact` `16481`, `_tt_org_for_shop` `16492`) | scope once the org is known; the self-heal loop (`16507-16525`) scopes per org |
| 4 | TikTok OAuth callback (no session required) | `api_tiktok_callback` `17299-17337` | from the signed state (`17307`) | refuse a sandbox org **before** `_tt_token_exchange` (`17316`); else `org_scope(org)` |
| 5 | USPS tracking loop (6 h) | `_tracking_loop` `2221-2243` → `refresh_tracking_batch(org)` `2187` | loop over `list_org_ids()` (`2239`) | skip sandbox orgs; `org_scope(org)` in `refresh_tracking_batch` |
| 6 | Retention cleanup (hourly) | `cleanup_loop` `691-702` → `cleanup_all_orgs` `679-689` | loop over `list_org_ids()` | no outbound; sandbox media is handled by reset (§6), not by 30-day retention |
| 7 | Backups | `_backup_loop` `3410-3422`, `_backup_v2_loop` `3546-3562` | platform-wide | writes to our own backup bucket; the failure alert mail (`3529`) is a platform send: `org_scope(PLATFORM_ORG)` |
| 8 | Scanit AI lookup thread | `_scanit_start_lookup` `15989-16003` → `_scanit_lookup_info(org, sku)` `16014` | argument | via `_spawn(..., org=org)`; never started for a sandbox org (§3) |
| 9 | TikTok label batch thread | `_tt_start_batch_thread` `18816-18817` → `_tt_run_batch(org, bid)` | argument | via `_spawn(..., org=org)` |
| 10 | Tenant welcome mail thread | `_bg_welcome` `13092-13097` | closure (`_org`, `13090`) | via `_spawn(..., org=PLATFORM_ORG)` — the platform owner's own send; sandbox creation never takes this path |
| 11 | Public new-hire pages (no session) | `_hire_by_token` `3612-3636` pins `g.org` (`3632`) | `g.org` | `current_org()` already answers; the token scan skips sandbox orgs (they have no hires) |
| 12 | Sign-in, before a session exists | `api_login` `4876-4905`, `_finalize_login` `4907-4916`, `api_badge_login` `12743-12775` | `user["org"]` on the staff record | pass the record's org explicitly (blueprint N17) |
| 13 | Nightly sandbox reset (new) | §6 | from `organizations WHERE sandbox=1` | `org_scope(org)` |

`list_org_ids()` returns `[DEFAULT_ORG]` when `platform.db` fails (`app.py:155-156`); that stays correct because the founding org is never sandbox (§1.3 step 1).

## 2. 2FA exemption bound to the flag (SEC-3)

**Rule.** `_twofa_required(user)` (`app.py:764-770`) becomes:

```
required = (effective roles of user ∩ REQUIRED_ROLES) and not sandbox(user["org"])
sandbox(org): org_is_sandbox(org); SandboxUnknown → False   (fail closed: not exempt)
```

`REQUIRED_ROLES` and "effective roles" are SEC-1 / Q8 (→ email-2FA spec); this note only adds the last term. Nothing on the user record takes part.

Inside a sandbox org, additionally:
- Sign-in never enters the code step: `api_login` skips the `twofa_enabled` branch (`app.py:4894-4897`) and `_finalize_login` never sets `must_setup_2fa` (`4914-4915`). The seed never sets `twofa_enabled`, and §4 makes enrolment impossible, so this is belt and braces.
- No code is ever generated or mailed, at sign-in, set-up or deletion (rule 5.11). The "send code" endpoints (→ email-2FA spec) answer a plain refusal for a sandbox account — **not** a fake "sent", which would strand the user on a code screen.
- A sandbox account signs in only if its effective roles ⊆ `{worker, manager}` and it has no badge. Anything else is refused at sign-in and written to `platform_audit`: a tampered record must not become a no-2FA admin.
- Badge sign-in is refused for sandbox orgs (`api_badge_login`, check next to `app.py:12771`).

**Existing `twofa_exempt` fields.** The key stops being read anywhere: the line `app.py:769` is deleted. A one-time boot step, under the `users.json` lock (`update_json`, `app.py:823-833`), removes the key from every record and writes one `platform_audit` line with the count (no usernames in stdout). Effect on a real-org user who carried it: at next sign-in they are treated like anyone with their roles — an admin gets `must_setup_2fa` and is held at the gate (`app.py:3921-3929`). That is the intended outcome of SEC-3. Whether any production record carries the key is **not known** (production data was not read); `ios/APP_STORE.md:63` tells Ofir to set it by hand, so release-manager must correct that line in the same milestone. `tests/test_cycle25_ios_mobile_api.py:161-164` asserts the old behaviour and is rewritten in the same PR.

## 3. The outbound fence (SEC-4)

### 3.1 Shape

One helper, called as the first statement of each transport's single choke point:

```
fenced(transport, org=None) -> bool
    o = egress_org(org)
    if o is None:          log "[egress-no-org] <transport>"; return False     # see §7.2
    return org_is_sandbox(o)                                                    # SandboxUnknown propagates
```

- `True` → the choke point returns that transport's fake (table below), writes one `sandbox.egress.<transport>` line to the org's `audit_log`, and performs no DNS lookup and no connect.
- `SandboxUnknown` → the choke point returns/raises that transport's **ordinary failure** ("not sent, try again"). Never a fake success, never a pass-through. It cannot happen for the founding org (§1.3 step 1).
- The fence is independent of `STAGING_SAFE` / `IS_STAGING` (`app.py:60-74`), which stay as they are. Either one blocks.
- Second, independent layer: a sandbox org holds no credential-bearing state — no `tiktok_shops` row, no WARP key in `settings`, not in `_SHIP_LABEL_ORGS` — enforced at creation, at reset and in the writers named below.

### 3.2 Every transport found, its choke point, its call sites, its fake

The complete set of raw network calls in `app.py` is twelve `urlopen` sites, two `smtplib` sites, one Anthropic SDK client and one boto3 client (grep of the whole file; list in the "Raw call" column). `onboarding_seed.py`, `guide_content.py`, `ps_backup.py` and `mobile/__init__.py` contain none; `restore_backup.py` and `r2_oneoff_validate.py` are operator scripts with their own boto3 client (`restore_backup.py:35`, `r2_oneoff_validate.py:26`) and are not imported by the app.

| Transport | Raw call | Choke point (fence goes here) | Call sites | What a fenced call returns |
|---|---|---|---|---|
| **Email** — Resend, Google Apps Script, SMTP | `app.py:1069`, `1032`, `1109`, `1112` | `_send_email` `1123-1147`, next to the existing staging check (`1126-1128`) | backup alert `3529`; tenant welcome `11443`; new-hire invite `11505` (routes `11543-11592`, `11703`); test mail `11528`; **emailed 2FA codes when built** (→ email-2FA spec) | `(True, None)` — the same answer staging gives (`1128`). Nothing sent. Exception: code mail is refused one level up (§2), never faked. |
| **ShipStation** (rates, carriers, labels) | `2337` | `_ss` `2330-2343` | `2356` carriers, `2410` rates, `2427` buy, `15398` carrier list | By path: `GET /v2/carriers` → `{"carriers": []}`; `POST /v2/rates` → two fixed demo rates in the shape `_ship_rates` parses (`2396-2420`); label buy never arrives here — see next row. |
| **Label purchase (money)** | — | `_can_buy_labels()` `2290-2294` — **unchanged**; a sandbox org is never in `_SHIP_LABEL_ORGS` | gates at `15181`, `15629`, `15692` | The existing 403 with `_NO_LABEL_MSG` (`2295-2297`). Buying is refused, not simulated: no fake money path exists to get wrong. |
| **UPS direct** | `2456` (token), `2475` | `_ups` `2467-2487` and `_ups_token` `2446-2465` | `2546` rates, `2583` ship, `15386` carrier check | `_ups`: two fixed demo rates for `/api/rating/…/Shop`; `CarrierRejected("UPS: not available in the demo company")` for anything else (4xx meaning "nothing was created", `2324-2325`). `_ups_token`: raises the same — no token is ever fetched for a sandbox org. |
| **USPS tracking** | `2087` (token), `2133`, `2157` | `_usps_track_batch` `2142-2175` (the only caller of `_usps_token` / `_usps_track_v3`: `2130`, `2149`, `2153`) plus an early return in `refresh_tracking_batch` `2187` | loop `2240`; route `/api/tracking/refresh` (route line **not read**; listed in the security report) | `{}` — "no update". `refresh_tracking_batch` returns `{"checked":0,"updated":0,"note":"sandbox"}`. Seeded orders carry a fixed `delivery_status`. |
| **TikTok Shop API** | `16414` | `_tt_request` `16383-16428`, next to the staging answer (`16391`) | token exchange/refresh/shops `16431-16442`; order reads `14985`, `15051`, `16612`, `17185`, `17819`; live analytics `17631`, `18031`; combinable `18099`; **combine / ship / label writes** via `_tt_shop_call` `18197-18208` (`18217-18280`) | `{"code":"SANDBOX","message":"TikTok is not connected in the demo company"}` — same shape as the staging answer, which every caller already treats as an API error. |
| **TikTok connect / callback / token store** | redirect, no server call | `api_tiktok_connect` `17280-17297`; `api_tiktok_callback` `17299-17337`; `_tt_store_shop` `16462-16479`; `_tt_valid_token` `16532-16555` | — | connect → a `_tt_page` "Not available in the demo company", no redirect to TikTok; callback whose state names a sandbox org → the same page, **before** the token exchange; `_tt_store_shop` raises for a sandbox org; `_tt_valid_token` → `None` ("no shop"). |
| **TikTok webhooks (inbound)** | — | `api_tiktok_webhook` `17420` | — | Not outbound. A sandbox org owns no shop, so no event maps to it; the handler's outbound follow-ups (`_tt_enqueue_ingest`, self-heal) are scoped per §1.4. |
| **WARP freight** (book charges a card) | `7712` | `_warp_api` `7704-7718` | `7761` verify, `7776` quote, `7813` **book**, `7833` track | `(False, 0, {"error": "WARP is not available in the demo company"})` — the shape of "no key configured" (`7707`). `POST /api/warp/settings` (`7739-7745`) refuses to store a key for a sandbox org. Note: `_warp_api` has **no** staging guard today (finding for AUDIT, §10). |
| **Anthropic** | SDK client `966` | A thin proxy assigned to `anthropic_client` at `966`: `.messages.create(**kw)` calls `fenced("anthropic")` then delegates | `8973` PO line items, `9475` invoice extract, `15827` address parse, `16008` Scanit lookup (background thread), `16298` Scanit scripts | Raises `RuntimeError("AI is not available in the demo company")`. Each call sits in a `try` (`8972`, `9474`, `15826`, `16297`; `16014-16024` for the thread) — the handlers' bodies were **not read**; the programmer confirms each turns it into its normal "AI failed" answer. `_scanit_start_lookup` returns `False` for a sandbox org, so no thread starts. |
| **Barcode databases** (barcodelookup.com, upcitemdb.com, further fallbacks **not read** past `8560`) | `8536` | `_barcode_lookup_online` `8528` | `8605` auto-create on scan (reached from `/api/scanit/scan` `16103`), `8633` `/api/barcode/lookup` | `None` — the documented "nothing found" (`8529-8530`). In a sandbox org `_resolve_or_create_product_by_barcode` (`8595-8606`) also creates **no stub** and returns `(None, False, "")`, so `/api/scanit/scan` answers `found: false` (`16104`) and the demo catalog cannot grow (flow 4.9). |
| **Label/document fetch from a stored URL** | `15271` | `_fetch_label_bytes` `15268-15272` | `15290`, `18518`, `19028` | Raises; all three callers already skip a failed fetch (`15291-15292` read; `18518`, `19028` handlers **not read**). Also the server-side-request risk the security report could not exercise. |
| **Support tickets / plan requests** (reach the owner through `platform.db`, not the network) | — | `api_ticket_create` `13534-13568`; `api_billing_request_plan` `13319-13334` | — | `{"ok": true, "id": 0}` / `{"ok": true, "plan": …}` with **no insert**. |
| **Public new-hire links** (collect ID documents) | — | `api_hires_create` `11543-11592`; `_hire_by_token` `3612` | — | Create refused (§4); the token scan skips sandbox orgs. |
| **Object storage (R2)** | boto3 `230-239` | not fenced — it is our own storage, keys are namespaced by org (`_r2_media_key` `254-256`) | `/api/upload` `5120` and others | Real writes, capped and expiring (§6.5). |
| **LAN-address probe at start-up** | `19579` (UDP socket, sends nothing) | — | — | Not org-related; listed for completeness. |

Not present in the code (grep): PrintNode, any SMS provider, Stripe API calls (only the columns exist, `app.py:361-363`), outbound webhooks, push notifications.

Client-side, outside the server fence: a product picture supplied by a barcode database is a third-party URL the phone itself loads (blueprint N15d). The seed's pictures are on our own host (§6.1), and nothing can add others in a sandbox org.

### 3.3 How a transport added later is caught — tests, not a checklist

Three tests in a new `tests/test_sandbox_fence.py`, all gating PR-C1 and every PR after it:

1. **Socket tripwire (behavioural).** A fixture replaces `socket.getaddrinfo`, `socket.create_connection` and `socket.socket.connect` with recorders that raise. Every HTTP, SMTP or SDK client in Python ends in one of these, whichever library a future change brings. With all `*_ENABLED` flags forced on and dummy credentials:
   - for **every rule in `app.url_map`** × every method, as forged sandbox sessions of each role (worker, manager, and — to test the fence without the §4 gate — admin, cs, host with the gate disabled), with a minimal valid body: the recorder stays empty;
   - for every registered choke point called directly under `org_scope(<sandbox org>)`: the recorder stays empty and the return equals the documented fake;
   - **positive control:** the same direct calls under `org_scope(<real org>)` must hit the recorder. A tripwire that cannot fire proves nothing.
2. **Registry (structural).** The programmer keeps one dict `_EGRESS_CHOKEPOINTS = {function name: transport}`. The test parses `app.py` and every first-party module it imports with `ast` and fails when (a) a network-capable call (`urlopen`, `smtplib.SMTP`/`SMTP_SSL`, `http.client`, `requests.`, `httpx.`, `socket.create_connection`, `.messages.create`, `boto3.client`) appears in a function that is not registered, or (b) a registered function does not call `fenced(` before its network call, or (c) `threading.Thread(` appears outside `_spawn` and the boot loops of §1.4.
3. **Dependency guard.** Fails when `requirements.txt` or a top-level `import` gains a package that is not on a short allow-list in the test. Adding `stripe`, `twilio`, `requests` or a PrintNode client forces the author into this file and so into test 1.

Rejected: patching `socket` in production as a last line. It would sit under the live warehouse's TikTok sync and label buying, and R2 must stay reachable for the sandbox; the risk to the floor is larger than the gain.

## 4. What is immutable inside the sandbox, and how each is refused

Background that makes this necessary: a **manager** passes every `req_role("admin")` route that is not on a prefix block-list (`app.py:4136-4149`, list `4124-4130`). `/api/2fa/*` (`4957-5015`), `/api/tiktok/*` (`17280`), `/api/warp/settings` (`7739`), `/api/hires` (`11543`) are not on it. So the demo manager can today enrol 2FA (locking out the next reviewer), start a TikTok connection, paste a WARP key and create a public hire link.

Three layers; the first two are single choke points, the third is per function.

**Layer 1 — the sandbox gate (allow-list).** One `before_request`, after the billing gate. If `g._sandbox` is true, the request must match `SANDBOX_ALLOW` — the routes the app itself calls: `/m/*`, `/api/mobile/session`, sign-in/out, `/api/account/delete`, the Pick, Pack, Track, Today and Scanit-scan endpoints, `/media/video/*`, `/static/*`, the legal pages. Everything else: `403 {"ok":false,"error":"demo_company","message":"Not available in the demo company."}` for `/api/*`, a redirect to `/m/` for pages. The exact list is built by the programmer from `mobile/static/*.js` and the Swift client and reviewed by security-reviewer; a test asserts that every rule in `app.url_map` is either on the list or answers 403/redirect for a sandbox session — so a **new route is closed to the sandbox by default**. This shuts the several hundred desktop routes the security report could not exercise. It is Ofir's call (§10, Q1).

**Layer 2 — the staff-file guard.** `update_json(USERS_FILE)` (`app.py:823-833`) and `svj` (`818-820`) are the only writers of `users.json`. On exit, before `_atomic_write`, compare before/after for records whose org is a sandbox org (ids read from `platform.db` **before** taking the file lock): any added, removed or changed record raises and nothing is written — except the keys `last_login` (`_touch_last_login`, `4111-4120`) and inside `with sandbox_seed_scope():`, which only the reset (§6) and the console's "set reviewer password" action enter. One choke point covers every present and future user-management route.

**Layer 3 — explicit refusals** (clear messages, and defence if a route is ever allow-listed by mistake):

| Thing | Routes / functions | In a sandbox org |
|---|---|---|
| Passwords | `api_pw` `12708-12717`; `api_hire_issue_temp_password` `11593-11615`; the legacy-hash upgrade in `api_login` `4890-4892` (never fires: the seed stores bcrypt) | Layer 1 → 403; Layer 2 blocks the write. No self-service password change route exists today (grep). |
| 2FA | `/api/2fa/setup`, `enable`, `disable`, `recovery` (`4965-5015`); email-code set-up (→ email-2FA spec) | 403 `demo_company`; the Account row reads "Not available in the demo company" (flow 4.2). |
| Users and roles | `api_add` `12622`, `api_user_roles` `12658`, `api_user_name` `12683`, `api_del` `12698` | 403 (true-admin routes; no sandbox user is an admin); Layer 2. |
| Badges | `api_badge_regen` `12719`, `api_badge_revoke` `12733`, badge PDFs `13858-14061`; `api_badge_login` `12743` | 403; no sandbox record has a badge; badge sign-in refused (§2). |
| Branding | `api_org_branding_set` `10865` | 403. The app is indigo regardless (D8); the company name is the seed's. |
| Integrations | TikTok connect/forget/pause/cutover (`17280`, `17406`, `17497`, `17507`), `_tt_store_shop` `16462`; WARP settings `7739`; email test `11507` | 403 at Layer 1; the writers refuse a sandbox org (§3.2). |
| Billing | `api_billing_request_plan` `13319`; `/api/orgs/<id>/subscription` and `/payment` (`13105`, `13275`, platform owner) | Tenant route: canned OK, no insert. Platform routes refuse a sandbox org: it stays `internal=1`. |
| Hires | `api_hires_create` `11543`, `send-invite` `11703`, public `/api/hire/<token>/…` `11763-12052` | 403; token scan skips sandbox orgs. |
| Impersonation | `api_impersonate` `13461-13481` | Refused for a sandbox target (checklist 5). It would mint an **admin** session inside the sandbox. The platform owner manages the demo from the console only. |
| The flag itself, `internal`, `active` | — | No tenant route; `active` stays the platform owner's off switch (§7.5). |

Also bounded (checklist 10): a sandbox session expires 12 hours after sign-in (`session["sbx_iat"]`, checked in the gate; real orgs keep 7 days, `app.py:3857`); every refused or fenced action is in `audit_log`; `/api/mobile/session` (`app.py:4852-4872`) returns `sandbox: true` for the banner (N3), read through `org_is_sandbox`, not `org_get`.

One conflict for security-reviewer to rule on: checklist 10 asks for a per-account login throttle (SEC-11) in the sandbox. A hard per-account lockout on a shared login lets anyone who learns the username lock Apple out. Proposed: in a sandbox org the per-account limiter is a growing delay capped at 30 s, never a lock; the per-IP limit (`app.py:879-896`) stays as is.

## 5. Deletion (SEC-7, K3, blueprint N21)

### 5.1 Real orgs — re-authentication (the one deliberate behaviour change)

`POST /api/account/delete` (`app.py:4817-4845`) today needs only the session cookie. New contract:

| Account | Must send |
|---|---|
| has a password it knows | `password` |
| floor account with a badge (after SEC-2: effective roles ⊆ floor roles) | `password` **or** `badge` = a fresh scan of **its own** badge token |
| has a second factor enrolled | additionally `code` (authenticator, or an emailed code → email-2FA spec) |
| last admin of the org | additionally `wipe_org: true` (existing 409 `need_org_confirm`, `4834-4836`) |

States: `signed-in → credential-checked → [last admin: org-confirmed] → user removed → [org wipe pending → wiped] → session cleared`.

Rules and failure modes:
- A wrong or missing credential, or **someone else's badge**: 403, counted against the account by the login limiter (key `username:delete`, same store as `app.py:879-896`), nothing changes. The credential is checked **before** the `users.json` lock is taken; the removal re-reads the record under the lock.
- Two workers race (double tap): the second finds no record → 404 as today (`4830`).
- The request dies after the user is removed and before the org wipe: today that leaves a company with no admin and all its data. Fix: write an `org_deletions(org_id, requested_by, state='pending', at)` row in `platform.db` **before** removing the last admin; the wipe marks it `done`; the hourly cleanup loop (`app.py:691-702`) finishes any `pending` row. The wipe is idempotent. What the wipe must remove is SEC-6 and not this note.
- `SandboxUnknown` while deciding: 503, nothing deleted.
- The route stays reachable during the 2FA-setup and billing gates (`app.py:3893`, `3918`), as the blueprint requires; it is now safe because it demands the credential.
- The desktop "Me" page must send the password: a `templates.py` change by the programmer in the same PR (shared logic, not mobile work).

### 5.2 Sandbox org — simulated

`POST /api/account/delete` for a sandbox account:
1. Checks the password exactly as in 5.1 (the reviewer types it in flow 4.8 step 6; a wrong one is refused — the flow must look real). No code is asked, ever.
2. Writes `account.delete.simulated` to `audit_log`.
3. Clears the session and answers the real success body: `{"ok": true, "deleted_user": <u>, "org_deleted": false}` (shape of `app.py:4845`).
4. Changes nothing in `users.json`. The next sign-in with the same login works.

`wipe_org` is ignored. Independently, `_delete_org_data` (`app.py:4797-4815`) begins with: sandbox org or `SandboxUnknown` → return without deleting. `api_del` (`12698`) cannot remove a sandbox user (Layer 2). No sandbox login is an admin, so the last-admin path cannot be reached (K3).

**Deviation from the SEC-7 fix text**, for security-reviewer to confirm: the report says "simulated success followed by an automatic re-seed". This design does **not** re-seed on deletion: flow 4.8 has the worker delete the account (step 6) and then the manager play the video of the box that worker just packed (step 8); a re-seed in between would erase it. Nothing needs restoring after a simulated deletion, because nothing was removed.

For app-review (not Ofir): the account works again immediately. If app-review judges that a reviewer who signs back in will read that as "deletion does not work", the alternative is a 15-minute tombstone in `sandbox_state` that refuses that one login with "This account was deleted" and then lapses by itself. It costs a lock-out risk if the reviewer deletes before picking. Default here is no tombstone, as the blueprint says (flow 4.7).

## 6. Seed and reset

### 6.1 The seed

A new module `sandbox_seed.py` at the repo root: pure data and pure functions, no I/O, no network — `SEED_VERSION` and `rows(today) -> {table: [row, …]}`. Dates are relative to `today` so the show is always "today". Ids are fixed so the label PDF never changes. Assets in `sandbox_assets/`.

| Content | Detail |
|---|---|
| Company | "Demo Company" (name final wording: release-manager), `internal=1`, `sandbox=1`. |
| Logins | From `sandbox_logins`: one `worker`, one `manager`. No badge, no email address, no second factor, no extra roles (N12). |
| Shows | Two: today's and yesterday's. |
| Orders (12) | 6 pending (to pick), 2 picked (ready to pack), 1 **packed, with a video**, 1 shipped/delivered, 1 cancelled, 1 with an issue. One to three items each. Tables `shipments`, `shipment_items` (`app.py:1260`, `1286`); the columns pick/pack read were **not read** — the programmer takes `scripts/mobile_audit.py:100-140` as the column model, **not** as content. |
| Tracking numbers | `LOHDEMO` + 8 digits. Passes the upload check (`app.py:5098`), is not rewritten by `_normalize_tracking` (`5042-5048`), and is not a USPS number (`_is_usps_tracking`, `2177-2185`). The audit seed's `9400111…` numbers (`scripts/mobile_audit.py:128`) are USPS-shaped and must not be used. |
| Buyers | Invented names; addresses on "Example St", ZIP `00000`; phones `555-01xx`; `@example.com`. No row copied from any company. |
| Products | Invented names, no real brands (the audit seed uses real brand names, `scripts/mobile_audit.py:117-120` — do not reuse). Three complete catalog products for Scanit: picture **on our host**, typed retail price, notes, lookup state "done" so no lookup is wanted (`_scanit_wants_lookup`, `app.py:15963`, body **not read**). Barcodes are EAN-13 in the 200–299 in-store range, which no manufacturer product carries, with valid check digits; `/api/scanit/scan` accepts 8–14 digits (`16102`). |
| Packed order's video | One H.264 `.mp4`, under 1 MB, no people, voices or real labels (§10, Q2), stored under the same key scheme as an upload (`_r2_media_key("videos", …)`, `app.py:254-256`) plus its `packing_log.csv` row (`LOG_FIELDS`, `app.py:89`). |
| Label PDF | `sandbox_assets/demo-labels.pdf`, generated by a script from the same seed (reportlab and python-barcode are already dependencies): four shipping labels — two pending, one ready to pack, the pre-packed one — and one product barcode, each with its number printed for typing. Attached in App Review Information by Ofir. Which barcode symbologies the iOS camera reads was **not read** (`ios/`); Code 128 for labels is the assumption and must be proven on a device (M3 "done when"). |
| Not seeded | Hires, onboarding workflows (`onboarding_seed.py` holds a real company's handbook), TikTok shops, WARP keys, tickets. |

A test asserts: `rows()` is deterministic; every buyer, address, phone, email and tracking number matches the fake patterns above; no row enables USPS selection; importing the module opens no socket.

### 6.2 The reset — one function

`sandbox_reset(org, by)`; refuses a non-sandbox org. Steps, each idempotent:

1. `with _flock("sandbox_reset_" + org)` (`app.py:788-800`) — cross-process, blocks a second reset.
2. `sandbox_state.state = 'resetting'`, `state_since = now`.
3. `shipments.db`: one `BEGIN IMMEDIATE` transaction — delete all rows of every data table, insert the seed, commit. Other workers' readers see the old rows or the new rows, never a mix (WAL snapshot); their writers wait on `busy_timeout` (60 s, `app.py:1252`) for a few milliseconds. **No file swap**: replacing a SQLite file under four workers is the risky way. Which `settings` keys must survive (the stock-model migration marker, `app.py:8326`, `8346-8361`) was **not read**; the programmer keeps an explicit keep-list.
4. `giveaways.db`: the same.
5. JSON stores and `packing_log.csv`: atomic writes; the log under `_flock("packing_log_" + org)`, the lock uploads use (`app.py:667`).
6. `users.json`: restore the org's two records from `sandbox_logins` inside `sandbox_seed_scope()`; remove any other record of that org.
7. Media: delete every object under `<org>/videos|photos|labels|documents|products|invoices` that is not a seed object; put the seed video and pictures (fixed keys).
8. `platform.db`: delete the org's rows in `tickets`, `ticket_messages`, `billing_requests`, `tiktok_shops`, `tiktok_orders`, `tiktok_events`, `tiktok_live_sessions` (all should be empty by §3–§4); zero the upload counters.
9. `sandbox_state`: `state='ready'`, `seed_version`, `last_reset_at`, `last_reset_by`; one `platform_audit` line (`plog`, `app.py:588`).

Triggers:
- **Platform console**: `POST /api/orgs/<org_id>/sandbox/reset`, `@req_super`. Immediate. The Organizations screen shows state, last reset, last activity, upload usage, and "Set reviewer password" (writes `sandbox_logins`, then the user record through the seed scope; the password is typed by Ofir there and exists nowhere else — checklist 12).
- **Nightly**: a thread started in every worker; each tick (10 min) claims the run with the tracking loop's pattern — check and touch a marker file inside one `_flock`, so exactly one worker runs it and a recycled worker does not orphan the job (`app.py:2221-2237`). Due when the last reset is older than 20 h and it is after 09:00 UTC (early morning in both US coasts). **Deferred while the sandbox was active in the last 30 minutes** (`sandbox_state.last_activity_at`, updated by the gate at most once a minute), for at most 6 hours, then forced.
- **Deploy**: when `SEED_VERSION` in code is newer than the stored one, the same claimed run applies it.
- **Self-heal**: a tick that finds `state='resetting'` older than 5 minutes runs the whole reset again (a worker died mid-reset).

Not started on a staging box (R2 writes are blocked there, `app.py:76-88`); the console action still works for the databases and reports the media step as skipped.

### 6.3 Concurrency

Four workers (`Procfile:1`). The flock serialises resets; the per-database transaction is atomic against requests; counters are single `UPDATE … WHERE` statements. Between step 3 and step 7 an order may briefly point at a video that is being replaced — tolerable in a demo, bounded to seconds, and self-corrected by step 9.

### 6.4 A reviewer mid-session during a reset

- Their session stays valid: the username and roles are unchanged, so `_session_revocation` (`app.py:3939-3963`) does nothing.
- Lists show the fresh seed on the next load. An order they had picked is pending again; a pick or pack call for it succeeds as a first-time action because the ids are the same.
- An upload in flight either commits first (and is then erased) or waits for the lock and lands on the fresh order — a normal pack either way.
- The deferral rule makes the nightly reset avoid an active reviewer; only the console button can interrupt one, and it shows the last activity time before confirming.

### 6.5 Upload caps and expiry (sandbox orgs only)

`/api/upload` (`app.py:5088-5135`) reads the whole body into memory with a 250 MB ceiling (`5104`, `3852`). For a sandbox org, before reading:
- `Content-Length` over **30 MB** → 413. A file that is neither MP4 nor WebM → 400 (`_is_mp4`, `5109`; EBML check `5114-5116`) — SEC-9 applied here first. Photos: 5 MB.
- A ring, not a wall: at most **20** non-seed videos; storing the 21st deletes the oldest. Bounded at 600 MB without ever answering "storage full" to a reviewer because of an earlier visitor. Counted in `sandbox_state`.
- Expiry: every non-seed object is deleted at each reset (≤ 26 h). The 30-day retention (`cleanup_old_files`, `app.py:644-675`) and bucket lifecycle rules are not relied on.

## 7. Concurrency, failure modes, migration, rollback

### 7.1 Migration on the live `platform.db`

Additive only, in `pdb_init` next to the existing column loop (`app.py:366-372`): `ALTER TABLE organizations ADD COLUMN sandbox INTEGER NOT NULL DEFAULT 0` when missing, and `CREATE TABLE IF NOT EXISTS` for `sandbox_logins`, `sandbox_state`, `org_deletions`. SQLite adds a constant-default column without rewriting rows. The four workers boot together and may race the `ALTER`: wrap `pdb_init`'s migration in `_flock("platform_migrate")` and treat "duplicate column name" as success (whether `pdb_init` is already serialised at boot was **not read**). Existing code is unaffected by the extra column: inserts name their columns (`app.py:452-454`, `13402-13408`); `SELECT *` consumers (`13354`, `1872`) return one more key. Tests create orgs with a direct `INSERT` (`tests/test_security_mobile_baseline.py:26-38`) and get `sandbox=0` by default.

### 7.2 Fail-open / fail-closed decisions

| Situation | Decision | Why |
|---|---|---|
| Org is the founding org or a label-owner org | Not sandbox, **no lookup** | The live warehouse must not depend on this feature in any way. |
| Lookup fails, question is **2FA exemption** | Not sandbox → 2FA required | Worst case the reviewer is held at a code step; an exemption never leaks. |
| Lookup fails, question is **outbound** | Refuse with the transport's ordinary error; send nothing; **never a fake** | "Treat as sandbox" would hand a real company a fake success (a label that does not exist, an email that was never sent). "Treat as real" could let a sandbox call out. Refusing is the only answer that is wrong for nobody. For in-request code this adds no new failure: the same row is already read by the billing gate, which fails the request first. |
| Lookup fails, question is **immutability / deletion** | Refuse (503); never delete | Same reasoning. |
| Outbound call with **no org at all** (a missed scope) | Allowed, logged as `[egress-no-org]`; **fails the test suite** (§3.3 tests 1 and 2) | Denying in production would stop the floor's TikTok sync on one forgotten `org_scope`. A sandbox request cannot produce an org-less call: in a request `current_org()` answers, and threads go through `_spawn`. After two weeks with zero such log lines in production, a follow-up PR flips this to "refuse". |
| Reset fails midway | State stays `resetting`; rerun within 10 min; every step idempotent | — |
| `sandbox_logins` empty (Ofir has not set passwords yet) | The org exists with no users; nobody can sign in | Safe default between PR-A and PR-F. |
| `platform.db` restored from a backup | Row present ⇒ `sandbox=1` (create-only); row absent ⇒ its users cannot sign in (`app.py:1971-1972`) | Runbook line for Ofir: after a restore, press Reset on the demo company. |

### 7.3 Request dies halfway

- Sign-in, gate, fence: read-only decisions; nothing to repair.
- Simulated deletion: the audit line may exist without the session being cleared — harmless.
- Real deletion: §5.1 (`org_deletions`).
- Reset: §6.2.

### 7.4 Two workers race

- Creating the sandbox org twice: the primary key rejects the second insert.
- Two resets: the flock. Reset against uploads: the database transaction and the ring counter's single statement.
- `users.json`: all writers already hold one flock (`app.py:826`); the guard runs inside it.

### 7.5 Turning the whole thing off

- **Now, no deploy:** Organizations → Suspend the demo company (`api_orgs_toggle`, `app.py:13439-13452`). Sign-in is refused (`4886`) and live sessions get 402 at the next request (`org_access`, `1941-1942`).
- **By variable:** `SANDBOX_ENABLED=0` → sandbox sign-in refused, reset loop not started, the create action refused. The fence, the gate and the staff-file guard are **never** switched off by a variable; they do nothing when no sandbox org exists.
- **Rollback of code:** each PR reverts on its own (§8). The column and tables stay; they are inert. Reverting PR-B alone must not happen while a sandbox login exists — suspend first. Order of safe removal is the reverse of the build order.

## 8. Build order as PRs

Each is a shared-logic PR ("Shared logic:" in the first line), programmer → qa → security-reviewer, merged by Ofir outside packing hours. Gate for all: `python3 -m py_compile app.py templates.py && python3 check_js.py && python3 -m pytest -q tests`.

Dependencies outside this note: **SEC-1**, the **emailed code** (N13) and **SEC-2** come from the email-2FA spec. PR-A … PR-E do not wait for them. **PR-F does**: no reviewer login may exist before SEC-1 and SEC-2 are merged (checklist 11).

| PR | Contents | Tests that gate it | security-reviewer verifies | Strict-xfail turned green |
|---|---|---|---|---|
| **A — flag and org context** | Column + three tables (§7.1); `org_is_sandbox`; `egress_org`, `org_scope`, `_spawn` and the scopes of §1.4; console "create demo company" (creates the org with **no users**); `sandbox` in `/api/mobile/session`. No behaviour change for any existing org. | Migration on a copy of an old-schema `platform.db`, run by 4 processes at once; founding org short-circuit makes no query; no tenant route can set the column (every tenant POST with `sandbox: 1` in the body, plus a source check that the column is written in one statement only); thread structural test; full suite unchanged. | Create-only holds; `req_super` and not impersonating; `org_get` not used for the flag. | none |
| **B — 2FA exemption bound to the flag** | §2; delete `app.py:769`; strip `twofa_exempt` at boot; sandbox sign-in rules (roles ⊆ worker/manager, no badge, no code step). | Exempt admin in a real org is held; sandbox manager signs in with a password only; lookup failure ⇒ required; rewritten `test_cycle25` case. | SEC-3 closed; the key is read nowhere (grep); no code is mailed for a sandbox account. | `test_sec3_twofa_exempt_only_inside_a_sandbox_org` |
| **C1 — fence: email, carriers, USPS, WARP, AI, barcode, label fetch, tickets** | §3.1–3.2 for those rows; `_EGRESS_CHOKEPOINTS`; the three tests of §3.3. | §3.3 tests 1–3 incl. the positive control; **byte-identity test**: for a real org the request each transport builds (URL, headers, body) equals a recorded snapshot from before the PR. | One recorder per transport stays empty (checklist 4); fakes are not mistaken for real results anywhere money is involved; label buying is still refused, not faked. | `test_sec4_sandbox_org_sends_nothing_outside` (it exercises email and carrier rates) |
| **C2 — fence: TikTok** | `_tt_request`, connect, callback, `_tt_store_shop`, `_tt_valid_token`, scopes in sweep / ingest / webhook. Separate because it is the floor's most active path. | Tripwire over all `/api/tiktok/*`; callback with a sandbox state never calls the token exchange; existing `test_tiktok_*`, `test_cycle6_tiktok.py`, `test_cycle12_*` unchanged; byte-identity for a real org's sweep request. | A sandbox org cannot own a shop row by any path; webhook for an unknown shop still ignored. | none (keeps the SEC-4 test green with the gate off) |
| **D — deletion** | §5: credential for real orgs (password, or own badge for a badge floor account), `org_deletions`, simulated deletion, `_delete_org_data` guard; desktop "Me" page sends the password. The 2FA-code requirement attaches when N13 is merged. | No credential → refused, account remains; wrong badge counted; last admin still needs `wipe_org`; kill between user removal and wipe → cleanup finishes it; sandbox: success body, session gone, account remains, `wipe_org` ignored; `test_cycle13_account_delete.py` updated. | SEC-7 closed; N21 confirmed (it changes the SEC-7 fix); the §5.2 deviation (no re-seed on delete) accepted or not. | `test_sec7_account_delete_requires_password` |
| **E — sandbox gate and immutability** | §4 layers 1–3; 12-hour session; impersonation refusal; audit lines; login-delay rule. | Every rule in `app.url_map` is allow-listed or closed for a sandbox session; `users.json` guard refuses every change to a sandbox record outside the seed scope and lets every real-org write through unchanged; manager cannot reach `/api/2fa/*`, TikTok connect, WARP settings, hires. | Checklist 3, 5, 6, 10; the allow-list line by line. | none |
| **F — seed, reset, caps, console, label PDF** | §6; `sandbox_seed.py`, `sandbox_assets/`; console UI on the Organizations screen (`templates.py`, platform-owner page only); "set reviewer password". | Seed purity test; reset under 4 processes with concurrent pick/pack/upload; kill mid-reset then self-heal; ring at 21 uploads; 413 over 30 MB; browser check modelled on `scripts/m_pick_check.py` walking flow 4.8 against the seed. | Checklist 7, 8, 9, 12 (no password in the repo, logs or responses); fake data only. | none |
| **G — isolation with the sandbox as "org B"** | Tests only: the `test_holds_cross_org_*` cases re-run with a sandbox org against the founding org, both directions. | Themselves. | Checklist 5; then **CLEAR** line by line. app-review then confirms R1 and K3. | none |

After G: release-manager corrects `ios/APP_STORE.md:63-72` (role, wording, the two logins, the PDF); Ofir sets the two passwords in the console and runs flow 4.8 on the phone (`PROVEN.md`).

## 9. Risks to the live warehouse, per PR

The standing guarantee: every new check begins with `org_is_sandbox`, which answers False for the founding org and the label-owner orgs **before any I/O** (§1.3). With the flag off, each fenced function executes the same statements as today after one in-memory comparison; no argument, return value or request changes. The byte-identity tests in C1 and C2 hold that line.

| PR | Risk | How the design contains it |
|---|---|---|
| A | The `ALTER` at boot with four workers; a wrong scope in the TikTok sweep changing its behaviour | Additive column, flock, duplicate-column tolerated; `org_scope` only sets a context variable — the sweep's statements are unchanged; existing TikTok suites must pass untouched. |
| B | An admin who carried `twofa_exempt` meets the set-up gate | Intended. Ofir is told in the PR description; whether any such record exists in production is unknown. Nobody else's sign-in changes. |
| C1 | A fence check raising inside label buying or email | For the founding org the check cannot raise (no lookup). Label buying is not touched at all (`_can_buy_labels` unchanged). |
| C2 | The 5-second sweep and the webhook path | Same guarantee; byte-identity test on the sweep request; merge well outside a live show, since a restart interrupts the sweep leader (`app.py:17216-17222`). |
| D | **Real behaviour changes**: account deletion now needs a credential; the desktop "Me" page changes | The only PR that is not byte-for-byte, by Ofir's own decision (SEC-7). Limited to one route and one dialog. |
| E | The `users.json` guard runs on every staff-file write, including each sign-in's `last_login` | It compares only records of sandbox orgs (two); with no sandbox org it compares nothing. A `platform.db` read failure refuses the write — but then every signed-in request is already failing at the billing gate (`app.py:3906`). |
| F | A new background thread; R2 deletes | The loop touches only orgs with `sandbox=1`; `sandbox_reset` refuses any other org as its first statement; deletes are limited to keys that start with that org's prefix. |
| G | none (tests) | — |

Every merge restarts the server; merge outside packing hours (CLAUDE.md).

## 10. Open questions for Ofir

**Q1. May the demo logins open the desktop site at all?**
- *Option A — app only (recommended).* In the demo company only the app's own screens answer; every desktop page and every other `/api` route is closed (§4 Layer 1). Cost: the demo company cannot be used to show the desktop to a prospect; a sales demo needs a second, ordinary trial company. Gain: several hundred routes nobody has security-tested are simply not reachable without 2FA, and any route added later is closed by default.
- *Option B — desktop open, with a block-list.* The demo manager can browse the desktop. Cost: each dangerous route must be found and blocked by hand, every new route is open until someone remembers, and security-reviewer must test the whole desktop before CLEAR — weeks, not days.

**Q2. The packing video that ships inside the demo company.**
- *Option A — you record it (recommended).* Twenty seconds on an iPhone: a plain box, a few generic items, no faces, no voices, no real label or address in frame. Ten minutes of your time; the reviewer sees what the product really does.
- *Option B — a generated placeholder clip.* No time from you. Looks artificial to a reviewer judging whether the app is a real tool.

**Q3. The founding company can delete itself from inside.** Found while reading, not part of the sandbox: the last admin of your own company can wipe it with `wipe_org` (`app.py:4831-4840`); nothing protects the founding org in `_delete_org_data` (`4797-4815`). After PR-D it needs the password, but it remains possible.
- *Option A — forbid it (recommended).* Companies marked internal (yours and the demo) can be deleted only from the platform console. A few lines; your own account deletion still works.
- *Option B — leave it.* Nothing to build; one mistaken confirmation by the last admin, with the password, erases the live warehouse's data.

Not for Ofir, recorded for their owners: the tombstone question (§5.2, app-review); the login-delay rule and the no-re-seed deviation (§4, §5.2, security-reviewer); `_warp_api` has no staging guard (`app.py:7704-7718`) and `_create_tenant` seeds every new company with another company's handbook text (`onboarding_seed.py:21`, called at `app.py:13411`) — both to be filed in the audit by the lead session, since `AUDIT_2026-10.md` and `docs/ARCHITECTURE.md` do not exist in this worktree.

## 11. Not read / not verified

- `docs/specs/2026-11-10-email-2fa.md` (being written in parallel).
- `app.py` outside the cited ranges — in particular: the bodies of the pick, pack, today and shipment-lookup endpoints (`4574`, `6664`, `7468`) and whether any of them calls TikTok on the way (callers of `_tt_live_order_statuses` found only in the label batch, `18547`, `18727`); `/api/tracking/refresh`; the label routes between `15150` and `15700` beyond the gates; `_tt_retention_purge` (`17390`); the barcode fallbacks after `app.py:8560`; the exception handlers around the Anthropic calls and two of the three `_fetch_label_bytes` callers; the product-image and `/media/*` routes; `_migrate_stock_model_packtime`; whether `svj` is ever called on `users.json`; how `pdb_init` is serialised at boot; the other `list_org_ids()` loops at `2057`, `3345`, `3387`, `3467` (boot and backup code, not checked for outbound calls).
- `templates.py` (not opened), `mobile/static/*.js`, everything in `ios/` (so: which requests the app really makes, which barcode types the camera reads), `live-vision/` (a separate service; not checked for calls into this app), `ps_backup.py` beyond its header, `tests/` other than the cited lines.
- `AUDIT_2026-10.md`, `docs/ARCHITECTURE.md`: missing from this worktree; not created here because this task allowed one file only.
- Production: Railway variables, real `users.json` and `platform.db` contents, bucket lifecycle rules, the server's time zone. Nothing was sent to production; nothing was run except read-only `git`, `grep` and `sed`.
