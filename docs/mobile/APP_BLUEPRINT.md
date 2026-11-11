# App blueprint — Live Ops Hub (iPhone / iPad)

**Status: approved by Ofir 2026-11-10**, together with the roadmap, "with these answers" (D1–D8 and Q1–Q5, recorded below). Written by app-planner from `main` as checked out on branch `docs/roadmap-to-app-store`.

Two parts of this version were written *after* the approval, from Ofir's answers, and he has not read them yet: the Scanit plan (his Q4 answer) and the text-message two-step verification plan (his D3 condition). They are marked **new** where they appear. Three questions they raise are in §7 (Q6–Q8). Everything else is the approved draft with the undecided branches removed. The change log at the bottom lists every difference from the draft.

This is the app planned as one product: who uses it, what each role sees, every screen and where it lives, the journeys across screens, and what ships in 1.0. Screen design belongs to ios-designer (`docs/mobile/screens/`); this document only says which screens exist and how they connect.

Inputs: `ROADMAP.md`, `BOARD.md`, `REVIEW-2026-11-10.md` (R1–R3, K1–K12, P1–P8), `docs/security/2026-11-10-mobile-baseline.md` (SEC-1…20), `DESIGN_SYSTEM.md`, the specs in `screens/`, and the code (`mobile/`, `ios/LiveOpsHub/`, role checks and the Scanit and sign-in routes in `app.py`, `tests/test_scanit_catalog.py`). All code statements are from reading; nothing was run.

How to read "state today": **exists** = in the repo and reachable in build 5 · **specified** = a spec exists, nothing built · **missing** = neither. None of it is proven on a device except "installs and opens" (`device-tests/PROVEN.md`).

### Ofir's decisions (2026-11-10) — the blueprint is built on these

| # | Decision | Where it lands |
|---|---|---|
| D1 | Yes: an isolated demo (sandbox) company without two-step verification for Apple's reviewer | flow 4.8, N12 |
| D2 | Reviewer logins are **manager + worker**. No admin demo account | §2, flow 4.8 |
| D3 | Badge sign-in only for floor roles is accepted **on one condition: two-step verification by a text-message code to a phone number exists first**, offered in addition to the authenticator app; the user chooses | S1, S12, flows 4.1 and 4.2, N13–N14 |
| D4 | iPad in 1.0 is decided after the first device round (M1) | §2 iPad table — the only place where two branches remain |
| D5 | **Unlisted** distribution, **United States storefront only** | §6 |
| D6 | liveopshub.com is Ofir's; privacy, terms, support and marketing pages move there | rule 5.6, N18 |
| D7 | Public support contact is **support@liveopshub.com**. Policy wording still needs Ofir's sign-off when drafted | S8, flow 4.7 |
| D8 | **Always LiveOpsHub indigo** inside the app; no per-company colour in the app | rule 5.9, N16 |
| Q1 | Manage tab for **admin only** | §2 |
| Q2 | Track lives **inside Today** | §2 |
| Q3 | News and My Schedule are **not** in 1.0; they are first in 1.1 | §3.2 |
| Q4 | **Scanit is built now** — the host's tool is in 1.0 | S13, flow 4.9, N15 |
| Q5 | **Yes** — the packing video is viewable from Track for cs / manager / admin | S7, flow 4.6, N10 |

### Apple guidance used (read online 2026-11-10)

| Page | Change log (latest) | What this blueprint takes from it |
|---|---|---|
| HIG › Tab bars (`developer.apple.com/design/human-interface-guidelines/tab-bars`) | June 8, 2026 | Tab bars are for navigation between top-level sections, not actions. "Avoid overflow tabs" — a More tab "makes it harder for people to reach and notice content". "Don't disable or hide tab bar buttons, even when their content is unavailable." Badges are reserved "for critical information". On iPadOS the system shows the tab bar near the top; converting it to a sidebar is an option for more complex apps ("Prefer a tab bar for navigation"). |
| HIG › Sidebars (`…/sidebars`) | June 8, 2026 | "Consider using a tab bar first"; the sidebar-adaptable style is for exposing "more areas than fit in a tab bar". |
| HIG › Launching (`…/launching`) | June 10, 2024 | "Launch instantly"; "Restore the previous state when your app restarts"; launch in the device's current orientation when both are supported. |
| HIG › Layout (`…/layout`) | September 9, 2026 | "Determine layout based on size classes, not device type or orientation"; "Keep functionality the same as size classes change"; iPad windows are resizable. |

These four pages were read for the draft earlier the same day and were not fetched again for this version; no new statement about tab bars, navigation or iPad layout was added. Not fetched, so nothing is asserted from them: HIG Onboarding, Managing accounts, Notifications, Web views, Split views. The App Review guideline wording used below is quoted from app-review's report, not re-read.

Also read today, for Q6 only: Twilio's "A2P 10DLC" documentation page (`twilio.com/docs/messaging/compliance/a2p-10dlc`). It says a sender must register before an application sends text messages to US numbers from an ordinary ten-digit number; the page gives no duration for that registration.

---

## 1. People and jobs

The server has **five** roles: `worker`, `host`, `cs`, `manager`, `admin` (`app.py` `VALID_ROLES`). "Picker" is not a role any more — it was merged into `worker`. A picker and a packer are the same account type doing two jobs. `superadmin` (platform owner) is a sixth, internal account type.

| Who | Opens the app to | How often | Conditions | Signs in with | Done looks like |
|---|---|---|---|---|---|
| **Worker picking** (`worker`) | choose a show, scan a label, tick items off the table, finish or report a problem | all shift, hundreds of orders after each live | one hand, often gloves, phone or a shared iPad, Bluetooth scanner or camera, patchy Wi-Fi | badge scan, or username + password | "Order picked" and the next label scanned without looking for a button |
| **Worker packing** (`worker`) | scan a label, see the box contents, record the packing video, upload, next box | all shift | phone or iPad on a stand, Bluetooth/USB scanner, hands full | same | video saved to the order, order marked packed, next scan opens the next box |
| **Warehouse manager** (`manager`) | see where each show stands (to pick / to pack / issues), jump in to pick or pack, look up a label and its packing video | many times a day, walking the floor | phone in hand, interrupted | password + two-step code (authenticator or text message) | knows which show is behind and why, in under a minute, without a laptop |
| **Customer service** (`cs`) | answer "where is my order / an item was missing": find the label, see who picked and packed it, watch the packing video | per buyer claim | desk or phone, good network | password + two-step code | status and video in front of them in seconds |
| **Host** (`host`) | **Scanit**: scan the product in her hand and read its name, retail price, our target price and its notes while selling | every product, for the length of a live | on air; phone or iPad on a stand beside her, glanced at from arm's length; one hand holds the product; camera or a Bluetooth scanner; the screen must stay awake | username + password (two-step: see Q8) | the product's card is on screen a moment after the scan, and she never has to touch the phone between products |
| **Admin** (`admin`) | everything a manager does, plus the full console (users, settings, TikTok, shipments, inventory) when away from a computer | daily glance; occasional deep task | at home, phone | password + two-step code | floor status at a glance; any console page reachable when really needed |
| **Reviewer — floor login** (demo `worker`) | follow the review notes: sign in, pick an order, pack a box from the sample-label PDF, look up a label, delete the account | once, ~10 minutes, has never seen a warehouse | no scanner, no second device, scans a PDF off a screen | username + password only (demo company) | every step in the notes works and no screen looks like a website |
| **Reviewer — second login** (demo `manager`) | see the other account type: the shows on Today, the packing video of the box just packed, a product lookup | a few minutes | same | username + password only (demo company) | sees a different Today, plays a video, never meets a desktop page |
| **Platform owner** (`superadmin`) | not an app user | — | — | — | told the console is on the web (§2) |

Order of care, as Ofir set it: workers → manager → admin. The host is planned to the same standard because Q4 put her tool in 1.0.

---

## 2. App map

Before sign-in there is **no tab bar**: one native sign-in screen in front of everything (answers K7a, R2).

After sign-in the tab bar is built **once per account** from what the server says that account may do, and does not change with data or state (an empty section explains itself; a tab never disappears mid-session). That is this blueprint's reading of HIG "don't disable or hide tab bar buttons": the rule is about an unstable interface, and a tab that would always answer "Access denied" for this account is not a section of this person's app (K7b). app-review should confirm that reading.

