# App blueprint — Live Ops Hub (iPhone / iPad)

**Status: approved by Ofir 2026-11-10; rev 2 awaiting his read of the changed sections.** Written by app-planner. The approved version was written from `main` as checked out on `docs/roadmap-to-app-store`; rev 2 was written on `design/specs-to-blueprint`.

**Why rev 2.** After the approval Ofir changed one decision and answered three questions (2026-11-10, relayed by the lead session):

- The second sign-in step is **a code sent by email, not a text message.** Text messages are out of 1.0 entirely and no phone number is collected. The authenticator app stays because it exists.
- **Q8 accepted:** two-step verification is required for admin, manager and cs. **Q7 accepted in spirit:** the person enters their own address, and it counts only after they type a code sent to it. **Q6 is void** (there is no text-message service to choose).

**Sections changed in rev 2 — the ones Ofir has not read** (each is tagged **(rev 2)** where it appears): the decisions table (D3, Q6–Q8); §1 "Signs in with"; §2 "Opening `/m/` pages in a phone browser"; S1, S3, S5, S7, S8, S12; pieces N1, N3, N5–N10, N12–N14, N17, N18 and the new N19–N22; flows 4.1, 4.2, 4.4, 4.6, 4.7 and 4.8 step 10; rules 5.3, 5.11 and the new 5.13; §6; §7 (one new question, Q9); §8; §9. Everything else is the approved text.

The Scanit plan (S13, flow 4.9, N15, rule 5.12) was written after the approval from Ofir's Q4 answer. There is no record here that he has read it; it is unchanged in rev 2 and still tagged **new**.

This is the app planned as one product: who uses it, what each role sees, every screen and where it lives, the journeys across screens, and what ships in 1.0. Screen design belongs to ios-designer (`docs/mobile/screens/`); this document only says which screens exist and how they connect.

Inputs: `ROADMAP.md`, `BOARD.md`, `REVIEW-2026-11-10.md` (R1–R3, K1–K12, P1–P8), `docs/security/2026-11-10-mobile-baseline.md` (SEC-1…20), `DESIGN_SYSTEM.md`, the specs in `screens/` (for rev 2: `sign-in.md`, `scanit.md`, `today.md`, `track.md`, `me.md`, `cleanup.md` as ios-designer rewrote them, and `DESIGN_SYSTEM.md` §3), and the code (`mobile/`, `ios/README.md`, and in `app.py` the sign-in, two-step, user-management, mail, `/api/today`, lookup, upload and video routes). All code statements are from reading; nothing was run. This run had no search tool, so statements of the form "nothing in the code does X" cover the line ranges listed in §9, not the whole file.

How to read "state today": **exists** = in the repo and reachable in build 5 · **specified** = a spec exists, nothing built · **missing** = neither. None of it is proven on a device except "installs and opens" (`device-tests/PROVEN.md`).

### Ofir's decisions (2026-11-10) — the blueprint is built on these

| # | Decision | Where it lands |
|---|---|---|
| D1 | Yes: an isolated demo (sandbox) company without two-step verification for Apple's reviewer | flow 4.8, N12 |
| D2 | Reviewer logins are **manager + worker**. No admin demo account | §2, flow 4.8 |
| D3 **(rev 2)** | Badge sign-in only for floor roles, **on condition that the emailed code works first.** The second step is a code sent by email or the existing authenticator app; the person chooses. No text messages and no phone number in 1.0 | S1, S12, flows 4.1 and 4.2, N13–N14 |
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
| Q6 **(rev 2)** | Void — no text-message service is needed | — |
| Q7 **(rev 2)** | The person enters **their own email address** at set-up; it counts only after they type a code sent to it | S12, flow 4.2, N13 |
| Q8 **(rev 2)** | Two-step verification is **required for admin, manager and cs**. The emailed code is offered to all three, admin included | S1, S12, N13 |

Two working rules from the lead session, written into this document as rules because the code read does not contradict them (rule 5.11): there is **no self-service password reset by email** — an admin resets a forgotten password; and **the demo company never sends an email and never asks for a code**.

### Apple guidance used (read online 2026-11-10)

| Page | Change log (latest) | What this blueprint takes from it |
|---|---|---|
| HIG › Tab bars (`developer.apple.com/design/human-interface-guidelines/tab-bars`) | June 8, 2026 | Tab bars are for navigation between top-level sections, not actions. "Avoid overflow tabs" — a More tab "makes it harder for people to reach and notice content". "Don't disable or hide tab bar buttons, even when their content is unavailable." Badges are reserved "for critical information". On iPadOS the system shows the tab bar near the top; converting it to a sidebar is an option for more complex apps ("Prefer a tab bar for navigation"). |
| HIG › Sidebars (`…/sidebars`) | June 8, 2026 | "Consider using a tab bar first"; the sidebar-adaptable style is for exposing "more areas than fit in a tab bar". |
| HIG › Launching (`…/launching`) | June 10, 2024 | "Launch instantly"; "Restore the previous state when your app restarts"; launch in the device's current orientation when both are supported. |
| HIG › Layout (`…/layout`) | September 9, 2026 | "Determine layout based on size classes, not device type or orientation"; "Keep functionality the same as size classes change"; iPad windows are resizable. |

These four pages were read for the draft and were not fetched again for the approved version or for rev 2; rev 2 adds no statement about tab bars, navigation or iPad layout. Not fetched, so nothing is asserted from them: HIG Onboarding, Managing accounts, Notifications, Web views, Split views. The App Review guideline wording used below is quoted from app-review's report, not re-read.

**(rev 2)** Also read online 2026-11-10, for the packing-video format only (N10): the "WebM video format" table on caniuse.com (`caniuse.com/webm`). For Safari on iOS it lists partial support for versions 14 to 17.3 and full support from 17.4; it gives no reason for "partial". Apple's own documentation on what a web view plays was not found (one developer-forum thread on the question has no answer). The Twilio page cited in the approved version is no longer used.

---

## 1. People and jobs

The server has **five** roles: `worker`, `host`, `cs`, `manager`, `admin` (`app.py` `VALID_ROLES`). "Picker" is not a role any more — it was merged into `worker`. A picker and a packer are the same account type doing two jobs. `superadmin` (platform owner) is a sixth, internal account type.

| Who | Opens the app to | How often | Conditions | Signs in with **(rev 2)** | Done looks like |
|---|---|---|---|---|---|
| **Worker picking** (`worker`) | choose a show, scan a label, tick items off the table, finish or report a problem | all shift, hundreds of orders after each live | one hand, often gloves, phone or a shared iPad, Bluetooth scanner or camera, patchy Wi-Fi | badge scan, or username + password. No second step in 1.0 | "Order picked" and the next label scanned without looking for a button |
| **Worker packing** (`worker`) | scan a label, see the box contents, record the packing video, upload, next box | all shift | phone or iPad on a stand, Bluetooth/USB scanner, hands full | same | video saved to the order, order marked packed, next scan opens the next box |
| **Warehouse manager** (`manager`) | see where each show stands (to pick / to pack / issues), jump in to pick or pack, look up a label and its packing video | many times a day, walking the floor | phone in hand, interrupted | password + a code — emailed, or from an authenticator app. No badge | knows which show is behind and why, in under a minute, without a laptop |
| **Customer service** (`cs`) | answer "where is my order / an item was missing": find the label, see who picked and packed it, watch the packing video | per buyer claim | desk or phone, good network | password + a code (emailed or authenticator). No badge | status and video in front of them in seconds |
| **Host** (`host`) | **Scanit**: scan the product in her hand and read its name, retail price, our target price and its notes while selling | every product, for the length of a live | on air; phone or iPad on a stand beside her, glanced at from arm's length; one hand holds the product; camera or a Bluetooth scanner; the screen must stay awake | username + password. No second step in 1.0, no badge | the product's card is on screen a moment after the scan, and she never has to touch the phone between products |
| **Admin** (`admin`) | everything a manager does, plus the full console (users, settings, TikTok, shipments, inventory) when away from a computer | daily glance; occasional deep task | at home, phone | password + a code (emailed or authenticator). No badge | floor status at a glance; any console page reachable when really needed |
| **Reviewer — floor login** (demo `worker`) | follow the review notes: sign in, pick an order, pack a box from the sample-label PDF, look up a label, delete the account | once, ~10 minutes, has never seen a warehouse | no scanner, no second device, scans a PDF off a screen | username + password only (demo company: never a code, never an email) | every step in the notes works and no screen looks like a website |
| **Reviewer — second login** (demo `manager`) | see the other account type: the shows on Today, the packing video of the box just packed, a product lookup | a few minutes | same | username + password only (demo company) | sees a different Today, plays a video, never meets a desktop page |
| **Platform owner** (`superadmin`) | not an app user | — | — | — | told the console is on the web (§2) |

An account with several roles follows the strictest of them: if any of its roles is admin, manager or cs it signs in with a password and a code and has no badge.

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