| Role | Tab 1 (launch) | Tab 2 | Tab 3 | Tab 4 | Tab 5 |
|---|---|---|---|---|---|
| `worker` | **Today** | Pick | Pack | Account | — |
| `manager` | **Today** (manager sections) | Pick | Pack | Account | — |
| `cs` | **Today** | Pick | Pack | Account | — |
| `host` | **Today** | Scanit | Account | — | — |
| `admin` | **Today** (manager + admin sections) | Pick | Pack | Manage | Account |
| Demo floor login | exactly as `worker` | | | | |
| Demo second login | exactly as `manager` — no Manage tab, no special case in the app | | | | |
| `superadmin` | no tabs: a native screen "The platform console is on the web" with Sign out | | | | |

**Where Scanit sits (new).** The server lets four roles use Scanit: admin, cs, manager and host (`app.py:15875-15876`, `16088-16089`). One rule decides how each reaches it:

- an account that may use Scanit and may **not** pick (in practice: a host) gets **Scanit as a tab**;
- an account that may use Scanit and may also pick (cs, manager, admin, or a worker who also holds the host role) reaches the same screen from a row on **Today**, next to "Look up a label".

That keeps four tabs for the floor and five for admin, and no role lands on the desktop `/scanit` page. A worker has no Scanit entry and the server refuses it.

A user with several roles (`extra_roles`) gets the union: any role that may pick adds Pick and Pack, `admin` adds Manage, and the Scanit rule above applies to the result. The app does not work this out itself — see N3.

**Launch screen: Today, for every role.** Cold start with a live session opens Today; returning from the background keeps the person where they were. HIG Launching asks apps to restore the previous state on restart; Today's "Continue" row ("Keep picking {show}") is how this plan meets that without reopening a half-finished order from a stale state. For the host this means one tap to Scanit after a cold start and none after that: during a live the app stays on the Scanit tab. ios-designer and app-review should weigh the launch choice on the mockup.

What sits behind each tab:

| Tab | Root | Pushed / presented from it |
|---|---|---|
| **Today** | `/m/today` — my numbers, Continue, Look up a label, floor now; manager and admin also see each open show (to pick / to pack / issues); cs / manager / admin also see a Scanit row | Track (`/m/track`), Cleanup (`/m/cleanup`), Scanit (`/m/scanit`) for accounts without a Scanit tab |
| **Pick** | `/m/pick` — show queue | order checklist, report-a-problem sheet, Cleanup when a show's table must be cleared first |
| **Pack** | native Pack — scan stage | box contents + recording, saved |
| **Scanit** (host) | `/m/scanit` — ready to scan | product card |
| **Manage** (admin only) | the desktop site in a web view under a native title; never the launch tab | every desktop page the admin can open |
| **Account** | native — name, role, company | language, two-step verification, privacy, terms, support, sign out, delete account |

Decisions built into this table:

- **No "More" tab and no `/api/mobile/nav`.** What More held is in Account (language, sign out), dropped from 1.0 (§3.2), or inside Manage for admins.
- **Track is not a tab** (Q2). It is one tap from Today, and a scan made on Today is a lookup (§5.1).
- **Manage is admin-only** (Q1). Managers and cs lose in-app access to the desktop pages they reach through today's Dashboard tab; those pages still open in the phone's browser.
- **Manager and admin get no tabs that point at desktop pages.**

### iPad (D4 — decided after the M1 device round; both branches stay planned)

| | If iPad is in 1.0 | If 1.0 is iPhone-only |
|---|---|---|
| App map | identical: same tabs per role. The system places the tab bar near the top on iPadOS. **Tab bar only — no sidebar** in 1.0: three to five sections do not need one (HIG Tab bars, Sidebars). | identical |
| Layout | every 1.0 screen must hold at regular width and in a resized window, decided by size class (HIG Layout); `/m/` screens as a centred column. The two main iPad jobs: Pack on a stand in landscape with a hardware scanner, and Scanit on a stand beside the host | compact width only |
| Cost | device proof of every flow in §4 on an iPad in portrait, both landscapes and a resized window; 13-inch screenshots (K6) | `TARGETED_DEVICE_FAMILY: "1"`; floor iPads keep using the browser stations exactly as today, and a host with an iPad keeps the desktop `/scanit` page in the browser; iPad work moves to 1.1 |
| What the blueprint assumes | nothing in 1.0 exists only on iPad or only on iPhone | same |

So D4 changes proof, screenshots and one build setting — not the map, the inventory or the flows.

---

## 3. Screen inventory

A screen with no row does not get built. "Roles" lists who can reach it in the app.

### 3.1 Screens in 1.0