### Opening `/m/` pages in a phone browser (rev 2)

The 1.0 product is the app. `/m/` pages opened in a phone browser are **not a second product**; rule 5.13 says exactly what they do there. Nothing on the server sends a browser to `/m/`, and the floor's browser stations are not touched.

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
| S1 **(rev 2)** | **Sign-in** | username + password; the **second step** with the method the account has — emailed code, authenticator code, or the person's choice when both are set up — and a recovery-code fallback; "Scan badge" (camera or scanner) for floor accounts; Privacy and Terms links. No "forgot password" (rule 5.11) | everyone | native | **missing** as a native screen; **specified** (`sign-in.md`, rewritten). Endpoints exist for password, authenticator code and badge: `POST /api/login`, `/api/login/2fa`, `/api/badge-login`. **Emailed codes do not exist on the server** (N13) | 1.0 |
| S2 | **Role-built tab bar** | the table in §2 | everyone | native | **missing** (three fixed tabs: Dashboard, Pick, Pack; launch tab is the desktop site) | 1.0 |
| S3 **(rev 2)** | **Today** | "what should I do now": my packed / picked today, Continue, Look up a label, floor now. Manager/admin: each open show with to-pick / to-pack / issue counts, overdue first. cs / manager / admin: a Scanit row. Admin: today's sales line. Host: greeting and one row that opens the Scanit tab — nothing about orders | all five roles | `/m/today` | page **specified** (`today.md`, rewritten), not built. Data **exists in part**: `GET /api/today` (`app.py:4572-4710`) answers every signed-in role with the floor numbers and the show backlog, and admins with money; it has **no per-show "to pack" or issue count**, drops a show once nothing is left to pick, and gives a host the same order numbers as everyone (N19). `/api/pick/my-stats`, `/api/me/stats` exist per the spec | 1.0 |
| S4 | **Pick** — queue, order checklist, report a problem, cancelled-order stop | pick a show's orders | worker, cs, manager (through the server's manager→admin rule), admin | `/m/pick` | **exists**; three links leave for desktop pages and must change (N7) | 1.0 |
| S5 **(rev 2)** | **Table cleanup** | pull cancelled items off the table, show by show; confirm a show's table is cleared so picking can start; Pick sends workers here when a show is blocked | worker, cs, manager, admin | `/m/cleanup` | page **specified** (`cleanup.md`), not built; today Pick jumps to the desktop `/admin/cleanup` (`mobile/static/pick.js:240-241, 316, 321`). Data **exists**: `/api/cleanup/shows`, `/api/cleanup/<show>`, `…/mark`, and — per ios-designer's reading, not re-read here — `POST /api/show/cleanout` for "Table cleared — start picking" | 1.0 |
| S6 | **Pack** — scan, contents, record, upload, next | pack with video proof | worker, cs, manager, admin (exact list is the programmer's SEC-8 fix; host is out) | native | **exists** (`Features/Pack/`); gaps in N8 | 1.0 |
| S7 **(rev 2)** | **Track** (label lookup) | scan or type a label → show, buyer, status, who picked and packed, last event; for cs / manager / admin also **the packing video, played in the app** (Q5) | worker, cs, manager, admin | `/m/track`, pushed from Today | page **specified** (`track.md`, rewritten), not built. Data **exists**: `GET /api/shipment/<code>`. It returns the whole order row and **no video field** (`app.py:6662-6725`); `/media/video/<file>` exists but needs a file name the page does not have (N10) | 1.0 |
| S8 **(rev 2)** | **Account** | name, role, company; language; **two-step verification** (opens S12; shown to accounts it applies to); Privacy, Terms, Support (support@liveopshub.com); sign out; delete account (own screen: what is deleted; the password — or, for a badge account, a scan of its own badge; a two-step code when enrolled; confirm; last admin gets the second "this deletes the company" confirm) | everyone | native | **missing**; **specified** (`me.md`, rewritten). Endpoint exists: `POST /api/account/delete` incl. `need_org_confirm`; it asks for no password today (SEC-7) | 1.0 |
| S9 | **Manage** | the desktop console, presented as what it is, under a native title | admin only | desktop pages inside the Manage tab | **exists** as today's Dashboard tab (shown to everyone, launch tab) | 1.0 |
| S10 | **Camera scan sheet** | camera + typing fallback for any scan asked by an `/m/` page | whoever is on that page | native | **exists** (`ScannerSheet`) | 1.0 |
| S11 | **System states**: offline / can't reach server; update required; session expired; subscription inactive; two-step set-up required (hands over to S12); account type not supported (`superadmin`) | never a blank or desktop page | everyone | native | offline + update required **exist**; the other four **missing** (today they surface as desktop redirects: `/`, `/billing`, `/me?setup2fa=1`) | 1.0 |
| S12 **(rev 2)** | **Two-step verification set-up** | choose a method — **email** or authenticator app. Email: the person types their own address, a code is sent to it, they type the code; only then does the address count. Authenticator: QR / key, confirm a code. Then the recovery codes, shown once. Later, from Account: add the other method, change the address, turn a method off, make new recovery codes — each after a current code | admin, manager, cs (required for all three); refused in the demo company; not offered to worker or host in 1.0 | native; reached from the "set-up required" state and from Account | **missing**; **specified** (`sign-in.md` §3). Authenticator endpoints exist (`/api/2fa/setup`, `/enable`, `/status`, `/recovery`, `/disable`, `app.py:4957-5026`) but answer only to admin, and to a manager through the manager→admin rule; **cs is refused today**. Nothing exists for email codes, and a staff account has no email address on it (N13) | 1.0 |
| S13 | **Scanit** (new) | scan a product barcode → its card: picture, name, retail price (MSRP) with where the price came from, our target price, and its notes (fragrance top / heart / base, or short selling points) with their source. **Read-only on the phone in 1.0** | host (tab); cs, manager, admin (from Today) | `/m/scanit` | page **missing**; **specified** (`scanit.md`). Data **exists**: `GET /api/scanit/scan?code=` and `GET /api/scanit/item?sku=` for admin, cs, host, manager (`app.py:16088-16123`); the desktop page `/scanit` exists | 1.0 |

### 3.2 Screens not in 1.0

| Screen | Roles | Lives when built | State today | Release | Why it waits |
|---|---|---|---|---|---|
| News (announcements, with "Got it") | all | `/m/` | specified; desktop page exists | **1.1 — first** (Q3) | managers' channel to the floor; needs a badge rule |
| My Schedule | all | `/m/` | specified | **1.1 — second** (Q3) | read-only, small |
| Shows (manager) and Issues queue | manager, cs, admin | `/m/` | not specified; desktop pages exist | 1.1 | the manager's next need after Today. app-review asked for it before a *public* listing only; D5 is unlisted, so it stays here |
| Scanit — fixing a product (name, price, notes), forcing a new lookup | cs, manager, admin | `/m/` | endpoints exist (`POST /api/scanit/item`, `/api/scanit/item/lookup`); not specified | 1.1 | done at a desk today; the forced lookup is a paid call |
| Scanit — search by product name, saved favourites, a scan history that survives closing the app, AI-drafted selling scripts | host, cs, admin | `/m/` | endpoints exist only on the **old** Scanit table (`scanit_products`), not on the catalog the scan screen now reads; whether the desktop page still uses them was not checked | later | needs server work first; none is needed to sell a product on air |
| Leaderboard | all | `/m/` | specified | 1.1 | motivation, not work |
| My numbers / achievements / recent packages (the top of the old `me.md`) | all | `/m/` or native | specified | 1.1 | Account in 1.0 is account only |
| Optional two-step verification for roles that are not required to use it | worker, host | native (S12) | missing | 1.1 | 1.0 offers S12 to the accounts that must use it |
| "Forgot password" by email; text-message codes | — | — | missing | **not planned** | rule 5.11: the mailbox that receives the code must not also be able to reset the password; Ofir took text messages out |
| Onboarding checklist | new hires | `/m/` | specified | later | |
| Documents | all | `/m/` | specified | later | includes signing and ID documents; keeping it out of the app keeps the privacy answers simpler (K11) |
| Guides | all | `/m/` | specified | later | |
| Live Mode, Match Products | worker, cs, admin | `/m/` | specified | later | real floor work, but two long scanning flows; how often they are done on a phone is not known |
| Push notifications, widgets, offline picking queue | — | native | missing | later | app-review: none is needed for 4.2 |
| **More tab, `/api/mobile/nav`, `/more` web page, native Appearance/theme picker, global search field, a company-colour setting in the app** | — | — | withdrawn from the specs | **not in the app** | replaced by §2 and D8 |
| Welcome chooser (`/welcome`), badge page (`/badge-login`), desktop `/login`, `/me`, `/home`, `/billing`, `/scanit`, the web two-step enrolment on `/me` | — | — | exist on the web | **not in the app** (reachable only by an admin browsing inside Manage) | replaced by S1, S3, S8, S11, S12, S13 |
| iPad web packing station (`/`, `WORKER_HTML`) | worker | browser | exists | **not in the app** | the floor's browser stations are untouched |
| Platform console (`/admin/organizations`) | superadmin | browser | exists | **not in the app** | |

### 3.3 Pieces 1.0 needs that do not exist today

Each becomes its own board entry. N1–N18 keep their numbers (the board refers to them); N19–N22 are new in rev 2. §3.4 groups the same list by owner.

| # | Piece | Needed by | Owner |
|---|---|---|---|
| N1 **(rev 2)** | Native sign-in gate in front of all tabs (S1): password, the second step with method choice, "Send code" / "Send again" with its wait for the emailed code, recovery code, badge scan, legal links, error and throttle messages | every flow | ios-engineer, from `sign-in.md` |
| N2 | Tab bar built from the session (S2), rebuilt when the session's capabilities change (role changed on the server, sign-out, another user signs in) | every flow | ios-engineer |
| N3 **(rev 2)** | **`/api/mobile/session` tells the app what this account may open** — `can: {pick, pack, track, scanit, manage}` computed by the same check the routes use. Today it returns only `roles` (`app.py:4852-4874`); the app cannot derive from `["manager"]` that a manager may pick or use Scanit, because that comes from the server's manager→admin rule (`req_role`). Roles stay enforced on the server; this field only decides which tabs and Today rows are drawn. Also in the same answer: `must_setup_2fa`; the two-step state of the account (required or not, which methods are on, the email address **masked**); whether the account has a badge (for the delete screen, N21); a billing-locked flag; a `sandbox` flag (for the "Demo company" banner, security requirement 10). The support address is fixed by D7 and does not come from the server. | S2, S3, S8, S11, S12 | programmer (shared-logic PR) → security-reviewer |
| N4 | `/api/mobile/session` must answer while the two-step set-up gate or the billing gate is active. Today both gates stop it (it is in neither `_2FA_SETUP_OPEN` nor `_BILLING_OPEN_PATHS`, `app.py:3893-3929`), so the app would get 403 / 402 instead of a session. By code reading — not run. | S11, S12 | programmer |
| N5 **(rev 2)** | Native Account (S8) incl. the delete-account screen — password or own-badge scan (N21), two-step code when enrolled incl. "Email me a code", the last-admin confirm — and sign-out that ends the session on the server and clears both cookie stores | flows 4.1, 4.7 | ios-engineer; programmer for SEC-7 / SEC-10. Only `GET /logout` (a redirect) exists; whether a JSON sign-out is needed is the engineers' call |
| N6 **(rev 2)** | Bridge additions. **(a) `LOHubNative.openTab(id, path)`** — `id` is a tab id (`today`, `pick`, `pack`, `scanit`, `manage`, `account`); `path` is optional and lets the page say where inside a **web** tab to land (`openTab('pick', '/m/pick?order=…')`). The shell accepts a path only when it is on our host and begins with that tab's own root (`/m/today`, `/m/pick`, `/m/scanit`); any other path is dropped and the tab opens as it was. No path is ever accepted for `manage` (an `/m/` page must not steer the admin console), `pack` (that is `pack(code)`, which exists) or `account`. A tab this account does not have: nothing happens and the call says so, so the page can tell the person. The page that opens applies its own rules — a path is a request, never a permission. Only a tap calls it (rule 5.1). **(b)** a "session ended" signal from `/m/` pages to the shell (today `mobile.js` sends a signed-out page to `/` and a billing-locked page to `/billing`, both desktop pages). **(c)** keep the screen awake while Scanit is in front | flows 4.3–4.6, 4.9 | ios-engineer + mobile-engineer; security-reviewer (bridge) |
| N7 **(rev 2)** | `/m/pick` clean-up: cleanup gates → `/m/cleanup`; avatar → Account tab instead of desktop `/me`; the browser-only web tab bar in `pick.html` still lists Track and More; when Pick is opened with an order in the path while another order is open and unfinished, it keeps the open one and says "Finish this order first" | flows 4.3, 4.6 | mobile-engineer |
| N8 **(rev 2)** | Pack gaps: (a) a failed upload **deletes the recording** and the packer must film the box again (`PackFlowView.swift` `stopAndUpload`; the security report states the same) — keep the file and retry, under the waiting rule in flow 4.4; (b) session-expired handled by the gate instead of "Open the Dashboard tab and sign in" (K7a); (c) Spanish strings (P3); (d) **the server must accept the same recording twice without counting it twice** — today each accepted upload writes a new video file and a new row in the packing log (`app.py:5118-5147`), and "packed today" counts those rows, so a retry after a lost answer would inflate the numbers; the app sends an id per recording and the server answers a repeat with success and nothing else | flow 4.4 | ios-engineer (a–c, and sending the id); programmer (d, shared-logic PR → qa) |
| N9 **(rev 2)** | `/m/today`, `/m/track`, `/m/cleanup` and `/m/scanit` pages, each with its browser check. `/m/cleanup` uses the existing `POST /api/show/cleanout`; the programmer confirms its role list and that calling it twice is harmless before the page ships | flows 4.3, 4.5, 4.6, 4.9 | mobile-engineer (roadmap M5) |
| N10 **(rev 2)** | **Packing video for a lookup** — a 1.0 requirement (Q5) that the server cannot serve today: the lookup answer has no video field. Needed: one read-only answer for cs / manager / admin, per order — is there a video; a link **on our host** to play it; its format (`mp4` or `webm`); when it was recorded and how long it is. A worker and a host receive nothing about it. Facts from reading: `/media/video/<file>` is allowed for admin and cs, and a manager through the server rule (`app.py:14300-14318`); with storage on, it answers with a redirect to a link on the storage host that lasts 15 minutes; the page policy allows video from other https hosts (`media-src`, `app.py:4022`); the iPhone app's recordings are stored as `.mp4`, browser-station recordings as `.webm` (`app.py:5106-5110`). **What Track must handle:** follow the redirect; ask for a fresh link when one has expired; play `.mp4`; **try** `.webm` and, when the phone refuses it, show "This video can't be played on this phone" instead of a dead player. Most of the real warehouse's videos are browser-station `.webm`, and the app supports iOS 17.0 upward while the table read online lists full WebM support only from 17.4 — so a real station recording must be played on the oldest supported iOS and on a current one **before** the screen is called done (mobile-qa with device-test-lead). If it fails there, raising the minimum iOS or converting on the server is a new decision for Ofir; it is not assumed here | flow 4.6 | programmer (answer), security-reviewer; mobile-engineer (page); mobile-qa (format proof) |
| N11 | Manage wrapper (S9): admin-only, native title, exact-host rules (SEC-15), bridge closed to sub-frames (SEC-16) | admin | ios-engineer |
| N12 **(rev 2)** | Demo company (D1), the two logins **manager + worker** (D2), and the sample PDF. The seed must contain, besides orders to pick and pack: **one order already packed with a packing video in `.mp4`** (so the manager can show a video even if the reviewer's own recording failed, and no format question arises in review), and **three catalog products with a picture, a typed retail price and notes**, one of whose barcodes is printed on the PDF. Both demo logins have a password, no badge, no email address and no two-step method | flow 4.8 | programmer (roadmap M3); security-reviewer; app-review |
| N13 **(rev 2)** | **Emailed sign-in codes on the server** — nothing exists. A staff record today holds password, role, name, company, and optionally extra roles, a badge, authenticator fields and recovery codes (`api_add` `app.py:12622-12656`, the two-step routes `4957-5026`); **no email address.** Needed: **(1)** an email address on the staff record, with a confirmed flag; an unconfirmed address is never used. **(2)** A confirm-address flow at set-up: send a code to the typed address, check it, then store the address. **(3)** At sign-in: the password answer lists the account's methods with the address masked; "send code" and "check code"; a different answer for an expired code than for a wrong one; wait lengths and remaining sends in the answers so the app can show them; the step does not expire while a sent code is still valid. **(4)** Codes: random, short-lived, single use, a new one cancels the old one, stored hashed **where every gunicorn worker can read them** (the shared database or the staff file under its lock, as the throttles already do — not process memory), never written to a log (note: on staging `_send_email` prints the recipient and subject, so the code must not be in the subject). **(5)** Limits on sending — per account, per address and per network — and on checking (SEC-11 becomes part of this). **(6)** Sent through the existing mail function `_send_email` (`app.py:1123-1147`: Resend, then the Google script, then SMTP, each waiting up to 20–25 s, one after another inside the request); a sign-in request must not hold a worker that long, so the programmer sets a short limit for code mail. When no mail service is configured the email method is not offered at all. **(7)** Behind the sandbox fence (N17). **(8)** The same recovery codes as the authenticator; turning a method off, changing the address and making new recovery codes need a current code from **either** method (today those routes accept only an authenticator code); turning the email method off deletes the address; an account that must use two-step cannot turn off its last method. **(9)** Who is gated: any account whose roles include admin, manager or cs (`_twofa_required` looks at the main role and at admin only today — SEC-1); the set-up routes must answer for all three (**cs is refused today**). **(10)** Every send, confirm, change and reset in the audit log, without the code. **(11)** The address is used for sign-in codes and nothing else. | S1, S12, flows 4.1, 4.2, 4.7 | programmer (shared-logic PRs) → qa → security-reviewer. **Must be live and proven with a real inbox before SEC-2 (badge sign-in for floor roles only) is merged** — that is D3's condition |
| N14 **(rev 2)** | Native two-step set-up (S12) and the two-step row in Account, from `sign-in.md` §3 | flow 4.2 | ios-engineer |
| N15 | Scanit for the phone: `/m/scanit` route with the same four roles as the desktop page (mobile-engineer wiring in `mobile/__init__.py`); no new data endpoint for the read-only screen. For the programmer and security-reviewer to settle before it ships: (a) SEC-4 for Scanit, below; (b) `GET /api/scanit/scan` **writes** — it can add a product to the catalog, records the scan, and can start a paid lookup — and, being a GET, it is outside the CSRF check; (c) a first scan of an unknown barcode asks up to four outside databases one after another inside the request (`_barcode_lookup_online`, 6 s limit each, by reading), so the screen needs a waiting state and the server a total time limit shorter than the 30 s the spec waits; (d) product pictures found by those databases are links to other companies' hosts, loaded by the phone itself — either store them on our side or confirm the app's content policy and privacy answers allow it. | flow 4.9 | mobile-engineer; programmer; security-reviewer |
| N16 | Indigo only (D8): native tint is the LiveOpsHub indigo; `/m/` pages stop emitting the company's colour (today `mobile/__init__.py` `_brand_css()` injects it); read literally, the desktop pages inside Manage also show indigo when opened by the app (`_brand_style()` in `templates.py` — a shared-logic change that must leave browsers untouched). Company **name** stays everywhere. | rule 5.9 | mobile-engineer (`/m/`), ios-engineer (native), programmer (Manage, own PR) |
| N17 **(rev 2)** | SEC-4 fence additions. **Email codes:** a demo-company account is never sent a code and never asked for one. At sign-in there is no signed-in session yet when a code would be sent, so the fence is decided from the company on the staff record, not from the session. **Scanit:** the barcode databases, the AI lookup and the old AI script route; the AI lookup runs in a background thread that has no session (`_scanit_lookup_info(org, sku)`), so the same applies. The only switch in the mail function today is the whole-server staging one (`app.py:1126`). | flows 4.1, 4.8, 4.9 | programmer → security-reviewer |
| N18 **(rev 2)** | Public pages and privacy answers: Privacy, Terms and Support on liveopshub.com (D6) with support@liveopshub.com (D7). **Staff email address:** collected from admins, managers and cs for sign-in codes. This is not a new data type for the app's declarations — the privacy manifest already declares Email Address (app-review K11; the security report's table) — but the App Privacy table in `ios/APP_STORE.md` does not list it and must; the policy's "account data: name, email" becomes true for these accounts and should say what the address is used for; the mail service that carries the code, and the barcode databases, belong in the subprocessor list (the security report already lists the mail service as missing). Account deletion removes the address with the account. **No phone number** is collected for staff. | rule 5.6, flow 4.7 | release-manager (answers, listing), ios-engineer (manifest stays as is — to confirm), programmer (pages), Ofir (policy wording) |
| N19 **(rev 2, new)** | **`/api/today` for the phone** (`app.py:4572-4710`). (1) A new list `open_shows`, sent only to accounts whose roles include manager, cs or admin: every show that still has an order to pick **or to pack**, with `pending`, `to_pack`, `issues`, `packed`, `total`, `overdue`, date, in today's order (most overdue first). The query already counts picked-not-packed per show and drops it; issues per show are counted the way `/m/api/pick/extras` does. The existing `backlog` object is left exactly as it is, because the desktop Today reads it. (2) **A host is answered with her name and role only** — no floor numbers, no shows, no issues (rule 5.7; same reasoning as SEC-8). The programmer first checks what the desktop `/home` draws for a host (not read here). (3) A worker keeps what the worker Today draws — own numbers, orders to pick, waiting to pack, tables to clear — and is not sent `open_shows`. The fields a worker's screen never draws (show backlog, company issue count, the 7-day series) are not new to a worker — Pick already lists the shows — so trimming them is security-reviewer's call inside SEC-8, not a 1.0 blocker. | flows 4.3, 4.5 | programmer (shared-logic PR → qa) → security-reviewer |
| N20 **(rev 2, new)** | **An admin can reset another person's two-step verification.** The user-management routes read (`app.py:12622-12741`: add, roles, name, delete, password, badge) contain no such action, and `sign-in.md` tells a locked-out person to "ask your admin to reset two-step verification". Needed: a true-admin action on a user of the same company that clears that user's methods, address and recovery codes, so the user meets "set-up required" at the next sign-in; it asks for the admin's own current code and is written to the audit log; refused in the demo company. It needs a button on the desktop Users page | flows 4.1, 4.2 | programmer (endpoint) → security-reviewer; product-engineer (the Users page — a desktop request through the board) |
| N21 **(rev 2, new)** | **Account deletion for a floor worker who signs in by badge.** Every account is created with a password (`api_add` refuses an empty one), but it is typed by the admin and a badge worker may never have known it. Deletion re-checks **the credential the account signs in with**: the password, or — only for an account that has a badge, and after SEC-2 only floor accounts do — a fresh scan of **its own** badge. `POST /api/account/delete` accepts either; a badge that belongs to someone else is refused and counted as a failed try. This changes the SEC-7 fix, so security-reviewer confirms it. | flow 4.7 | programmer (with SEC-7) → security-reviewer; ios-engineer (the screen, in N5) |
| N22 **(rev 2, new)** | **Browser fallback in the shared mobile layer** (rule 5.13): the web tab bar lists only this account's `/m/` roots; with no bridge the nav-bar avatar opens a small sheet with the person's name and **Sign out** (to `/logout`); rows that need the app are not drawn | rule 5.13 | mobile-engineer |

### 3.4 The same list by owner (rev 2)

| Owner | Pieces |
|---|---|
| **programmer** (each a shared-logic PR → qa → security-reviewer where marked) | N3, N4 session answer · N13 emailed codes, wider two-step gate, set-up routes for manager and cs · N17 fence for code mail and Scanit · N19 `/api/today` · N10 video answer for a lookup · N8d repeat-safe upload · N21 deletion by password or own badge (with SEC-7) · N20 admin reset of two-step · N12 demo company · N15 a–d Scanit points · N16 indigo inside Manage · N18 pages · confirm `POST /api/show/cleanout` (N9) · SEC-10 sign-out |
| **ios-engineer** | N1 sign-in gate · N2 tab bar · N14 two-step set-up · N5 Account, delete screen, sign-out · N6 `openTab(id, path)`, session-ended, keep-awake · N8 a–c Pack and the waiting-video rule · N11 Manage wrapper · N16 native tint · S11 system states |
| **mobile-engineer** | N9 `/m/today`, `/m/track` (incl. the video and both formats), `/m/cleanup`, `/m/scanit` · N7 `/m/pick` clean-up and order-in-path · N6 page side of the bridge · N22 browser fallback · N16 no company colour on `/m/` |
| **product-engineer** (desktop, through the board) | N20 the reset button on the Users page |
| **release-manager / Ofir** | N18 answers, listing, policy wording · Q9 sender address |

---

## 4. Flows

Same four failure cases for every flow, answered once here and only repeated where a flow differs:

- **No network:** `/m/` screens show the offline banner and keep what is on screen; actions that need the server say so and can be retried; nothing is queued in 1.0 except what §4.4 says about the packing video. Native screens show the existing "Can't reach LiveOpsHub — Try again".
- **Session expired** (7-day cookie, role removed, user deleted): the shell returns to Sign-in with one line, "You were signed out. Sign in again." After sign-in the person lands on Today, not mid-order.
- **Role without access:** the tab or row is not there. If a stale tab or link is used anyway the server refuses (403) and the screen says "Your account can't open this. Ask your manager." — never the plain text "Access denied".
- **Wrong scan:** the screen says what the code was and what it expected, with one way forward. A scan is never silently dropped.

### 4.1 Sign-in (rev 2)

1. App opens → Sign-in (no tab bar, no camera prompt).
2. Username + password → `POST /api/login`.
3. **The second step**, for an account that has two-step verification on (admin, manager, cs). The server's answer says which methods the account has:
   - email only → "We'll email a code to m•••@n•••.com" → **Send code** → type the code; "Send again" after a wait;
   - authenticator only → type the 6-digit code;
   - both → the person picks; the method used last on this device is offered first. Choosing "Email" sends nothing until "Send code" is tapped;
   - always available: "Use a recovery code".
   Wrong code: stays on the step and says so. Expired code: says so and offers a new one. Too many tries, or too many emails requested: "Try again shortly" (429). The step itself expires (five minutes after the password today; it must not expire under a code that is still valid — N13) → back to the password form with "Sign in again".
4. **No email address on the account** (it set up the authenticator only): the email option is not shown; one line says "Email codes aren't set up for this account. You can add your email in Account after signing in." The app never asks for an address before the person is signed in.
5. **The email does not arrive:** "It can take a minute. Check your spam or junk folder", then "Send again" (limited), then the authenticator if the account has it, then a recovery code, then "Ask your admin to reset two-step verification" — which needs N20; it does not exist today.
6. **Floor accounts** may instead tap "Scan badge" → camera or Bluetooth scanner → `POST /api/badge-login`. Once SEC-2 is in, a badge that belongs to an account with an admin, manager or cs role is answered with "This account signs in with a password" and the password form; nothing is filled in from the badge. SEC-2 is merged only after the emailed code has been proven with a real inbox (D3).
7. Shell reads `/api/mobile/session`, builds the tabs (§2), opens Today.
8. Variants: two-step set-up required → flow 4.2; organisation suspended or billing-locked → "Your company's subscription is not active. Ask your admin." with Account still reachable for sign-out and deletion, no prices and no link to buy (K8); `superadmin` → "console is on the web"; app too old → Update required.
- **Forgotten password:** there is no "forgot password" in the app and no reset by email (rule 5.11). The wrong-password message says to ask an admin, who sets a new one on the web (`POST /api/users/pw` exists, true admins only).
- No network: the form stays, "Can't reach LiveOpsHub", retry; a code is not counted as used. Privacy and Terms open in an in-app browser sheet from this screen (K1).
- Demo company: no second step at all, and **no email is ever sent** for a demo-company account, whatever is requested (N17).

### 4.2 Setting up two-step verification (rev 2)

Starts in one of two places: the "set-up required" state straight after the password (an admin, manager or cs account with no method yet), or Account → Two-step verification.

1. Choose: **Email** or **Authenticator app**. One sentence each on what it needs.
2. Email: the person types **their own address** → a code is sent to it → they type the code → on. The address is stored only after its code was confirmed; a typed-but-unconfirmed address is never used for a sign-in code. Nobody else can put an address on an account in 1.0 — not an admin, not an import.
3. Authenticator: the key as a QR code and as text (and a button that opens the authenticator app on the same phone) → type a code from the app → on.
4. Recovery codes are shown once, with Copy; the person confirms they kept them.
5. From Account later: add the other method, change the address (the new one is confirmed by its own code), turn a method off, make new recovery codes — each asks for a current code first, from either method. Turning the email method off deletes the address. An account that must use two-step cannot turn off its last method.
- Until set-up is finished the account can do nothing else except open Account, sign out and delete the account (the server's gate already works this way).
- Wrong or expired code: stays on the step. Address not valid, or the email could not be sent: says so, offers "Change email" and the authenticator.
- No network: nothing is saved; says so.
- **The day the requirement widens** (N13 live): every manager and cs meets "Protect your account" at their next sign-in and needs about a minute and an inbox they can open on that phone. People already signed in keep their session until it ends unless the programmer and security-reviewer decide to end sessions that day. Tell the managers and cs the date beforehand.
- Demo company: the row in Account reads "Not available in the demo company"; nothing can be changed and nothing here can send an email (security requirement 6).
- Worker and host: no two-step row in Account in 1.0.
- With this flow, **no desktop page is shown anywhere outside Manage.**

### 4.3 A picker's shift

1. Today → "Continue: keep picking {show}" or the Pick tab.
2. Pick queue → tap a show (or scan a label straight away — the scan finds its show).
3. If the show's table must be cleared first, Pick opens **Cleanup** for that show (`/m/cleanup`), the worker marks each cancelled item pulled, "Table cleared — start picking", back to Pick. (Today this step is a desktop page.)
4. Scan a packing label (Bluetooth scanner with nothing tapped, camera button, or typing) → order checklist.
5. Tick each item → "Done — scan next" → next scan. "Report a problem" → reason → the order goes to Issues, the picker continues.
- Wrong scan: label from another show → "It belongs to {other show}" with Switch / Cancel; unknown code → "No order for {code}" + Type it instead; cancelled order → full-screen "Don't pick this order".
- No network mid-order: ticks already sent stay; a tick that fails says so and is not shown as done (the server is the record — warehouse progress is never invented on the phone).
- Session expired mid-order: Sign-in → Today → Continue brings the show back; ticks already saved are still ticked.
- Host or any account without `can.pick`: no Pick tab.

### 4.4 Scan → pack → next box (rev 2: the waiting-video rule)

1. Pack tab → scan the shipping label (scanner, camera, typing).
2. Contents card (combined packages and giveaways included) → recording starts (auto-record on by default).
3. Scan again or tap Stop → upload → "Packed" → next label. If the second scan was the next box's label, that box opens.
- Wrong scan: unknown → "Shipment not found", stays on scan; cancelled → "This order is cancelled — don't ship it"; a scan while a box is open but not recording is ignored today — it should say so (N8).
- No network at step 1: cannot look up; says so.
- **Upload fails at step 3 — today the video is lost and the box must be filmed again (N8a). The 1.0 rule for videos waiting to upload:**
  1. The recording is **kept on the device** and the box shows "Video saved on this phone — uploading when connected", not "Packed". The order becomes packed only when the server has accepted the video, so stock is still deducted exactly once.
  2. The packer **may go on to the next box**; Pack shows how many videos are waiting.
  3. **At most 10 videos wait on one device.** At 10, Pack does not open another box and says "10 videos are waiting to upload. Connect to Wi-Fi to continue." (At roughly 3.5 MB a video — the server's own estimate — that is a small amount of storage; the limit is there so a dead network is noticed within ten boxes, not at the end of a shift.)
  4. Retries are automatic — when the connection returns, when the app comes to the front, after sign-in — oldest first. No button is needed; one is offered.
  5. A waiting video **belongs to the account that recorded it** and is uploaded only while that account is signed in, so "packed by" is never someone else's name. Signing out with videos waiting asks first ("3 videos haven't uploaded yet. Sign out anyway?"); they stay on the device and go up when that person signs in on it again.
  6. A video is deleted from the device only after the server accepted it. One the server refuses for a reason a retry cannot fix stops retrying, stays on the device, and Pack says "This video couldn't be saved. Tell your manager."
  7. The server must treat a repeated upload of the same recording as one (N8d).
  The numbers in 3 are this plan's starting values, to be checked on the floor in the device round.
- Session expired: Sign-in, then back on Pack; kept recordings are uploaded after sign-in.
- Camera or microphone refused: typing and a hardware scanner still work for the label; without the camera there is no video — say what to switch on in Settings. Microphone is optional.
- Signed out: cannot happen — the gate is in front (K7a).

### 4.5 A manager checking a show

1. Today (manager sections): open shows, most overdue first, each with to-pick / to-pack / issue counts (N19); floor now (pickers and packers online, picked and packed today); open-issues count.
2. Needs to act → Pick tab (same show list) or Pack tab; needs one order → Look up a label (4.6).
3. Needs the Shows or Issues desktop pages → not in the app in 1.0 (Q1); the phone's browser still opens them; in 1.1 they are `/m/` screens.
- In 1.0 the manager's Today is read-only: there is no close-show, re-import or issue-resolve action in the app, so no money or irreversible action is reachable from a manager's phone.
- No network: last numbers stay with "may be out of date".

### 4.6 Looking up a label for a buyer's claim (rev 2: the video and "Open in Pick")

1. Today → "Look up a label", or scan while on Today → Track.
2. Scan or type the tracking / order number → result: status, show, buyer, items, picked by, packed by, last event.
3. cs / manager / admin: **"Packing video" plays in the app** (Q5), whichever of the two formats it was recorded in (N10). No video yet (order not packed, or the upload has not arrived): the row says so instead of showing a dead player. A recording this phone cannot play: "This video can't be played on this phone." Workers get nothing about the video (server rule: playback is admin, cs, manager).
4. From the result: status *pending* → **"Open in Pick" opens the Pick tab on that order** — `openTab('pick', '/m/pick?order=…')`, N6 — without a second scan; Pick still applies its own gates (table not cleared, already picked, cancelled, another order open). Status *picked* → "Pack this order" (opens the Pack tab on that label, `pack(code)`).
- Wrong scan: "No order found for {code}". A product barcode scanned here gets the same answer; it is not passed on to Scanit.
- No network: "Lookups need a connection". A video that stops mid-play offers "Try again"; the link is short-lived (15 minutes on the server), so a retry asks for a fresh one.
- Host: no entry on Today; the server-side hole (a host can read any order through `/api/shipment`) is SEC-8 and is closed on the server, not by hiding the entry.
- Buyer address: the result shows the buyer's name and items, not the address — the programmer's SEC-8 fix (named fields instead of the whole row) decides what the app receives.

### 4.7 Account deletion (rev 2: the confirming step)

1. Account tab → Delete account → a screen that says what is deleted and what the company keeps. That wording mirrors the privacy policy and waits for Ofir's sign-off (D7).
2. **Confirm it is you, with the credential this account signs in with:**
   - an account with a password the person knows → the password;
   - a floor account that signs in by badge → "Scan your badge" — the account's own badge, scanned again now (N21). The password field stays available for a worker who has one;
   - an account with two-step verification → also a code: from the authenticator, or "Email me a code" (SEC-7).
3. Last admin of a company: a second confirm that names the company — "This also deletes {company} and all its data" → `wipe_org`.
4. Success → signed out → Sign-in, with one line confirming the deletion. The email address goes with the account.
- Reachable when the company is billing-locked and during two-step set-up (the server already allows it).
- Demo company: the server answers success, signs out, and the account still exists (security requirement 7); the app does nothing special. Both demo logins have a password and no code. Because they are a worker and a manager, **no reviewer account is ever the last admin**, so the "this deletes the company" confirm cannot be reached from a demo login (K3).
- No network: nothing is deleted; says so.
- Never reachable by accident: destructive style, its own screen, a credential. Answers K2, K3.

### 4.8 The reviewer's ten minutes (D1, D2)

The notes give two logins — a worker and a manager — and a PDF with sample shipping labels and one product barcode. Neither login meets two-step verification, an emailed code, the Manage tab or a desktop page.

1. Sign in with the **worker login**.
2. Today: a "Demo company" banner, numbers, Continue.
3. **Pick:** Pick tab → the demo show → scan a label from the PDF with the camera (or type the number from the notes) → tick items → Done.
4. **Pack:** Pack tab → scan the same label → contents → recording → Stop → "Packed".
5. **Track:** Today → Look up a label → the same number → status now *packed*, who packed it. (A worker sees no video.)
6. **Account deletion:** Account → Privacy, Terms, Support → Delete account → password → signed out. The notes say to test deletion with this login; it is restored (K3).
7. Sign in with the **manager login**. Today now shows the shows and their counts; the tabs are the same four.
8. **Track with video:** Look up a label → the label packed in step 4 → the packing video the reviewer just recorded plays. The notes also name the label of the order that was seeded already packed, in case the reviewer's own upload failed.
9. **Scanit:** Today → Scanit → scan the product barcode on the PDF → the product card.
10. **(rev 2)** The notes say, in one sentence each: company admins also have a Manage tab that opens the web console; hosts get Scanit as their own tab; real accounts with management roles sign in with a second step — a code sent to their own email address, or an authenticator app — which is switched off in the demo company only, so no code and no inbox is needed for review.
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

1. **Scanning is the same everywhere.** Three inputs on every scan screen: Bluetooth/USB scanner in keyboard mode with nothing tapped, the camera, typing. What a scan *means* depends only on where you are: on Pick → open that order to pick; on Pack → open that box / stop and save; on Today or Track → look that label up; on Scanit → show that product; on Sign-in → badge; on the delete-account screen of a badge account → confirm with that badge. A scan never buys a label, ships, cancels or changes stock, and never switches tabs by itself. One thing a scan can do that costs a little: the first Scanit scan of a product may start the one-time lookup (§4.9).
2. **Language.** English and Spanish for everything a floor role sees: Sign-in, two-step set-up, Today, Pick, Cleanup, Pack, Track, Scanit, Account, system states. Chosen once in Account (default: the device language), applied to native and `/m/` screens together. Product names and notes on Scanit are shown as stored (English). Manage is whatever the desktop is. The code email carries both languages in one short message. Today Pack and all native text are English only (P3).
3. **Offline and retry (rev 2).** No screen goes blank or falls back to a web error. Reads show the last data with "may be out of date"; writes fail visibly and can be retried; nothing is queued on the phone except packing videos waiting to upload, under the rule in flow 4.4: at most 10 per device, each tied to the account that recorded it, retried automatically, never deleted before the server accepted it, and an order is packed only when the server says so.
4. **The server is the record.** The app shows picked / packed only after the server said so. No tab, button or hidden entry is a permission: every role rule is enforced on the server.
5. **Badges and notifications.** 1.0 has no push notifications and no tab badges. When News arrives in 1.1 it gets the first badge; HIG reserves badges for critical information.
6. **Sign-out, help and legal are always in the same place:** the Account tab — Support (support@liveopshub.com), Privacy, Terms, Sign out, Delete account. Privacy and Terms are also on Sign-in. Legal and support pages are on liveopshub.com and open in an in-app browser sheet.
7. **What a worker can never reach from the app:** the Manage tab or any desktop page; label buying, shipping, cancels, stock adjustments; users, roles, settings, billing, TikTok connection; packing videos; Scanit and our target prices; another company's anything. Same for the demo floor login. A manager and cs additionally cannot reach Manage. A host reaches Scanit and Account, and nothing about orders — not on a screen and not in what the server sends her (N19).
8. **Web content stays in two boxes.** `/m/` pages (our host, phone-built, bridge enabled on the main frame only) and Manage (admin, desktop pages). No `/m/` screen links to a desktop page; mobile-qa should fail a screen that does. Known exceptions to "our host only": a product picture on Scanit that an outside database supplied (N15d), and a packing video, which the server hands to the storage host by a short-lived link (N10).
9. **Appearance.** One look across native and `/m/` screens (P2): 1.0 follows the system light/dark setting, with no in-app theme picker. **The colour is always LiveOpsHub indigo** (D8) — native tint, `/m/` screens and, read literally, Manage; a company's own colour never appears in the app, its name does.
10. **One sign-in, one session.** The native screens and the web views share the session; signing out anywhere signs out everywhere in the app.
11. **Two-step verification and passwords (rev 2).**
    - One step, one place: after the password on Sign-in. Required for any account with an admin, manager or cs role; not offered to worker and host in 1.0.
    - Two methods: a code sent to the person's own email address, or an authenticator app. The person chooses; the emailed code is open to all three roles, admin included. No text messages, no phone number.
    - An address is typed by its owner, counts only after a code sent to it was typed back, is shown masked everywhere after that, and is used for sign-in codes and nothing else. The app never asks for it before sign-in.
    - **There is no password reset by email**, in the app or on the web: if the inbox that receives the code could also reset the password, one mailbox would be both steps. A forgotten password is reset by an admin; a lost second step is recovered with a recovery code or reset by an admin (N20).
    - A badge opens floor accounts only, and only once the emailed code works (D3).
    - **The demo company never sends an email and never asks for a code** — at sign-in, at set-up or at deletion.
12. **Checked facts and guesses look different (new).** Anything on Scanit that came from an AI estimate or an unchecked source is labelled, so nobody reads a guess out on air as a fact.
13. **`/m/` pages in a phone browser (rev 2, new).** Supported for 1.0 only this far: each `/m/` page works on its own in a browser, with the same sign-in, roles and data. The page draws its own bottom bar listing only this account's `/m/` roots (Today, Pick; Scanit for a host) and never a desktop address. There is **no Pack and no Account** in a browser: packing on a browser is the existing station page, and account deletion, two-step set-up and legal links in a browser are the existing web pages. With no app around it, the avatar opens a small sheet with the person's name and **Sign out**; language stays on the page's own control. Rows that need the app ("Pack this order") are not drawn; "Open in Pick" and the Scanit row are ordinary links to `/m/` pages. A browser that is signed out or billing-locked is sent where the web sends it today (`/`, `/billing`). Nothing on the server redirects a browser to `/m/`, nobody is told to use `/m/` in a browser, and the floor's browser stations do not change. A fuller browser version of the app is not planned.

---

## 6. The 1.0 scope line (rev 2)

**In:** native Sign-in with a second step (emailed code or authenticator app), native two-step set-up, role-built tabs, Today, Pick, Table cleanup, Pack, Track with the packing video, Scanit (read-only), Account, the system states, and Manage for admins.

**Out, deliberately:** More; News and My Schedule (first two screens of 1.1); Leaderboard, Onboarding, Documents, Guides, the "my numbers" profile; Live Mode and Match Products; Shows / Issues / Inventory / Shipments for managers on the phone; editing a product, forcing a lookup, name search, favourites and selling scripts in Scanit; optional two-step verification for workers and hosts; **text-message codes and any phone number; "forgot password" by email**; push notifications; offline picking; an iPad sidebar; a theme picker; a company colour; a browser version of the app.

**Why:** a worker's whole day, a host's whole live and everything the reviewer is told to try must never touch a desktop page (R2). With native two-step set-up in 1.0 there is no exception: outside the admin-only Manage tab the app shows no desktop page at all.

**What Ofir's answers added to the draft's 1.0** — two things, both real work: Scanit (one new `/m/` screen plus its sandbox fence) and the emailed code (a new server capability and two native screens). The emailed code is the one on the critical path: M2's SEC-2 waits for it, and the demo company waits for SEC-2. Compared with the text-message plan it is lighter: no new provider account, no sender registration, no per-message cost — it uses the mail function the server already has. What it still needs from outside the code is a sender address people will trust (Q9) and a mail service configured in production, which could not be checked from here.

**What unlisted + United States only means for scope (D5):**
- 1.0 stays as drawn. app-review asked for phone-built Shows and Issues only before a *public* listing; they stay in 1.1.
- Apple declines an unlisted request for an app "in a beta or prerelease state" (app-review's report). So 1.0 carries **no "coming soon" rows, no empty placeholder tabs and no pointers to the website for missing features**; a host's Today shows what exists.
- English and Spanish in the app; no EU trader paperwork. The "request access" sentence in the listing may stay (K8) — release-manager's call.
- The app is installed from a link, not found by search; nothing in the app assumes a public store page except the "Update required" button, which opens the app's own store page by id (P1) — that this works for an unlisted app was not checked.

**What real users give up in 1.0, compared with build 5:** workers, managers and cs can no longer open the desktop site inside the app (schedule, news, leaderboard, shows, issues …). Those pages still work in the phone's browser, as they did before the app existed. Managers and cs, and any admin who used a badge, sign in with a password and a code from the day SEC-2 lands, and each needs an inbox they can open on their phone (or an authenticator app).

**First things to cut if 1.0 must shrink:** the admin sales line on Today; the Scanit row on Today for cs / manager / admin (host keeps the tab); badge scan on the native Sign-in (password only — the browser stations keep their badge page); going on to the next box while a video waits (flow 4.4 points 2–3 — Pack would then hold on the box until its video is up). Not cuttable: Scanit, the packing video in Track, the emailed code.

---

## 7. Open questions for Ofir (rev 2)

Q6, Q7 and Q8 are closed (decisions table). One question remains that needs him, because it needs his domain.

| # | Question | Option A | Option B | Recommendation |
|---|---|---|---|---|
| **Q9** | **Which address do the sign-in codes come from?** Blocks N13 going live, and through it SEC-2 and the demo company. | **Whatever the server sends mail from today** — the sender configured in Railway for new-hire invites. Costs nothing. But that sender could not be seen from here, and the code's own comments describe a Gmail account or another brand's address as possibilities; a code from an address that does not say Live Ops Hub is more likely to land in junk, and an outside seller's manager would get sign-in codes from someone else's brand. | **A liveopshub.com sender** (for example `no-reply@liveopshub.com`) on the mail service the code already supports. Costs Ofir a few DNS records on liveopshub.com — the same domain he is about to point at the public pages (D6) — and the programmer a settings change; no code beyond N13. | **B.** A is acceptable only for the first internal test. A code email that lands in junk is a manager who cannot sign in. |

Decided by app-planner in rev 2 and listed here so Ofir can overrule them when he reads the changed sections — none needs an answer to proceed:

- A floor worker who signs in by badge confirms account deletion with a fresh scan of their own badge (N21, flow 4.7). security-reviewer must confirm, because it changes the SEC-7 fix.
- Up to 10 packing videos may wait on a device, and the packer may keep packing meanwhile (flow 4.4).
- A host receives nothing about orders from the server, including on Today (N19).
- `/m/` pages in a phone browser are kept working but are not a product (rule 5.13).
- An admin can reset another person's two-step verification from the desktop Users page (N20) — a small desktop change.

Not questions, but waiting on Ofir: sign-off on the policy wording (D7), which the delete-account screen and the sentence about the email address both quote; and — from `scanit.md`, to glance at on the mockup — whether "our target price" may be as large as the retail price on a screen the live camera may catch.

---

## 8. Work for ios-designer (rev 2)

app-planner does not edit specs. ios-designer has rewritten `sign-in.md`, `scanit.md`, `today.md`, `track.md`, `me.md`, `cleanup.md` and `DESIGN_SYSTEM.md`; those were read for rev 2 and agree with this blueprint on tabs, screens, where each lives and the 1.0 scope. `scanit.md` covers all twelve points the approved version asked for. What remains:

### 8.1 Lines the rewritten specs must now touch up

| File | Line or section | What must change, and why |
|---|---|---|
| `screens/sign-in.md` | header note | "app-planner is correcting the blueprint" — done by rev 2; the note can go |
| `screens/sign-in.md` | §3.2, "An address is already on file for the account" | Cannot occur in 1.0: only the owner puts an address on the account, and turning the email method off deletes it (flow 4.2). Remove the state, or mark it "not in 1.0" |
| `screens/sign-in.md` | §3.5 | Add: turning Email off deletes the address; changing the address confirms the new one by its own code |
| `screens/sign-in.md` | §2 "Step expired (5 minutes since the password)" | Drop the number: the step must not expire under a code that is still valid (N13); the wording stays |
| `screens/sign-in.md` | "Open points — for app-planner" | All answered: admin reset is N20 (does not exist today; needed for the footnote to be true); floor accounts = accounts with no admin, manager or cs role, host is password-only; "Open in authenticator app" is accepted; no "forgot password" (rule 5.11); an account with several roles follows the session's "required" flag, as drawn |
| `screens/me.md` | Delete account, step 3 and Acceptance | A badge account confirms with **"Scan your badge"** (its own badge) instead of the password; the password field stays available (flow 4.7, N21). Acceptance becomes "cannot be completed without the password or, for a badge account, its badge". The first open point is answered |
| `screens/today.md` | section E and "What the spec needs from the server" | Read `open_shows` (N19) — `pending`, `to_pack`, `issues` per show, and a show stays until nothing is left to pick or pack. The interim wording ("{packed} of {total} packed", no issue pill) can go once N19 is built. The host variant asks the server for nothing about orders |
| `screens/today.md` | Bridge, browser line | In a browser the avatar **is** drawn and opens the small sheet with Sign out (rule 5.13) |
| `screens/track.md` | E "Next step", Assumptions last bullet, Bridge | "Open in Pick" → `openTab('pick', '/m/pick?order=…')`; the sub-line "Scan this label there to start" goes (flow 4.6, N6). In a browser it is an ordinary link |
| `screens/track.md` | C "Packing video", Assumptions | The page gets the format with the link (N10) and tries `.webm`; the "can't be played on this phone" state is the answer when the phone refuses. Acceptance should add: a browser-station `.webm` and an app `.mp4` both tried on a device |
| `screens/pack.md` | upload states (not re-read in this run) | The waiting-video rule of flow 4.4: saved on this phone, count of waiting videos, the stop at 10, the sign-out question, the "couldn't be saved" state |
| `DESIGN_SYSTEM.md` | §3.4 (Track → Pick), §8 (`openTab(id)`) | The call is `openTab(id, path)` with the limits in N6 |
| `DESIGN_SYSTEM.md` | §3.6, §9 last bullet, DS-3 | Settled by rule 5.13; DS-3 can close |

### 8.2 Specs not re-read in this run

`screens/pick.md`, `pack.md`, `more.md` and the eight waiting specs (`announcements.md`, `my-schedule.md`, `leaderboard.md`, `onboarding.md`, `documents.md`, `guides.md`, `live-mode.md`, `match-products.md`) were not opened for rev 2. The approved version asked for: `pick.md` → `/m/pick` as built, Account instead of More, avatar → Account tab; `pack.md` → indigo, the upload rule and the missing states; `more.md` withdrawn; the eight marked "not in 1.0" with their release. Whether that is done was not checked here.

### 8.3 Still to draw

Mockups for Track (with the video states), Account, the delete-account screen (password and badge variants), Table cleanup, and Pack with videos waiting. `sign-in.md`'s mockup should be checked against the touch-ups above.

Not specs, but the same kind of mismatch — for their owners: `BOARD.md` still records D3 as a text-message code and carries the entries "New questions Q6–Q8" and "SMS provider for 2FA codes"; `ROADMAP.md` M2–M6 were written for text messages and a phone-number privacy answer (lead session). `ios/README.md` and `ios/APP_STORE.md` describe Dashboard / Pick / Pack and an admin demo account (release-manager, R3). `mobile/pick.html`'s browser tab bar still lists Track and More (mobile-engineer, N7); `mobile/__init__.py` still emits the company colour (mobile-engineer, N16).

---

## 9. Review findings, decisions, and what was not verified

### Which part answers which finding

| Finding | Answered by |
|---|---|
| R1 demo access | flow 4.8; N12; `sandbox` flag in N3 |
| R2 web wrapper (4.2) | §2 (launch on Today, no desktop tab for the floor, no More), §6 (no desktop page outside Manage, no exception left), rule 5.8 |
| R3 listing ≠ build | §3.1 is the list the listing may describe; "pull up the video" stays true (Q5); product lookup for hosts may now be described |
| K1 privacy in-app | S1, S8, rule 5.6 |
| K2 deletion findable | S8, flow 4.7 — incl. a floor worker who has only a badge (N21) |
| K3 reviewer can wipe the demo | flows 4.7, 4.8 — no demo login is an admin (D2), and deletion is simulated |
| K4 support contact | S8 Support row, support@liveopshub.com (D7) |
| K5, K6 device proof, iPad | §2 iPad table (D4); every flow in §4 is a device-script section |
| K7 dead ends | (a) S1 gate; (b) S2 role-built tabs and the "role without access" rule; (c) server pages — no blueprint part (programmer) |
| K8 purchase call to action | flow 4.1 billing-locked state has no prices or links; US storefront only (D5) |
| K9 domain | rule 5.6, N18 (D6); Q9 for the code email's sender |
| K10 policy accuracy | no screen; N18 and Ofir's sign-off (D7). Scanit sends product names and barcodes — not personal data — to an AI service and to barcode databases; the policy's subprocessor list should name them and the mail service |
| K11 privacy answers | N18: the staff email address is already declared in the manifest and must be added to the App Privacy table; no phone number is collected for staff. Documents and new-hire uploads are not in the app for floor roles, but remain reachable by an admin inside Manage, so the answers must still cover them |
| K12 unrestricted web access | rule 5.8: web content only on our host, Manage admin-only; N11; the Scanit picture and the packing-video link are the two exceptions for app-review to judge |
| P1 | S11 update-required state |
| P2, P3 | rules 5.9, 5.2; N8c |
| P4–P8 | no blueprint part |
| SEC-1 | Q8 accepted: the gate covers any account with an admin, manager or cs role (N13 point 9); S12 works for all three |
| SEC-2 | flow 4.1 step 6; merged only after the emailed code is proven (D3) |
| SEC-3 | flows 4.1, 4.2, 4.8: no second step and no email in the demo company only |
| SEC-4 | N17; flows 4.1, 4.8, 4.9 (code mail and Scanit's outside calls are fenced for the demo company) |
| SEC-7 | S8 / flow 4.7: password or own badge (N21), a two-step code when enrolled, last-admin confirm, simulated in the sandbox |
| SEC-8 | host has no Pack tab, no label lookup and nothing about orders from `/api/today` (N19); flow 4.6 expects named fields, not the whole order row |
| SEC-9 | touched by N8d (repeat-safe upload) — the programmer may do both in one change |
| SEC-10, SEC-18 | N5 native sign-out |
| SEC-11 | part of N13: limits per account on codes checked and emails sent |
| SEC-15, SEC-16 | N11, N6 (the path limit on `openTab`) |
| SEC-5, 6, 12–14, 17, 19, 20 | server work with no screen in the app; no blueprint part |

### Not verified

- Nothing was run: no tests, no browser, no device. Every statement about Swift and about `app.py` is from reading.
- **No search tool in this run.** The lead asked for a search of `app.py` for an email field on staff accounts; what was done instead is a reading of these ranges: 750–810 (`_twofa_required`), 838–900 (throttles), 955–1147 (mail), 3885–3929 (gates), 4005–4026 (page policy), 4100–4176 (roles), 4440–5215 (home, `/api/today`, deletion, session, sign-in, two-step, upload), 6655–6725 (lookup), 12600–12800 (user management, badge), 14270–14338 (video). In those ranges a staff record never gets an email address, there is no self-service password reset, and no admin action resets another person's two-step verification. The security report says the same of the email field ("staff accounts have a username, no email"). The rest of the file — including the `LOGIN_HTML` page and the new-hire routes, which do hold email addresses of applicants — was not read.
- **`POST /api/show/cleanout`**: taken from ios-designer's reading (`cleanup.md`); not found or re-read here. Its role list and whether a second call is harmless are for the programmer to confirm (N9).
- **`/m/pick?order=…`**: that Pick already understands an order in its address is `track.md`'s statement; not checked.
- **Mail in production:** which mail service is configured, from which address it sends, and whether its mail reaches inboxes — unknown (Q9). The 20–25 s waits are from reading.
- **WebM on iPhone:** one compatibility table was read online; nothing was played on a device, and whether a web view inside an app behaves like Safari was not established (N10).
- **Waiting videos:** the limit of 10 and the 3.5 MB estimate (a comment in `api_upload`) are not measured on the floor.
- **Scanit:** read were the server routes (`app.py:15861-16354`), `_barcode_lookup_online` (`8528-8593`), and `tests/test_scanit_catalog.py` (not run), for the approved version. **Not read:** the desktop page's own HTML and script (`SCANIT_HTML`). Not checked: how long a first scan of an unknown barcode really takes; whether the app's content policy lets a picture from an outside host load in `/m/`; what share of the real catalog already has notes and prices.
- What the desktop `/home` draws for a host and a worker from `/api/today` (N19 must not break it).
- Whether workers know their passwords or sign in by badge only — N21 is planned so that either works.
- Which roles count as "packing roles" after SEC-8 — the tab table assumes worker, cs, manager, admin.
- N4 (the gates blocking `/api/mobile/session`) and N8a (a failed upload deletes the video) are code readings; nobody has reproduced them.
- N16 reads "no per-company colour in the app" as covering the desktop pages inside Manage too; if Ofir meant the phone-built and native screens only, the programmer's part of N16 is dropped and nothing else changes.
- That two reviewer logins (worker, manager) satisfy Apple when admin and host accounts exist — app-review's call.
- That the "Update required" link opens the store page of an unlisted app.
- How the floor really uses Live Mode, Match Products, News and My Schedule on phones today.
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
  - **Reviewer logins are manager + worker** (D2): flow 4.8 rewritten; the demo seed gains a pre-packed order with video and three complete catalog products (N12).
  - **Packing video in Track is a requirement** (Q5); N10 raised accordingly.
  - **Indigo only** (D8): rule 5.9, piece N16.
  - **Unlisted, US only** (D5): consequences written into §6.
  - **liveopshub.com and support@liveopshub.com** (D6, D7) written into S8, rule 5.6 and N18.
  - Flows renumbered (4.2 two-step set-up and 4.9 host with Scanit are new).
  - §7 replaced with Q6–Q8; §8 rewritten as an ordered work list for ios-designer.
- 2026-11-10 — **approved → rev 2** (awaiting Ofir's read of the changed sections). Why: after the approval Ofir replaced the text-message code with an emailed code, took text messages and phone numbers out of 1.0, and answered Q7 and Q8; and ios-designer, rewriting the specs, reported seven gaps the blueprint had left open.
  - **Email instead of text message, everywhere:** status and decisions table (D3 reworded; Q6 void, Q7 and Q8 recorded); §1 "Signs in with"; S1, S8, S12; N1, N3, N5, N13 (rewritten: email address on the staff record, confirm-address flow, send and check, codes readable by every worker, limits, the existing mail function, the fence), N14, N17, N18 (the staff email address is already declared in the manifest; no phone number); flows 4.1, 4.2, 4.7, 4.8 step 10; rule 5.11; §6; §9. The Twilio reference is removed.
  - **Two rules stated:** no password reset by email — an admin resets a forgotten password; the demo company never sends an email and never asks for a code (rule 5.11, flows 4.1, 4.2, §3.2).
  - **Who is gated:** any account with an admin, manager or cs role; worker and host are not offered two-step in 1.0 (S12, N13).
  - **Gap 1 — Today's data:** new piece N19 (`open_shows` with to-pack and issue counts for cs / manager / admin; a host receives nothing about orders; `backlog` untouched for the desktop). S3 and rule 5.7 updated.
  - **Gap 2 — Cleanup:** `POST /api/show/cleanout` named in S5 and N9 as existing per ios-designer's reading, to be confirmed by the programmer.
  - **Gap 3 — bridge:** `openTab(id, path)` with its limits (N6); "Open in Pick" opens that order (flow 4.6, N7).
  - **Gap 4 — waiting videos:** the rule in flow 4.4 and rule 5.3 (kept on the device, at most 10, tied to the recording account, automatic retry); N8d repeat-safe upload on the server.
  - **Gap 5 — deletion by a badge worker:** password or a fresh scan of the account's own badge (flow 4.7, N21, rule 5.1).
  - **Gap 6 — phone browsers:** new rule 5.13, a paragraph in §2, piece N22.
  - **Gap 7 — video format:** N10 rewritten — what the server must answer, the redirect and the 15-minute link, `.mp4` and `.webm`, the device proof required; the demo seed's video is `.mp4` (N12).
  - **New:** N20 (admin reset of two-step, which the sign-in spec's wording relies on); §3.4, the pieces grouped by owner; Q9 (sender address of the code email).
  - §7 replaced (Q6–Q8 closed, Q9 added, app-planner's own rev 2 decisions listed for Ofir to overrule); §8 replaced with the touch-ups the rewritten specs now need.
  - Not changed: §2 tabs per role and the iPad table, S2, S4, S6, S9–S11, S13, N2, N4, N11, N15, N16, flows 4.3, 4.5, 4.9, rules 5.2 (one sentence added on the code email), 5.4–5.10, 5.12.