| # | Screen | Purpose | Roles | Lives | State today | Release |
|---|---|---|---|---|---|---|
| S1 | **Sign-in** | username + password; **two-step step** with the method the account has — authenticator code, text-message code, or the person's choice when both are set up — and a recovery-code fallback; "Scan badge" (camera or scanner) for floor roles; Privacy and Terms links | everyone | native | **missing** as a native screen. Endpoints exist for password, authenticator code and badge: `POST /api/login`, `/api/login/2fa`, `/api/badge-login`. **Text-message codes do not exist anywhere on the server** (N13). Spec `sign-in.md` needs changes (§8) | 1.0 |
| S2 | **Role-built tab bar** | the table in §2 | everyone | native | **missing** (three fixed tabs: Dashboard, Pick, Pack; launch tab is the desktop site) | 1.0 |
| S3 | **Today** | "what should I do now": my packed / picked today, Continue, Look up a label, floor now. Manager/admin: each open show with to-pick / to-pack / issue counts, overdue first. cs / manager / admin: a Scanit row. Admin: today's sales line. Host: greeting and one row that opens the Scanit tab | all five roles | `/m/today` | page **specified** (`today.md`, needs changes), not built. Data **exists**: `GET /api/today` is role-aware and returns the per-show backlog, issue count and admin money; `/api/pick/my-stats`, `/api/me/stats`. What it returns to a host was not checked | 1.0 |
| S4 | **Pick** — queue, order checklist, report a problem, cancelled-order stop | pick a show's orders | worker, cs, manager (through the server's manager→admin rule), admin | `/m/pick` | **exists**; three links leave for desktop pages and must change (N7) | 1.0 |
| S5 | **Table cleanup** | pull cancelled items off the table, show by show; Pick sends workers here when a show is blocked | worker, cs, manager, admin | `/m/cleanup` | page **specified** (`cleanup.md`), not built; today Pick jumps to the desktop `/admin/cleanup`. Data **exists**: `/api/cleanup/shows`, `/api/cleanup/<show>`, `…/mark` | 1.0 |
| S6 | **Pack** — scan, contents, record, upload, next | pack with video proof | worker, cs, manager, admin (exact list is the programmer's SEC-8 fix; host is out) | native | **exists** (`Features/Pack/`); gaps in N8 | 1.0 |
| S7 | **Track** (label lookup) | scan or type a label → show, buyer, status, who picked and packed, last event; for cs / manager / admin also **the packing video, played in the app** (Q5) | worker, cs, manager, admin | `/m/track`, pushed from Today | page **specified** (`track.md`, needs changes), not built. Data **exists**: `GET /api/shipment/<code>`. Whether that answer carries enough to play the video: **not verified** (N10) | 1.0 |
| S8 | **Account** | name, role, company; language; **two-step verification** (opens S12); Privacy, Terms, Support (support@liveopshub.com); sign out; delete account (own screen: what is deleted, password, two-step code when enrolled, confirm; last admin gets the second "this deletes the company" confirm) | everyone | native | **missing** (`LegalLinks.swift` exists, unused; deletion is at the bottom of the desktop `/me`). Endpoint exists: `POST /api/account/delete` incl. `need_org_confirm` | 1.0 |
| S9 | **Manage** | the desktop console, presented as what it is, under a native title | admin only | desktop pages inside the Manage tab | **exists** as today's Dashboard tab (shown to everyone, launch tab) | 1.0 |
| S10 | **Camera scan sheet** | camera + typing fallback for any scan asked by an `/m/` page | whoever is on that page | native | **exists** (`ScannerSheet`) | 1.0 |
| S11 | **System states**: offline / can't reach server; update required; session expired; subscription inactive; two-step set-up required (hands over to S12); account type not supported (`superadmin`) | never a blank or desktop page | everyone | native | offline + update required **exist**; the other four **missing** (today they surface as desktop redirects: `/`, `/billing`, `/me?setup2fa=1`) | 1.0 |
| S12 | **Two-step verification set-up** (new) | choose a method — authenticator app or text message; authenticator: QR / key, confirm a code; text message: enter a US mobile number, confirm the code sent to it; then the recovery codes, shown once. Also: add the second method, change the phone number, see which methods are on (number shown masked) | accounts that must or do use two-step (see Q8); refused in the demo company | native; reached from the "set-up required" state and from Account | **missing**. Authenticator endpoints exist (`/api/2fa/setup`, `/enable`, `/status`, `/recovery`, `/disable`) but answer only to admin, and to a manager through the manager→admin rule; **cs is refused today**. Nothing exists for text messages. No spec | 1.0 |
| S13 | **Scanit** (new) | scan a product barcode → its card: picture, name, retail price (MSRP) with where the price came from, our target price, and its notes (fragrance top / heart / base, or short selling points) with their source. **Read-only on the phone in 1.0** | host (tab); cs, manager, admin (from Today) | `/m/scanit` | page **missing**, **no spec**. Data **exists**: `GET /api/scanit/scan?code=` and `GET /api/scanit/item?sku=` for admin, cs, host, manager (`app.py:16088-16123`); the desktop page `/scanit` exists | 1.0 |

### 3.2 Screens not in 1.0

| Screen | Roles | Lives when built | State today | Release | Why it waits |
|---|---|---|---|---|---|
| News (announcements, with "Got it") | all | `/m/` | specified; desktop page exists | **1.1 — first** (Q3) | managers' channel to the floor; needs a badge rule |
| My Schedule | all | `/m/` | specified | **1.1 — second** (Q3) | read-only, small |
| Shows (manager) and Issues queue | manager, cs, admin | `/m/` | not specified; desktop pages exist | 1.1 | the manager's next need after Today. app-review asked for it before a *public* listing only; D5 is unlisted, so it stays here |
| Scanit — fixing a product (name, price, notes), forcing a new lookup | cs, manager, admin | `/m/` | endpoints exist (`POST /api/scanit/item`, `/api/scanit/item/lookup`); not specified | 1.1 | done at a desk today; the forced lookup is a paid call |
| Scanit — search by product name, saved favourites, a scan history that survives closing the app, AI-drafted selling scripts | host, cs, admin | `/m/` | endpoints exist only on the **old** Scanit table (`scanit_products`), not on the catalog the scan screen now reads; whether the desktop page still uses them was not checked | later | needs server work first; none is needed to sell a product on air |
| Leaderboard | all | `/m/` | specified | 1.1 | motivation, not work |
| My numbers / achievements / recent packages (the top of `me.md`) | all | `/m/` or native | specified | 1.1 | Account in 1.0 is account only |
| Optional two-step verification for roles that are not required to use it | worker, host | native (S12) | missing | 1.1 | 1.0 offers S12 to the accounts that must use it |
| Onboarding checklist | new hires | `/m/` | specified | later | |
| Documents | all | `/m/` | specified | later | includes signing and ID documents; keeping it out of the app keeps the privacy answers simpler (K11) |
| Guides | all | `/m/` | specified | later | |
| Live Mode, Match Products | worker, cs, admin | `/m/` | specified | later | real floor work, but two long scanning flows; how often they are done on a phone is not known |
| Push notifications, widgets, offline picking queue | — | native | missing | later | app-review: none is needed for 4.2 |
| **More tab, `/api/mobile/nav`, `/more` web page, native Appearance/theme picker, global search field, a company-colour setting in the app** | — | — | specified in `more.md` / `DESIGN_SYSTEM.md §3` | **not in the app** | replaced by §2 and D8 |
| Welcome chooser (`/welcome`), badge page (`/badge-login`), desktop `/login`, `/me`, `/home`, `/billing`, `/scanit`, the web two-step enrolment on `/me` | — | — | exist on the web | **not in the app** (reachable only by an admin browsing inside Manage) | replaced by S1, S3, S8, S11, S12, S13 |
| iPad web packing station (`/`, `WORKER_HTML`) | worker | browser | exists | **not in the app** | the floor's browser stations are untouched |
| Platform console (`/admin/organizations`) | superadmin | browser | exists | **not in the app** | |

### 3.3 Pieces 1.0 needs that do not exist today

Each becomes its own board entry. N1–N12 keep their numbers from the draft (the board refers to them); N13–N18 are new.

| # | Piece | Needed by | Owner |
|---|---|---|---|
| N1 | Native sign-in gate in front of all tabs (S1): password, the two-step step with method choice, text-message "send / resend" with a wait, recovery code, badge scan, legal links, error and throttle messages | every flow | ios-designer → ios-engineer |
| N2 | Tab bar built from the session (S2), rebuilt when the session's capabilities change (role changed on the server, sign-out, another user signs in) | every flow | ios-engineer |
| N3 | **`/api/mobile/session` tells the app what this account may open** — `can: {pick, pack, track, scanit, manage}` computed by the same check the routes use. Today it returns only `roles` (`app.py:4852-4874`); the app cannot derive from `["manager"]` that a manager may pick or use Scanit, because that comes from the server's manager→admin rule (`req_role`). Roles stay enforced on the server; this field only decides which tabs and Today rows are drawn. Also in the same answer: `must_setup_2fa`; the two-step state of the account (required or not, which methods are on, the phone number **masked**); a billing-locked flag; a `sandbox` flag (for the "Demo company" banner, security requirement 10). The support address is fixed by D7 and does not need to come from the server. | S2, S3, S11, S12 | programmer (shared-logic PR) → security-reviewer |
| N4 | `/api/mobile/session` must answer while the two-step set-up gate or the billing gate is active. Today both gates stop it (it is in neither `_2FA_SETUP_OPEN` nor `_BILLING_OPEN_PATHS`, `app.py:3893-3929`), so the app would get 403 / 402 instead of a session. By code reading — not run. | S11, S12 | programmer |
| N5 | Native Account (S8) incl. delete-account screen with password and two-step code (SEC-7 changes the endpoint) and the last-admin confirm; sign-out that ends the session on the server and clears both cookie stores | flows 4.1, 4.7 | ios-engineer; programmer for SEC-7 / SEC-10. Only `GET /logout` (a redirect) exists; whether a JSON sign-out is needed is the engineers' call |
| N6 | Bridge additions: `LOHubNative.openTab(id)` (Today → Pick / Scanit, Track → Pack, avatar → Account); a "session ended" signal from `/m/` pages to the shell (today `mobile.js` sends a signed-out page to `/` and a billing-locked page to `/billing`, both desktop pages); **keep the screen awake while Scanit is in front** (a host cannot unlock the phone mid-sale) | flows 4.3–4.6, 4.9 | ios-engineer + mobile-engineer; security-reviewer (bridge) |
| N7 | `/m/pick` clean-up: cleanup gates → `/m/cleanup`; avatar → Account tab instead of desktop `/me`; the browser-only web tab bar in `pick.html` still lists Track and More | flow 4.3 | mobile-engineer |
| N8 | Pack gaps: (a) a failed upload **deletes the recording** and the packer must film the box again (`PackFlowView.swift` `stopAndUpload`, by reading) — keep the file and retry; (b) session-expired handled by the gate instead of "Open the Dashboard tab and sign in" (K7a); (c) Spanish strings (P3) | flow 4.4 | ios-engineer |
| N9 | `/m/today`, `/m/track`, `/m/cleanup` and **`/m/scanit`** pages, each with its browser check | flows 4.3, 4.5, 4.6, 4.9 | mobile-engineer (roadmap M5) |
| N10 | Packing video from a lookup for cs / manager / admin — **now a 1.0 requirement** (Q5). `/media/video/<file>` exists for admin and cs, and a manager through the server rule (`app.py:14300-14318`); whether `GET /api/shipment/<code>` gives the file name was **not verified**. If not: one read-only field or endpoint. A worker must not receive it. | flow 4.6 | programmer to confirm, then security-reviewer |
| N11 | Manage wrapper (S9): admin-only, native title, exact-host rules (SEC-15), bridge closed to sub-frames (SEC-16) | admin | ios-engineer |
| N12 | Demo company (D1), the two logins **manager + worker** (D2), and the sample PDF. The seed must contain, besides orders to pick and pack: **one order already packed with a packing video** (so the manager can show a video even if the reviewer's own recording failed), and **three catalog products with a picture, a typed retail price and notes**, one of whose barcodes is printed on the PDF (so Scanit has something to scan and never needs an outside lookup) | flow 4.8 | programmer (roadmap M3); security-reviewer; app-review |
| N13 | **Text-message two-step verification on the server** (new; nothing exists — the security report lists "SMS: none in the code today", and staff accounts have no phone or email field). Needs: a phone number on the user record (US mobile, verified before it counts); "send code" and "check code" at sign-in and at set-up; the sign-in answer says which methods the account has, with the number masked; codes that are short-lived, single-use, never logged and **stored where every gunicorn worker can read them** (the server runs several workers — no in-process memory); limits per account, per phone number and per network on sending as well as on checking (each text costs money; SEC-11 becomes part of this); the same recovery codes as the authenticator; removing or changing a number needs a current code; every send and change in the audit log; a text-message provider behind one transport function with a timeout (Q6). The set-up routes must be usable by every role that has to enrol — today they are admin-gated and **cs is refused**. | S1, S12, flows 4.1, 4.2 | programmer (shared-logic PRs) → qa → security-reviewer. **Must be live before SEC-2 (badge sign-in for floor roles only) is merged** — that is D3's condition |
| N14 | Native two-step set-up (S12) and the two-step row in Account | flow 4.2 | ios-designer → ios-engineer |
| N15 | Scanit for the phone: `/m/scanit` route with the same four roles as the desktop page (mobile-engineer wiring in `mobile/__init__.py`); no new data endpoint for the read-only screen. For the programmer and security-reviewer to settle before it ships: (a) SEC-4 for Scanit, below; (b) `GET /api/scanit/scan` **writes** — it can add a product to the catalog, records the scan, and can start a paid lookup — and, being a GET, it is outside the CSRF check; (c) a first scan of an unknown barcode asks up to four outside databases one after another inside the request (`_barcode_lookup_online`, 6 s limit each, by reading), so the screen needs a waiting state and the server a total time limit; (d) product pictures found by those databases are links to other companies' hosts, loaded by the phone itself — either store them on our side or confirm the app's content policy and privacy answers allow it. | flow 4.9 | mobile-engineer; programmer; security-reviewer |
| N16 | Indigo only (D8): native tint is the LiveOpsHub indigo; `/m/` pages stop emitting the company's colour (today `mobile/__init__.py` `_brand_css()` injects it); read literally, the desktop pages inside Manage also show indigo when opened by the app (`_brand_style()` in `templates.py` — a shared-logic change that must leave browsers untouched). Company **name** stays everywhere. | rule 5.9 | mobile-engineer (`/m/`), ios-engineer (native), programmer (Manage, own PR) |
| N17 | SEC-4 fence additions: the new text-message transport; and for Scanit the barcode databases, the AI lookup and the old AI script route. The Scanit AI lookup runs in a **background thread that has no session** (`_scanit_lookup_info(org, sku)`), so the fence must be decided from the company passed to it, not from the signed-in user. | flows 4.8, 4.9 | programmer → security-reviewer |
| N18 | Public pages and privacy answers: Privacy, Terms and Support on liveopshub.com (D6) with support@liveopshub.com (D7); the staff **phone number** is new personal data — App Privacy answer "Phone Number" (linked to the person, app functionality), the privacy manifest, the policy text, the text-message provider and the barcode databases in the subprocessor list; account deletion removes the number | rule 5.6, flow 4.7 | release-manager (answers, listing), ios-engineer (manifest), programmer (pages, deletion), Ofir (policy wording) |

---

## 4. Flows

Same four failure cases for every flow, answered once here and only repeated where a flow differs:

- **No network:** `/m/` screens show the offline banner and keep what is on screen; actions that need the server say so and can be retried; nothing is queued in 1.0 except what §4.4 says about the packing video. Native screens show the existing "Can't reach LiveOpsHub — Try again".
- **Session expired** (7-day cookie, role removed, user deleted): the shell returns to Sign-in with one line, "You were signed out. Sign in again." After sign-in the person lands on Today, not mid-order.
- **Role without access:** the tab or row is not there. If a stale tab or link is used anyway the server refuses (403) and the screen says "Your account can't open this. Ask your manager." — never the plain text "Access denied".
- **Wrong scan:** the screen says what the code was and what it expected, with one way forward. A scan is never silently dropped.

### 4.1 Sign-in

1. App opens → Sign-in (no tab bar, no camera prompt).
2. Username + password → `POST /api/login`.
3. **Two-step step**, when the account has it. The server's answer says which methods are on:
   - authenticator only → enter the 6-digit code;
   - text message only → "Send a code to •••• 1234" → enter the code; "Send again" after a wait;
   - both → the person picks; the last choice is offered first next time;
   - always available: "Use a recovery code".
   Wrong code: stays on the step and says so. Too many tries, or too many texts requested: "Try again shortly" (429). The step expires after five minutes (server rule today) → back to the password form with "Sign in again".
4. **No phone number on file.** The text-message option is simply not offered; the step shows the authenticator and the recovery code, and one line: "Text-message codes aren't set up for this account. You can add a phone number in Account after signing in." The app never asks for a phone number before the person is signed in.
5. A text that never arrives: "Send again" (limited), then the other method if the account has one, then a recovery code, then "Ask your admin to reset two-step verification". Whether an admin can reset another person's two-step today was not checked (§9).
6. **Floor accounts** may instead tap "Scan badge" → camera or Bluetooth scanner → `POST /api/badge-login`. Once SEC-2 is in, a badge that belongs to an admin, manager or cs is answered with "Use your password" and the password form (D3).
7. Shell reads `/api/mobile/session`, builds the tabs (§2), opens Today.
8. Variants: two-step set-up required → flow 4.2; organisation suspended or billing-locked → "Your company's subscription is not active. Ask your admin." with Account still reachable for sign-out and deletion, no prices and no link to buy (K8); `superadmin` → "console is on the web"; app too old → Update required.
- No network: the form stays, "Can't reach LiveOpsHub", retry. Privacy and Terms open in an in-app browser sheet from this screen (K1).
- Demo company: no two-step step at all, and **no text message is ever sent** for a demo-company account, whatever is requested (N17).

### 4.2 Setting up two-step verification (new)

Starts in one of two places: the "set-up required" state straight after the password (an account that must use two-step and has none), or Account → Two-step verification.

1. Choose: **Authenticator app** or **Text message**. One sentence each on what it needs.
2. Authenticator: the key as a QR code and as text → enter a code from the app → on.
3. Text message: enter a US mobile number → a code is sent → enter it → on. A number is saved only after its code was confirmed.
4. Recovery codes are shown once, with Copy; the person confirms they kept them.
5. From Account later: add the other method, change the number, switch a method off — each asks for a current code first. An account that must use two-step cannot switch off its last method.
- Until set-up is finished the account can do nothing else except open Account, sign out and delete the account (the server's gate already works this way).
- Wrong or expired code: stays on the step. Number not accepted (not a US mobile, or the provider refuses it): says so, offers the authenticator.
- No network: nothing is saved; says so.
- Demo company: the row in Account reads "Not available in the demo company"; nothing can be changed (security requirement 6).
- This flow replaces the draft's exception (the web enrolment page in a sheet). With it, **no desktop page is shown anywhere outside Manage.**

### 4.3 A picker's shift

1. Today → "Continue: keep picking {show}" or the Pick tab.
2. Pick queue → tap a show (or scan a label straight away — the scan finds its show).
3. If the show's table must be cleared first, Pick opens **Cleanup** for that show (`/m/cleanup`), the worker marks each cancelled item pulled, "Done", back to Pick. (Today this step is a desktop page.)
4. Scan a packing label (Bluetooth scanner with nothing tapped, camera button, or typing) → order checklist.
5. Tick each item → "Done — scan next" → next scan. "Report a problem" → reason → the order goes to Issues, the picker continues.
- Wrong scan: label from another show → "It belongs to {other show}" with Switch / Cancel; unknown code → "No order for {code}" + Type it instead; cancelled order → full-screen "Don't pick this order".
- No network mid-order: ticks already sent stay; a tick that fails says so and is not shown as done (the server is the record — warehouse progress is never invented on the phone).
- Session expired mid-order: Sign-in → Today → Continue brings the show back; ticks already saved are still ticked.
- Host or any account without `can.pick`: no Pick tab.

### 4.4 Scan → pack → next box

1. Pack tab → scan the shipping label (scanner, camera, typing).
2. Contents card (combined packages and giveaways included) → recording starts (auto-record on by default).
3. Scan again or tap Stop → upload → "Packed" → next label. If the second scan was the next box's label, that box opens.
- Wrong scan: unknown → "Shipment not found", stays on scan; cancelled → "This order is cancelled — don't ship it"; a scan while a box is open but not recording is ignored today — it should say so (N8).
- No network at step 1: cannot look up; says so. **At step 3: today the video is lost and the box must be filmed again (N8a). 1.0 requirement: the recording is kept and the upload retried; the order shows as packed only after the server accepted the video, so stock is still deducted exactly once.**
- Session expired: Sign-in, then back on Pack; a kept recording is uploaded after sign-in.
- Camera or microphone refused: typing and a hardware scanner still work for the label; without the camera there is no video — say what to switch on in Settings. Microphone is optional.
- Signed out: cannot happen — the gate is in front (K7a).

### 4.5 A manager checking a show

1. Today (manager sections): open shows, most overdue first, each with to-pick / to-pack / issue counts; floor now (pickers and packers online, picked and packed today); open-issues count.
2. Needs to act → Pick tab (same show list) or Pack tab; needs one order → Look up a label (4.6).
3. Needs the Shows or Issues desktop pages → not in the app in 1.0 (Q1); the phone's browser still opens them; in 1.1 they are `/m/` screens.
- In 1.0 the manager's Today is read-only: there is no close-show, re-import or issue-resolve action in the app, so no money or irreversible action is reachable from a manager's phone.
- No network: last numbers stay with "may be out of date".

### 4.6 Looking up a label for a buyer's claim

1. Today → "Look up a label", or scan while on Today → Track.
2. Scan or type the tracking / order number → result: status, show, buyer, items, picked by, packed by, last event.
3. cs / manager / admin: **"Packing video" plays in the app** (Q5). No video yet (order not packed, or the upload has not arrived): the row says so instead of showing a dead player. Workers do not get the video (server rule: playback is admin, cs, manager).
4. From the result: status *pending* → "Open in Pick"; *picked* → "Pack this order" (opens the Pack tab on that label).
- Wrong scan: "No order found for {code}". A product barcode scanned here gets the same answer; it is not passed on to Scanit.
- No network: "Lookups need a connection". A video that stops mid-play offers Retry; the link is short-lived (15 minutes on the server), so a retry asks for a fresh one.
- Host: no entry on Today; the server-side hole (a host can read any order through `/api/shipment`) is SEC-8 and is closed on the server, not by hiding the entry.
- Buyer address: the result shows the buyer's name and items, not the full address — the programmer's SEC-8 fix (named fields instead of the whole row) decides what the app receives.

### 4.7 Account deletion

1. Account tab → Delete account → a screen that says what is deleted and what the company keeps. That wording mirrors the privacy policy and waits for Ofir's sign-off (D7).
2. Enter the password, and a two-step code when enrolled — from the authenticator, or sent by text message on request (SEC-7) → confirm.
3. Last admin of a company: a second confirm that names the company — "This also deletes {company} and all its data" → `wipe_org`.
4. Success → signed out → Sign-in, with one line confirming the deletion. The phone number goes with the account.
- Reachable when the company is billing-locked and during two-step set-up (the server already allows it).
- Demo company: the server answers success, signs out, and the account still exists (security requirement 7); the app does nothing special. Because the demo logins are a worker and a manager, **no reviewer account is ever the last admin**, so the "this deletes the company" confirm cannot be reached from a demo login (K3).
- No network: nothing is deleted; says so.
- Never reachable by accident: destructive style, its own screen, password. Answers K2, K3.

### 4.8 The reviewer's ten minutes (D1, D2)

The notes give two logins — a worker and a manager — and a PDF with sample shipping labels and one product barcode. Neither login meets two-step verification, a text message, the Manage tab or a desktop page.

1. Sign in with the **worker login**.
2. Today: a "Demo company" banner, numbers, Continue.
3. **Pick:** Pick tab → the demo show → scan a label from the PDF with the camera (or type the number from the notes) → tick items → Done.
4. **Pack:** Pack tab → scan the same label → contents → recording → Stop → "Packed".
5. **Track:** Today → Look up a label → the same number → status now *packed*, who packed it. (A worker sees no video.)
6. **Account deletion:** Account → Privacy, Terms, Support → Delete account → password → signed out. The notes say to test deletion with this login; it is restored (K3).
7. Sign in with the **manager login**. Today now shows the shows and their counts; the tabs are the same four.
8. **Track with video:** Look up a label → the label packed in step 4 → the packing video the reviewer just recorded plays. The notes also name the label of the order that was seeded already packed, in case the reviewer's own upload failed.
9. **Scanit:** Today → Scanit → scan the product barcode on the PDF → the product card.
10. The notes say, in one sentence each: company admins also have a Manage tab that opens the web console; hosts get Scanit as their own tab; real accounts with management roles sign in with two-step verification (authenticator app or text message), which is switched off in the demo company only.
- Wrong scan: anything else the reviewer scans gets "No order for {code}" / "Not a product barcode", and the typed numbers still work.
- Nothing a reviewer does can leave the demo company or break it for the next reviewer (SEC-4, SEC-7, K3) — that is M3's job; the app only needs the banner.
- app-review should confirm that two logins cover what Apple expects, given that the admin and host account types are described but not handed over.

### 4.9 A host on air with Scanit (new)

What Scanit is, from the code: the host scans a product's barcode and the server answers from the company's one product catalog — the same `products` table inventory, picking and Live Mode use — with the name, picture, retail price, our target price and the product's notes. No stock is touched. If the catalog does not know the barcode and it looks like a real product barcode (8–14 digits), the server looks it up in outside barcode databases and **adds it to the catalog**, or adds a placeholder marked "Needs review" when nothing is found. If notes or a trustworthy retail price are missing, the server looks them up **once** in the background with an AI service that searches the web, saves the result on the product with its source, and never asks again; a price the team typed is never overwritten.

1. Scanit tab (host) or Today → Scanit (cs, manager, admin). The screen is ready to scan and keeps the phone awake.
2. Scan the product: Bluetooth scanner with nothing tapped, the camera, or typing the barcode or our SKU → `GET /api/scanit/scan`.
3. The product card: picture, name, retail price with where it came from (typed by the team · the brand's page · an estimate · a store price), our target price, notes with their source. An estimate or unchecked notes are labelled as such — the host must be able to tell a checked fact from a guess before she says it on air.
4. Details still being looked up (`info_status` "looking"): the card shows what is known and "Looking up details…", then fills in by itself (`GET /api/scanit/item`). The host does nothing.
5. Next scan replaces the card. The products scanned since the screen was opened stay in a short list to tap back to; the list is not kept after the app closes (1.0).
- **Wrong scan:** a shipping label, a link or stray text → "That's not a product barcode" (the server answers "not found" and adds nothing).
- **Unknown product barcode:** a first-ever scan can take many seconds while the outside databases are asked (N15c) — a visible "Looking this barcode up…" that cannot be double-fired. Then either the product found, marked "New — added to the catalog", or "New product — not recognised. Ask an admin to complete it."
- **Lookup failed or the AI service is not set up:** the card shows what the catalog has and "No more details found". The server retries on its own later, at most twice per product; the phone has no retry button in 1.0.
- **No network:** "Scanit needs a connection"; the last card stays on screen.
- **Role without access:** a worker has no entry and gets 403.
- **Session expired:** Sign-in, then Today; one tap back to Scanit.
- **No editing on the phone in 1.0.** Fixing a name, price or notes and forcing a new lookup stay on the desktop (admin: inside Manage; manager and cs: in the browser). The host can never edit — the server already refuses her.
- **Demo company:** the seeded products are complete, so a scan of the PDF's barcode needs no outside call. Any other barcode gets a fixed answer from the server; no barcode database and no AI service is contacted, and the demo catalog cannot grow without limit between resets (N17).

---

## 5. Rules that span screens

1. **Scanning is the same everywhere.** Three inputs on every scan screen: Bluetooth/USB scanner in keyboard mode with nothing tapped, the camera, typing. What a scan *means* depends only on where you are: on Pick → open that order to pick; on Pack → open that box / stop and save; on Today or Track → look that label up; on Scanit → show that product; on Sign-in → badge. A scan never buys a label, ships, cancels or changes stock, and never switches tabs by itself. One thing a scan can do that costs a little: the first Scanit scan of a product may start the one-time lookup (§4.9).
2. **Language.** English and Spanish for everything a floor role sees: Sign-in, two-step set-up, Today, Pick, Cleanup, Pack, Track, Scanit, Account, system states. Chosen once in Account (default: the device language), applied to native and `/m/` screens together. Product names and notes on Scanit are shown as stored (English). Manage is whatever the desktop is. Today Pack and all native text are English only (P3).
3. **Offline and retry.** No screen goes blank or falls back to a web error. Reads show the last data with "may be out of date"; writes fail visibly and can be retried; the only thing held on the device is a packing video waiting to upload (N8a).
4. **The server is the record.** The app shows picked / packed only after the server said so. No tab, button or hidden entry is a permission: every role rule is enforced on the server.
5. **Badges and notifications.** 1.0 has no push notifications and no tab badges. When News arrives in 1.1 it gets the first badge; HIG reserves badges for critical information.
6. **Sign-out, help and legal are always in the same place:** the Account tab — Support (support@liveopshub.com), Privacy, Terms, Sign out, Delete account. Privacy and Terms are also on Sign-in. Legal and support pages are on liveopshub.com and open in an in-app browser sheet.
7. **What a worker can never reach from the app:** the Manage tab or any desktop page; label buying, shipping, cancels, stock adjustments; users, roles, settings, billing, TikTok connection; packing videos; Scanit and our target prices; another company's anything. Same for the demo floor login. A manager and cs additionally cannot reach Manage. A host reaches Scanit and Account, and nothing about orders.
8. **Web content stays in two boxes.** `/m/` pages (our host, phone-built, bridge enabled on the main frame only) and Manage (admin, desktop pages). No `/m/` screen links to a desktop page; mobile-qa should fail a screen that does. The one known exception to "our host only" is a product picture on Scanit that an outside database supplied (N15d).
9. **Appearance.** One look across native and `/m/` screens (P2): 1.0 follows the system light/dark setting, with no in-app theme picker. **The colour is always LiveOpsHub indigo** (D8) — native tint, `/m/` screens and, read literally, Manage; a company's own colour never appears in the app, its name does.
10. **One sign-in, one session.** The native screens and the web views share the session; signing out anywhere signs out everywhere in the app.
11. **Two-step verification (new).** One step, one place: after the password on Sign-in. The person chooses between the methods their account has; the app never asks for a phone number before sign-in and never shows a full number afterwards. Text messages go to US mobile numbers only in 1.0. The demo company has no two-step verification and never sends a text.
12. **Checked facts and guesses look different (new).** Anything on Scanit that came from an AI estimate or an unchecked source is labelled, so nobody reads a guess out on air as a fact.

---

## 6. The 1.0 scope line

**In:** native Sign-in with two-step verification (authenticator or text message), native two-step set-up, role-built tabs, Today, Pick, Table cleanup, Pack, Track with the packing video, Scanit (read-only), Account, the system states, and Manage for admins.

**Out, deliberately:** More; News and My Schedule (first two screens of 1.1); Leaderboard, Onboarding, Documents, Guides, the "my numbers" profile; Live Mode and Match Products; Shows / Issues / Inventory / Shipments for managers on the phone; editing a product, forcing a lookup, name search, favourites and selling scripts in Scanit; optional two-step verification for workers and hosts; push notifications; offline picking; an iPad sidebar; a theme picker; a company colour.

**Why:** a worker's whole day, a host's whole live and everything the reviewer is told to try must never touch a desktop page (R2). With native two-step set-up in 1.0 there is no longer any exception: outside the admin-only Manage tab the app shows no desktop page at all.

**What Ofir's answers added to the draft's 1.0** — two things, both real work: Scanit (one new `/m/` screen with no spec, plus its sandbox fence) and text-message two-step verification (new server capability, a provider account, two native screens, and it has to be live before badge sign-in is narrowed). Of the two, the text-message work is the one on the critical path: M2's SEC-2 waits for it, and the demo company waits for SEC-2.

**What unlisted + United States only means for scope (D5):**
- 1.0 stays as drawn. app-review asked for phone-built Shows and Issues only before a *public* listing; they stay in 1.1.
- Apple declines an unlisted request for an app "in a beta or prerelease state" (app-review's report). So 1.0 carries **no "coming soon" rows, no empty placeholder tabs and no pointers to the website for missing features**; a host's Today shows what exists.
- English and Spanish in the app; text messages to US numbers only; no EU trader paperwork. The "request access" sentence in the listing may stay (K8) — release-manager's call.
- The app is installed from a link, not found by search; nothing in the app assumes a public store page except the "Update required" button, which opens the app's own store page by id (P1) — that this works for an unlisted app was not checked.

**What real users give up in 1.0, compared with build 5:** workers, managers and cs can no longer open the desktop site inside the app (schedule, news, leaderboard, shows, issues …). Those pages still work in the phone's browser, as they did before the app existed. Managers and cs, and any admin who used a badge, sign in with password and a code from the day SEC-2 lands.

**First things to cut if 1.0 must shrink:** the admin sales line on Today; the Scanit row on Today for cs / manager / admin (host keeps the tab); badge scan on the native Sign-in (password only — the browser stations keep their badge page). Not cuttable any more: Scanit, the packing video in Track, text-message two-step.

---

## 7. Open questions for Ofir

Only what the answers above newly raise and what cannot be settled from the code. Each blocks a named piece.

| # | Question | Option A | Option B | Recommendation |
|---|---|---|---|---|
| **Q6** | Which text-message service sends the codes? Blocks N13 (and through it SEC-2 and the demo company). Needs an account, a monthly cost and a key that only Ofir can enter in Railway. | **A verification service** (the kind that sends and checks the code for us, such as Twilio Verify). Costs a few cents per sign-in; the provider handles the sender identity and delivery; least code on our side. | **Our own number with a plain text-message service.** Cheaper per message; but a sender must register with the US carriers before an application may text US numbers from an ordinary number (Twilio's A2P 10DLC page, read today), the wait is not stated there, and we write and guard the code handling ourselves. | **A.** The programmer confirms price and lead time before Ofir opens the account; this is the first thing to start, because everything in D3 waits for it. |
| **Q7** | Who puts the phone number on an account? Blocks the S12 spec and N13. | **The person, during set-up in the app** — types their own number and proves it with the code. Nothing for an admin to do; the number is known only to the person and the server. | **An admin types it in Users**, the person only confirms the code. An admin controls which phone receives the codes; costs a desktop change (product-engineer) and puts every manager's number in front of admins. | **A.** Admins keep one power: resetting someone's two-step verification when a phone is lost (to be confirmed that it exists — §9). |
| **Q8** | When badge sign-in is limited to floor roles, who **must** use two-step verification? The board's D3 text says admins, managers and cs sign in with password + two-step; the code today requires it for admin only, and SEC-1 left "manager" to be decided. Blocks N13 (who is gated) and how many people meet set-up on day one. | **Admin, manager and cs must**; host and worker sign in with a password (worker also by badge) and get optional two-step in 1.1. Every manager and cs sets it up once, at their next sign-in after the change — a text message makes that a one-minute job. | **Admin only must**; manager and cs sign in with a password alone once their badge stops working. Less friction; but the security report calls the manager a near-admin and a password alone is what SEC-1 was written against. | **A** — it is what D3 said, and this blueprint is drawn for it. Tell the managers and cs the date beforehand. |

Not a question, but waiting on Ofir: sign-off on the policy wording (D7), which the delete-account screen and the phone-number sentence both quote.

---

## 8. Work for ios-designer

app-planner does not edit specs. This is the full list, **in the order it should be done**; the first three block engineers.

### 8.1 Order of work

| # | What | Why first / what it blocks |
|---|---|---|
| 1 | **Rewrite `screens/sign-in.md`** as the native Sign-in (S1) and add the two-step set-up (S12) — as one spec or two | blocks N1, N14 and, through them, M4. Needs Q7 and Q8; the screen can be drawn for the recommended answers meanwhile |
| 2 | **`DESIGN_SYSTEM.md` §1.6, §2, §3, §8, §9, §10**: tab bar per role from §2 of this document, no More, indigo only | every other spec leans on it; blocks the tab-bar mockup Ofir is to look at (roadmap M1b) |
| 3 | **Write `screens/scanit.md`** — new, nothing exists | blocks N9 / N15 (M5). Content list in §8.3 |
| 4 | `screens/today.md` | the launch screen; gains the Scanit row and the host variant |
| 5 | `screens/track.md` | gains the in-app packing video (Q5) |
| 6 | `screens/me.md` → native Account | gains the two-step row and support@liveopshub.com |
| 7 | `screens/cleanup.md`, `screens/pick.md`, `screens/pack.md` | smaller corrections |
| 8 | Withdraw `screens/more.md`; mark the eight waiting specs "not in 1.0" | housekeeping |
| 9 | Mockups: the tab bar for worker, manager, host and admin; Sign-in with the two-step step; the Scanit card on a phone on a stand | what Ofir looks at on the phone |

### 8.2 Contradictions between the specs and this blueprint

| File | What contradicts | What must change |
|---|---|---|
| `screens/sign-in.md` | "native sign-in **or** `/badge-login` in a full-screen WebView"; no two-step step at all; no Privacy / Terms links; Welcome screen; a company name in the wordmark example | Native only. Add: the two-step step with **method choice** (authenticator · text message · recovery code), "Send a code to •••• 1234", "Send again" and its wait, the wrong / expired / too-many-tries states, the **no-phone-number-on-file** line (flow 4.1 step 4), badge answered with "Use your password" for non-floor roles (D3), legal links (K1), the system states of S11. Add S12: method choice, authenticator QR and key, phone-number entry (US), code confirm, recovery codes shown once, add / change / switch off from Account, the demo-company "not available" state. Welcome is not in the app. |
| `DESIGN_SYSTEM.md` §1.6, §2, §10 "D1" | Four company themes (Taupe & Teal, Sage & Stone, Slate & Blush) with their own brand rows; "let tenants keep their own color via `_brand_style()`"; "the four themes" as part of the brand; theme in More → Appearance | **Indigo only in the app (D8).** One brand row (indigo → violet), light and dark. The other three themes and the company-colour override are desktop matters and leave this document. Its "D1" is answered: indigo inside the app. |
| `DESIGN_SYSTEM.md` §3.1–3.5 | Native More list; `/api/mobile/nav` as the source of tabs; tab tables (worker: Today/Pick/Pack/Track/More; manager: Today/Shows/Issues/Inventory/More; admin: Today/Shows/Shipments/Insights/More — desktop pages as tabs); "More per role" lists incl. Scanit as a `/scanit` desktop link; `.sidebarAdaptable` on iPad; tab URLs `/home`, `/pick`, `/admin/track` | Replace §3 with the app map in §2 of this document, including the host's Today · Scanit · Account; tabs come from the session's capabilities (N3); iPad is tab bar only. |
| `DESIGN_SYSTEM.md` §8, §9, §10 | Bridge `setBadge` and "More list fed by `/api/mobile/nav`"; "Language moves to More"; its own decisions "D1–D4" collide with the board's D1–D8 | Bridge list = scan, pack, haptic, openTab, session-ended, keep-awake; language in Account; drop or renumber those four decisions (D1 is answered by D8, D2 by §2 here). |
| `screens/today.md` | Path `/home` · `HOME_HTML`; avatar → `/me`; rank tile → `/leaderboard`; "For you" rows → `/onboarding`, `/announcements`, `/my-schedule`, `/documents` (all desktop pages in 1.0); no lookup entry; manager/admin sections "follow later"; no host variant | `/m/today`; avatar → Account tab; drop the rank link and "For you" for 1.0; add "Look up a label" and scan-means-lookup; add the **Scanit row** for cs / manager / admin; specify the manager, admin and **host** variants (host: greeting and a row that opens the Scanit tab — no "coming soon", no website pointer) and the demo banner. |
| `screens/track.md` | "worker tab 4", a tab root; "Managers and admins use it from More"; path `/admin/track`; "Open in Pick" → `/pick?order=` | Pushed from Today; `/m/track`; "Open in Pick" and "Pack this order" through `openTab` / `pack`; **the packing video played in the app for cs / manager / admin** incl. no-video-yet, loading, failed and expired-link states; nothing for a worker; no host access. |
| `screens/me.md` | A web page (`/me` · `ME_HTML`) reached from More; numbers, achievements, recent packages; web QR enrolment; delete by typing DELETE | Becomes the native Account tab (S8): account, language, **two-step verification row → S12**, legal, **Support = support@liveopshub.com** (K4), sign out, delete with password and two-step code (SEC-7) and the last-admin confirm. Numbers / achievements → 1.1. |
| `screens/pick.md` | Path `/pick` · `PICK_HTML`; "Dark mode and Logout move to More"; avatar → `/me`; "Set as picking iPad" → More → Settings | `/m/pick` (as built); Account instead of More; avatar → Account tab; the picking-station setting is a Manage/desktop matter, not in the app. |
| `screens/cleanup.md` | Path `/admin/cleanup` · `CLEANUP_HTML`; no word on how it is entered | `/m/cleanup`; entered from Pick's two gates (with the show preselected) and from Today; "Go to Pick" through `openTab`. |
| `screens/pack.md` | Brand colour "passed through `/api/mobile/nav`"; "never block the next scan (it queues)" is not what the code does | Indigo, fixed (D8) — no colour is passed; state the 1.0 upload rule from §4.4 and the missing states (wrong scan while a box is open, camera refused). |
| `screens/more.md` | The whole spec | Withdraw. |
| `screens/announcements.md`, `my-schedule.md`, `leaderboard.md`, `onboarding.md`, `documents.md`, `guides.md`, `live-mode.md`, `match-products.md` | Back button `‹ More`; "More/News badge"; "language is in More"; desktop paths | Mark each "not in 1.0" with its release from §3.2 (News and My Schedule: 1.1, first). When one is taken up, it is entered from Today, lives under `/m/`, and gets its row here first. |
| *(no file)* | Scanit has no spec | Write `screens/scanit.md` — §8.3. |

### 8.3 What `screens/scanit.md` must specify

The screen is `/m/scanit`, read-only, the same for all four roles. Data: `GET /api/scanit/scan?code=` and `GET /api/scanit/item?sku=`; the fields it gets are `name`, `image_url`, `category`, `barcode`, `msrp`, `msrp_source`, `msrp_manual`, `target_price`, `notes` (`top` / `heart` / `base`, or `points`), `notes_source`, `info_status`, `needs_review`, and on a scan `found`, `created`, `created_source` (`app.py` `_scanit_view`, `api_scanit_scan`).

1. **Two entries, one screen:** tab root for a host; pushed from Today (with a way back) for cs / manager / admin.
2. **Ready state:** the three scan inputs of rule 5.1 — scanner with nothing tapped, camera button, typing a barcode or SKU. What the screen says before the first scan.
3. **Read from a stand at arm's length**, phone and iPad, portrait and landscape; the screen stays awake (N6).
4. **The card:** picture or placeholder, name, category, retail price, target price, notes in either shape (three fragrance lines, or up to six points).
5. **Source labels**, in words a host understands, for the price (typed by the team · brand page · estimate · store price from a named database) and for the notes (typed · found on the web · unchecked). Rule 5.12.
6. **"Looking up details…"** while `info_status` is "looking": what shows meanwhile, how the card fills in without a tap, what "failed" looks like.
7. **First scan of an unknown barcode:** the long wait (N15c), then "New — added to the catalog" or "New product — not recognised" (`created`, `needs_review`).
8. **Not a product barcode** (`found: false`): shipping label, link, text.
9. **The next scan and the short list** of products scanned since the screen opened; tapping one reopens its card.
10. **What is not there:** no edit, no "look up again", no favourites, no search by name, no scripts.
11. Offline, session ended, 403, the demo banner; English and Spanish for every label (product text stays as stored); sound and haptic for found / not found.
12. Whether the target price needs any care on a screen that may be caught by the live camera — a product question for Ofir to glance at on the mockup, not a blocker.

Not specs, but the same contradiction — for their owners: `ios/README.md` and `ios/APP_STORE.md` describe Dashboard / Pick / Pack, an admin demo account and screens that do not exist (release-manager, R3; security requirement 12); `mobile/pick.html`'s browser tab bar still lists Track and More (mobile-engineer, N7); `mobile/__init__.py` still emits the company colour (mobile-engineer, N16); `ROADMAP.md` M2, M3, M4, M5 and M6 do not yet mention text-message two-step, Scanit, the manager demo login's seed needs or the phone-number privacy answer (lead session).

---

## 9. Review findings, decisions, and what was not verified

### Which part answers which finding

| Finding | Answered by |
|---|---|
| R1 demo access | flow 4.8; N12; `sandbox` flag in N3 |
| R2 web wrapper (4.2) | §2 (launch on Today, no desktop tab for the floor, no More), §6 (no desktop page outside Manage, no exception left), rule 5.8 |
| R3 listing ≠ build | §3.1 is the list the listing may describe; "pull up the video" stays true (Q5); product lookup for hosts may now be described |
| K1 privacy in-app | S1, S8, rule 5.6 |
| K2 deletion findable | S8, flow 4.7 |
| K3 reviewer can wipe the demo | flows 4.7, 4.8 — no demo login is an admin (D2), and deletion is simulated |
| K4 support contact | S8 Support row, support@liveopshub.com (D7) |
| K5, K6 device proof, iPad | §2 iPad table (D4); every flow in §4 is a device-script section |
| K7 dead ends | (a) S1 gate; (b) S2 role-built tabs and the "role without access" rule; (c) server pages — no blueprint part (programmer) |
| K8 purchase call to action | flow 4.1 billing-locked state has no prices or links; US storefront only (D5) |
| K9 domain | rule 5.6, N18 (D6) |
| K10 policy accuracy | no screen; N18 and Ofir's sign-off (D7). Scanit sends product names and barcodes — not personal data — to an AI service and to barcode databases; the policy's subprocessor list should name them |
| K11 privacy answers | N18: the staff phone number is new; Documents and new-hire uploads are not in the app for floor roles, but remain reachable by an admin inside Manage, so the answers must still cover them |
| K12 unrestricted web access | rule 5.8: web content only on our host, Manage admin-only; N11; the Scanit picture exception (N15d) is for app-review to judge |
| P1 | S11 update-required state |
| P2, P3 | rules 5.9, 5.2; N8c |
| P4–P8 | no blueprint part |
| SEC-1 | Q8; S12 and N13 (set-up must work for every role that is gated) |
| SEC-2 | flow 4.1 step 6; ordered after N13 (D3) |
| SEC-3 | flows 4.1, 4.2, 4.8: no two-step and no text message in the demo company only |
| SEC-4 | N17; flows 4.8 and 4.9 (Scanit's outside calls and the text-message transport are fenced for the demo company) |
| SEC-7 | S8 / flow 4.7 (password, two-step code, last-admin confirm, simulated in the sandbox) |
| SEC-8 | host has no Pack tab and no label lookup; flow 4.6 expects named fields, not the whole order row |
| SEC-10, SEC-18 | N5 native sign-out |
| SEC-11 | part of N13: limits per account on codes checked and texts sent |
| SEC-15, SEC-16 | N11, N6 |
| SEC-5, 6, 9, 12–14, 17, 19, 20 | server work with no screen in the app; no blueprint part |

### Not verified

- Nothing was run: no tests, no browser, no device. Every statement about Swift and about `app.py` is from reading. `app.py` and `templates.py` were not read whole.
- **Scanit:** read were the server routes (`app.py:15861-16354`), `_barcode_lookup_online` (`8528-8593`), and `tests/test_scanit_catalog.py` (not run). **Not read:** the desktop page's own HTML and script (`SCANIT_HTML`) — so which of the old endpoints it still calls, and exactly what the host sees today, is unknown. Not checked: how long a first scan of an unknown barcode really takes; whether the app's content policy lets a picture from an outside host load in `/m/`; what share of the real catalog already has notes and prices (i.e. how often a live scan triggers the paid lookup).
- **Two-step verification:** that no text-message code exists is taken from the security report's table and from the sign-in and 2FA routes read (`app.py:4876-5026`); the whole file was not searched. Not checked: whether an admin can reset another person's two-step today; whether hosts or workers can hold recovery codes; any provider's price, delivery time or registration wait (Q6 cites one documentation page only).
- **Who is gated** (Q8) and which roles count as "floor roles" for the badge after SEC-2 — in particular whether a host keeps a badge. The blueprint assumes a host signs in with a password.
- N4 (the gates blocking `/api/mobile/session`) and N8a (a failed upload deletes the video) are code readings; nobody has reproduced them.
- N10: whether a lookup can already return a playable packing-video link.
- What `/api/today` returns to a worker or a host, and whether floor roles should receive the show backlog — programmer and security-reviewer.
- Which roles count as "packing roles" after SEC-8 — the tab table assumes worker, cs, manager, admin.
- N16 reads "no per-company colour in the app" as covering the desktop pages inside Manage too; if Ofir meant the phone-built and native screens only, the programmer's part of N16 is dropped and nothing else changes.
- That two reviewer logins (worker, manager) satisfy Apple when admin and host accounts exist — app-review's call.
- That the "Update required" link opens the store page of an unlisted app.
- How the floor really uses Live Mode, Match Products, News and My Schedule on phones today.
- Whether workers know their passwords or sign in by badge only (affects the delete-account password step for floor accounts).
- HIG pages not fetched are listed at the top; Apple's own guideline text for 4.2, 5.1.1 and 2.1 was taken from app-review's report.
- The reading of "don't hide tab bar buttons" in §2 is this document's interpretation, not Apple's wording.

---

## Change log

- 2026-11-10 — first draft, for Ofir's approval.
- 2026-11-10 — **draft → approved.** Ofir approved the roadmap and this blueprint with his answers to D1–D8 and Q1–Q5. Changes made from those answers:
  - Status line; a table of the decisions at the top.
  - **Removed the two-branch text** for D1, D2, D3, D5, D6, D7, D8 and Q1–Q5. Only D4 (iPad) still has two branches.
  - **Scanit moved from 1.1 into 1.0** (Q4): host tab bar is now Today · Scanit · Account; cs / manager / admin reach the same screen from Today; new inventory row S13, flow 4.9, pieces N15 and N17, rule 5.12, and the list of what `scanit.md` must specify. Editing, name search, favourites and scripts stay out of 1.0.
  - **Text-message two-step verification added as a 1.0 prerequisite** (D3's condition): Sign-in gains method choice; new native set-up screen S12 and flow 4.2; pieces N13 and N14; rule 5.11; the phone number as new personal data (N18). The draft's one exception — the web enrolment page shown in a sheet — is gone; native set-up moved from 1.1 into 1.0.
  - **Reviewer logins are manager + worker** (D2): the "admin second login" variant is deleted; flow 4.8 rewritten so it shows Pick, Pack, Track, account deletion (worker) and Track with the packing video plus Scanit (manager), with no Manage tab and no desktop page; the demo seed gains a pre-packed order with video and three complete catalog products (N12).
  - **Packing video in Track is a requirement** (Q5), no longer first on the cut list; N10 raised accordingly.
  - **Indigo only** (D8): rule 5.9, piece N16; company colour removed from the session payload in N3.
  - **Unlisted, US only** (D5): consequences written into §6; phone-built Shows / Issues confirmed for 1.1.
  - **liveopshub.com and support@liveopshub.com** (D6, D7) written into S8, rule 5.6 and N18.
  - Flows renumbered: 4.2 is new (two-step set-up), the picker's shift is 4.3, pack 4.4, manager 4.5, label lookup 4.6, deletion 4.7, reviewer 4.8, and 4.9 is new (host with Scanit).
  - §7 replaced: Q1–Q5 are answered; three new questions Q6–Q8 (text-message service, who enters the phone number, who must use two-step).
  - §8 rewritten as an ordered work list for ios-designer, with `sign-in.md`, the design system's themes and the missing Scanit spec added.
  - **Not yet seen by Ofir:** S12, S13, flows 4.2 and 4.9, N13–N18, rules 5.11–5.12, and Q6–Q8.
