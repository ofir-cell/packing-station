# App blueprint — Live Ops Hub (iPhone / iPad)

**Status: draft for Ofir's approval, 2026-11-10.** Nothing here is approved. Written by app-planner from `main` as checked out on branch `docs/roadmap-to-app-store`.

This is the app planned as one product: who uses it, what each role sees, every screen and where it lives, the journeys across screens, and what ships in 1.0. Screen design belongs to ios-designer (`docs/mobile/screens/`); this document only says which screens exist and how they connect.

Inputs: `ROADMAP.md`, `BOARD.md` (decisions D1–D8, all still open), `REVIEW-2026-11-10.md` (R1–R3, K1–K12, P1–P8), `docs/security/2026-11-10-mobile-baseline.md` (SEC-1…20), `DESIGN_SYSTEM.md`, the 16 specs in `screens/`, and the code (`mobile/`, `ios/LiveOpsHub/`, role checks in `app.py`).

How to read "state today": **exists** = in the repo and reachable in build 5 · **specified** = a spec exists, nothing built · **missing** = neither. None of it is proven on a device except "installs and opens" (`device-tests/PROVEN.md`).

### Apple guidance used (read online 2026-11-10)

| Page | Change log (latest) | What this blueprint takes from it |
|---|---|---|
| HIG › Tab bars (`developer.apple.com/design/human-interface-guidelines/tab-bars`) | June 8, 2026 | Tab bars are for navigation between top-level sections, not actions. "Avoid overflow tabs" — a More tab "makes it harder for people to reach and notice content". "Don't disable or hide tab bar buttons, even when their content is unavailable." Badges are reserved "for critical information". On iPadOS the system shows the tab bar near the top; converting it to a sidebar is an option for more complex apps ("Prefer a tab bar for navigation"). |
| HIG › Sidebars (`…/sidebars`) | June 8, 2026 | "Consider using a tab bar first"; the sidebar-adaptable style is for exposing "more areas than fit in a tab bar". |
| HIG › Launching (`…/launching`) | June 10, 2024 | "Launch instantly"; "Restore the previous state when your app restarts"; launch in the device's current orientation when both are supported. |
| HIG › Layout (`…/layout`) | September 9, 2026 | "Determine layout based on size classes, not device type or orientation"; "Keep functionality the same as size classes change"; iPad windows are resizable. |

Not fetched today, so nothing is asserted from them: HIG Onboarding, Managing accounts, Notifications, Web views, Split views. The App Review guideline wording used below is quoted from app-review's report, not re-read.

---

## 1. People and jobs

The server has **five** roles: `worker`, `host`, `cs`, `manager`, `admin` (`app.py` `VALID_ROLES`). "Picker" is not a role any more — it was merged into `worker` and is migrated at every boot (`app.py:939-947`). A picker and a packer are the same account type doing two jobs. `superadmin` (platform owner) is a sixth, internal account type.

| Who | Opens the app to | How often | Conditions | Done looks like |
|---|---|---|---|---|
| **Worker picking** (`worker`) | choose a show, scan a label, tick items off the table, finish or report a problem | all shift, hundreds of orders after each live | one hand, often gloves, phone or a shared iPad, Bluetooth scanner or camera, patchy Wi-Fi | "Order picked" and the next label scanned without looking for a button |
| **Worker packing** (`worker`) | scan a label, see the box contents, record the packing video, upload, next box | all shift | phone or iPad on a stand, Bluetooth/USB scanner, hands full | video saved to the order, order marked packed, next scan opens the next box |
| **Warehouse manager** (`manager`) | see where each show stands (to pick / to pack / issues), jump in to pick or pack, look up a label | many times a day, walking the floor | phone in hand, interrupted | knows which show is behind and why, in under a minute, without a laptop |
| **Customer service** (`cs`) | answer "where is my order / an item was missing": find the label, see who picked and packed it, watch the packing video | per buyer claim | desk or phone, good network | status and video in front of them in seconds |
| **Host** (`host`) | *nothing the app does today.* The host's tools (Scanit product lookup, live matching, availability) are desktop pages. Host is refused on Pick (`mobile/__init__.py` `PICK_ROLES`; measured 403 in the security report) | — | on air | — (see Q4) |
| **Admin** (`admin`) | everything a manager does, plus the full console (users, settings, TikTok, shipments, inventory) when away from a computer | daily glance; occasional deep task | at home, phone | floor status at a glance; any console page reachable when really needed |
| **Reviewer — floor login** (demo `worker`) | follow the review notes: sign in, pick an order, pack a box from the sample-label PDF, look up a label, delete the account | once, ~10 minutes, has never seen a warehouse | no scanner, no 2FA device, scans a PDF off a screen | every step in the notes works and no screen looks like a website |
| **Reviewer — second login** (demo `manager` or `admin`, per **D2**) | see the other account type | a few minutes | same | sees a different Today; with `admin` also sees Manage |
| **Platform owner** (`superadmin`) | not an app user | — | — | told the console is on the web (§2) |

Order of care, as Ofir set it: workers → manager → admin.

---

## 2. App map

Before sign-in there is **no tab bar**: one native sign-in screen in front of everything (answers K7a, R2).

After sign-in the tab bar is built **once per account** from what the server says that account may do, and does not change with data or state (an empty section explains itself; a tab never disappears mid-session). That is this blueprint's reading of HIG "don't disable or hide tab bar buttons": the rule is about an unstable interface, and a tab that would always answer "Access denied" for this account is not a section of this person's app (K7b). app-review should confirm that reading.

| Role | Tab 1 (launch) | Tab 2 | Tab 3 | Tab 4 | Tab 5 |
|---|---|---|---|---|---|
| `worker` | **Today** | Pick | Pack | Account | — |
| `manager` | **Today** (manager sections) | Pick | Pack | Account | — |
| `cs` | **Today** | Pick | Pack | Account | — |
| `host` | **Today** | Account | — | — | — |
| `admin` | **Today** (manager + admin sections) | Pick | Pack | Manage | Account |
| Demo floor login (`worker`) | as `worker` | | | | |
| Demo second login | as `manager` or as `admin` — whichever **D2** picks; no special case in the app | | | | |
| `superadmin` | no tabs: a native screen "The platform console is on the web" with Sign out | | | | |

A user with several roles (`extra_roles`) gets the union: any role that may pick adds Pick, `admin` adds Manage. The app does not work this out itself — see the session row in §3.3.

**Launch screen: Today, for every role.** Cold start with a live session opens Today; returning from the background keeps the person where they were. HIG Launching asks apps to restore the previous state on restart; Today's "Continue" row ("Keep picking {show}") is how this plan meets that without reopening a half-finished order from a stale state. ios-designer and app-review should weigh that choice.

What sits behind each tab:

| Tab | Root | Pushed / presented from it |
|---|---|---|
| **Today** | `/m/today` — my numbers, Continue, Look up a label, floor now; manager and admin also see each open show (to pick / to pack / issues) | Track (`/m/track`), Cleanup (`/m/cleanup`) |
| **Pick** | `/m/pick` — show queue | order checklist, report-a-problem sheet, Cleanup when a show's table must be cleared first |
| **Pack** | native Pack — scan stage | box contents + recording, saved |
| **Manage** (admin only) | the desktop site in a web view under a native title; never the launch tab | every desktop page the admin can open |
| **Account** | native — name, role, company | language, privacy, terms, support, sign out, delete account |

Decisions built into this table:

- **No "More" tab and no `/api/mobile/nav`.** The Nov 5 specs planned a fifth More tab listing every other page; nearly all of those pages are desktop pages, which is the 4.2 problem (R2), and HIG discourages an overflow More tab. What More held is either in Account (language, sign out), dropped from 1.0 (§3.2), or inside Manage for admins.
- **Track is not a tab.** It is one tap from Today for every role that may look up a label, and a scan made on Today is a lookup (§5.1). This keeps four tabs for the floor and five for admin; a Track tab would give admin six, i.e. an overflow tab. (Q2)
- **Manage is admin-only**, as the roadmap says. Managers and CS lose in-app access to the desktop pages they reach through today's Dashboard tab. (Q1)
- **Manager and admin get no tabs that point at desktop pages** (the Nov 5 design system gave them Shows / Issues / Inventory / Shipments / Insights tabs).

### iPad (D4)

| | If iPad is in 1.0 | If 1.0 is iPhone-only |
|---|---|---|
| App map | identical: same tabs per role. The system places the tab bar near the top on iPadOS. **Tab bar only — no sidebar** in 1.0: four or five sections do not need one (HIG Tab bars, Sidebars). | identical |
| Layout | every 1.0 screen must hold at regular width and in a resized window, decided by size class (HIG Layout); `/m/` screens as a centred column, Pack on a stand in landscape with a hardware scanner is the main iPad job | compact width only |
| Cost | device proof of every flow in §4 on an iPad in portrait, both landscapes and a resized window; 13-inch screenshots (K6) | `TARGETED_DEVICE_FAMILY: "1"`; floor iPads keep using the browser stations exactly as today; iPad work moves to 1.1 |
| What the blueprint assumes | nothing in 1.0 exists only on iPad or only on iPhone | same |

So D4 changes proof, screenshots and one build setting — not the map, the inventory or the flows.

---

## 3. Screen inventory

A screen with no row does not get built. "Roles" lists who can reach it in the app.

### 3.1 Screens in 1.0

| # | Screen | Purpose | Roles | Lives | State today | Release |
|---|---|---|---|---|---|---|
| S1 | **Sign-in** | username + password; 2FA code step; "Scan badge" (camera or scanner); Privacy and Terms links | everyone | native | **missing** as a native screen (sign-in happens on the desktop `/login` page inside the Dashboard tab). Endpoints exist: `POST /api/login`, `/api/login/2fa`, `/api/badge-login`. Spec `sign-in.md` needs changes (§8) | 1.0 |
| S2 | **Role-built tab bar** | the table in §2 | everyone | native | **missing** (three fixed tabs: Dashboard, Pick, Pack; launch tab is the desktop site) | 1.0 |
| S3 | **Today** | "what should I do now": my packed / picked today, Continue, Look up a label, floor now. Manager/admin: each open show with to-pick / to-pack / issue counts, overdue first. Admin: today's sales line. Host: greeting, floor numbers, and a plain line that host tools are on the website | all five roles | `/m/today` | page **specified** (`today.md`, needs changes), not built. Data **exists**: `GET /api/today` is already role-aware and returns the per-show backlog, issue count and admin money; `/api/pick/my-stats`, `/api/me/stats` | 1.0 |
| S4 | **Pick** — queue, order checklist, report a problem, cancelled-order stop | pick a show's orders | worker, cs, manager (through the server's manager→admin rule), admin | `/m/pick` | **exists**; three links leave for desktop pages and must change (§3.3 N7) | 1.0 |
| S5 | **Table cleanup** | pull cancelled items off the table, show by show; Pick sends workers here when a show is blocked | worker, cs, manager, admin | `/m/cleanup` | page **specified** (`cleanup.md`), not built; today Pick jumps to the desktop `/admin/cleanup` (`mobile/static/pick.js:240-241,316,321`). Data **exists**: `/api/cleanup/shows`, `/api/cleanup/<show>`, `…/mark` | 1.0 |
| S6 | **Pack** — scan, contents, record, upload, next | pack with video proof | worker, cs, manager, admin (exact list is the programmer's SEC-8 fix; host is out) | native | **exists** (`Features/Pack/`); gaps in §3.3 N8 | 1.0 |
| S7 | **Track** (label lookup) | scan or type a label → show, buyer, status, who picked and packed, last event; for cs / manager / admin also the packing video | worker, cs, manager, admin | `/m/track`, pushed from Today | page **specified** (`track.md`, needs changes), not built. Data **exists**: `GET /api/shipment/<code>`. Video link for a lookup: **not verified** (§3.3 N10) | 1.0 |
| S8 | **Account** | name, role, company; language; Privacy, Terms, Support; sign out; delete account (own screen: what is deleted, password, confirm; last admin gets the second "this deletes the company" confirm) | everyone | native | **missing** (`LegalLinks.swift` exists, unused; deletion is at the bottom of the desktop `/me`). Endpoint exists: `POST /api/account/delete` incl. `need_org_confirm` | 1.0 |
| S9 | **Manage** | the desktop console, presented as what it is, under a native title | admin only | desktop pages inside the Manage tab | **exists** as today's Dashboard tab (shown to everyone, launch tab) | 1.0 |
| S10 | **Camera scan sheet** | camera + typing fallback for any scan asked by an `/m/` page | whoever is on that page | native | **exists** (`ScannerSheet`) | 1.0 |
| S11 | **System states**: offline / can't reach server; update required; session expired; subscription inactive; 2FA set-up required; account type not supported (`superadmin`) | never a blank or desktop page | everyone | native | offline + update required **exist**; the other four **missing** (today they surface as desktop redirects: `/`, `/billing`, `/me?setup2fa=1`) | 1.0 |

### 3.2 Screens not in 1.0

| Screen | Roles | Lives when built | State today | Release | Why it waits |
|---|---|---|---|---|---|
| News (announcements, with "Got it") | all | `/m/` | specified; desktop page exists | **1.1 — first** | managers' channel to the floor; needs a badge rule |
| My Schedule | all | `/m/` | specified | 1.1 | read-only, small |
| Shows (manager) and Issues queue | manager, cs, admin | `/m/` | not specified; desktop pages exist | 1.1 | the manager's next need after Today; app-review asks for it before a *public* listing (D5) |
| Scanit (host product lookup) | host, cs, admin | `/m/` | not specified; desktop page exists | 1.1 | the only real host job on a phone (Q4) |
| Leaderboard | all | `/m/` | specified | 1.1 | motivation, not work |
| My numbers / achievements / recent packages (the top of `me.md`) | all | `/m/` or native | specified | 1.1 | Account in 1.0 is account only |
| 2FA enrolment, native | admin (and whoever SEC-1 adds) | native | missing | 1.1 | see §6 exception |
| Onboarding checklist | new hires | `/m/` | specified | later | |
| Documents | all | `/m/` | specified | later | includes signing and ID documents; keeping it out of the app keeps the privacy answers simpler (K11, security "Privacy answers vs. reality") |
| Guides | all | `/m/` | specified | later | |
| Live Mode, Match Products | worker, cs, admin | `/m/` | specified | later | real floor work, but two long scanning flows; how often they are done on a phone is not known (§9) |
| Push notifications, widgets, offline picking queue | — | native | missing | later | app-review: none is needed for 4.2 |
| **More tab, `/api/mobile/nav`, `/more` web page, native Appearance/theme picker, global search field** | — | — | specified in `more.md` / `DESIGN_SYSTEM.md §3` | **not in the app** | replaced by §2 |
| Welcome chooser (`/welcome`), badge page (`/badge-login`), desktop `/login`, `/me`, `/home`, `/billing` | — | — | exist on the web | **not in the app** (reachable only by an admin browsing inside Manage) | replaced by S1, S3, S8, S11 |
| iPad web packing station (`/`, `WORKER_HTML`) | worker | browser | exists | **not in the app** | the floor's browser stations are untouched |
| Platform console (`/admin/organizations`) | superadmin | browser | exists | **not in the app** | |

### 3.3 Pieces a 1.0 flow needs that do not exist today

Each should become its own board entry once the blueprint is approved.

| # | Piece | Needed by | Owner |
|---|---|---|---|
| N1 | Native sign-in gate in front of all tabs (S1), incl. 2FA code step, badge scan, legal links, error and throttle messages | every flow | ios-designer → ios-engineer |
| N2 | Tab bar built from the session (S2), rebuilt when the session's capabilities change (role changed on the server, sign-out, another user signs in) | every flow | ios-engineer |
| N3 | **`/api/mobile/session` tells the app what this account may open** — e.g. `can: {pick, pack, track, manage}` computed by the same check the routes use. Today it returns only `roles`; the app cannot derive from `["manager"]` that a manager may pick, because that comes from the server's manager→admin rule (`req_role`). Roles stay enforced on the server; this field only decides which tabs are drawn. Also needed in the same answer: `must_setup_2fa`, a billing-locked flag, a `sandbox` flag (for the "Demo company" banner, security requirement 10) and the public support contact (D7). | S2, S11 | programmer (shared-logic PR) → security-reviewer |
| N4 | `/api/mobile/session` must answer while the 2FA-setup gate or the billing gate is active. Today both gates stop it (it is not in `_2FA_SETUP_OPEN` / `_BILLING_OPEN_PATHS`), so the app would get 403 / 402 instead of a session. By code reading — not run. | S11 | programmer |
| N5 | Native Account (S8) incl. delete-account screen with password (SEC-7 changes the endpoint) and the last-admin confirm; sign-out that ends the session on the server and clears both cookie stores | flows 4.1, 4.6 | ios-engineer; programmer for SEC-7 / SEC-10. Only `GET /logout` (a redirect) exists; whether a JSON sign-out is needed is the engineers' call |
| N6 | Bridge additions: `LOHubNative.openTab(id)` (Today → Pick, Track → Pack, avatar → Account) and a "session ended" signal from `/m/` pages to the shell. Today `mobile.js` sends a signed-out page to `/` and a billing-locked page to `/billing` — both desktop pages. | flows 4.2–4.5 | ios-engineer + mobile-engineer; security-reviewer (bridge) |
| N7 | `/m/pick` clean-up: cleanup gates → `/m/cleanup`; avatar → Account tab instead of desktop `/me`; the browser-only web tab bar in `pick.html` still lists Track and More (`/admin/track`, `/me`) | flow 4.2 | mobile-engineer |
| N8 | Pack gaps: (a) a failed upload **deletes the recording** and the packer must film the box again (`PackFlowView.swift` `stopAndUpload`: `defer { removeItem }`, by reading) — keep the file and retry; (b) session-expired handled by the gate instead of "Open the Dashboard tab and sign in" (K7a); (c) Spanish strings (P3; CLAUDE.md says the app ships Spanish for the floor) | flow 4.3 | ios-engineer |
| N9 | `/m/today`, `/m/track`, `/m/cleanup` pages, each with its browser check | flows 4.2, 4.4, 4.5 | mobile-engineer (roadmap M5) |
| N10 | Packing video from a lookup for cs / manager / admin. `/media/video/*` and `/api/recordings` exist for admin and cs (manager through the server rule); whether `GET /api/shipment/<code>` gives enough to play the video was **not verified**. If not: one read-only field or endpoint. | flow 4.5 (Q5) | programmer to confirm |
| N11 | Manage wrapper (S9): admin-only, native title, exact-host rules (SEC-15), bridge closed to sub-frames (SEC-16) | admin | ios-engineer |
| N12 | Demo company, two logins, sample-label PDF (roadmap M3) | flow 4.7 | programmer; blocked on D1, D2 |

---

## 4. Flows

Same four failure cases for every flow, answered once here and only repeated where a flow differs:

- **No network:** `/m/` screens show the offline banner and keep what is on screen; actions that need the server say so and can be retried; nothing is queued in 1.0 except what §4.3 says about the packing video. Native screens show the existing "Can't reach LiveOpsHub — Try again".
- **Session expired** (7-day cookie, role removed, user deleted): the shell returns to Sign-in with one line, "You were signed out. Sign in again." After sign-in the person lands on Today, not mid-order.
- **Role without access:** the tab is not there. If a stale tab or link is used anyway the server refuses (403) and the screen says "Your account can't open this. Ask your manager." — never the plain text "Access denied".
- **Wrong scan:** the screen says what the code was and what it expected, with one way forward. A scan is never silently dropped.

### 4.1 First sign-in

1. App opens → Sign-in (no tab bar, no camera prompt).
2. Username + password → `POST /api/login`.
3. If the account has 2FA → code step → `POST /api/login/2fa`. Wrong code: stays on the step, says so; too many attempts: "Try again shortly" (429).
4. Floor accounts may instead tap "Scan badge" → camera or Bluetooth scanner → `POST /api/badge-login`. **D3:** if badge sign-in becomes floor-only, an admin / manager / cs badge is answered with "Use your password" and the password form; if D3 is refused, the badge signs anyone in as today.
5. Shell reads `/api/mobile/session`, builds the tabs (§2), opens Today.
6. Variants: `must_setup_2fa` → the 2FA set-up state (§6 exception); organisation suspended or billing-locked → "Your company's subscription is not active. Ask your admin." with Account still reachable for sign-out and deletion, no prices and no link to buy (K8); `superadmin` → "console is on the web"; app too old → Update required.
- No network: the form stays, "Can't reach LiveOpsHub", retry. Privacy and Terms open in an in-app browser sheet from this screen (K1).

### 4.2 A picker's shift

1. Today → "Continue: keep picking {show}" or the Pick tab.
2. Pick queue → tap a show (or scan a label straight away — the scan finds its show).
3. If the show's table must be cleared first, Pick opens **Cleanup** for that show (`/m/cleanup`), the worker marks each cancelled item pulled, "Done", back to Pick. (Today this step is a desktop page.)
4. Scan a packing label (Bluetooth scanner with nothing tapped, camera button, or typing) → order checklist.
5. Tick each item → "Done — scan next" → next scan. "Report a problem" → reason → the order goes to Issues, the picker continues.
- Wrong scan: label from another show → "It belongs to {other show}" with Switch / Cancel; unknown code → "No order for {code}" + Type it instead; cancelled order → full-screen "Don't pick this order".
- No network mid-order: ticks already sent stay; a tick that fails says so and is not shown as done (the server is the record — warehouse progress is never invented on the phone).
- Session expired mid-order: Sign-in → Today → Continue brings the show back; ticks already saved are still ticked.
- Host or any account without `can.pick`: no Pick tab.

### 4.3 Scan → pack → next box

1. Pack tab → scan the shipping label (scanner, camera, typing).
2. Contents card (combined packages and giveaways included) → recording starts (auto-record on by default).
3. Scan again or tap Stop → upload → "Packed" → next label. If the second scan was the next box's label, that box opens.
- Wrong scan: unknown → "Shipment not found", stays on scan; cancelled → "This order is cancelled — don't ship it"; a scan while a box is open but not recording is ignored today — it should say so (N8).
- No network at step 1: cannot look up; says so. **At step 3: today the video is lost and the box must be filmed again (N8a). 1.0 requirement: the recording is kept and the upload retried; the order shows as packed only after the server accepted the video, so stock is still deducted exactly once.**
- Session expired: Sign-in, then back on Pack; a kept recording is uploaded after sign-in.
- Camera or microphone refused: typing and a hardware scanner still work for the label; without the camera there is no video — say what to switch on in Settings. Microphone is optional.
- Signed out: cannot happen — the gate is in front (K7a).

### 4.4 A manager checking a show

1. Today (manager sections): open shows, most overdue first, each with to-pick / to-pack / issue counts; floor now (pickers and packers online, picked and packed today); open-issues count.
2. Needs to act → Pick tab (same show list) or Pack tab; needs one order → Look up a label (4.5).
3. Needs the Shows or Issues desktop pages → not in the app in 1.0 unless Q1 goes the other way; in 1.1 they are `/m/` screens.
- In 1.0 the manager's Today is read-only: there is no close-show, re-import or issue-resolve action in the app, so no money or irreversible action is reachable from a manager's phone.
- No network: last numbers stay with "may be out of date".

### 4.5 Looking up a label for a buyer's claim

1. Today → "Look up a label", or scan while on Today → Track.
2. Scan or type the tracking / order number → result: status, show, buyer, items, picked by, packed by, last event.
3. cs / manager / admin: "Packing video" plays in the app. Workers do not get the video (server rule: playback is admin, cs, manager).
4. From the result: status *pending* → "Open in Pick"; *picked* → "Pack this order" (opens the Pack tab on that label).
- Wrong scan: "No order found for {code}".
- No network: "Lookups need a connection".
- Host: no entry on Today; the server-side hole (a host can read any order through `/api/shipment`) is SEC-8 and is closed on the server, not by hiding the entry.
- Buyer address: the result shows the buyer's name and items, not the full address — the programmer's SEC-8 fix (named fields instead of the whole row) decides what the app receives.

### 4.6 Account deletion

1. Account tab → Delete account → a screen that says what is deleted and what the company keeps (wording per D7).
2. Enter the password (and a 2FA code when enrolled — SEC-7) → confirm.
3. Last admin of a company: a second confirm that names the company — "This also deletes {company} and all its data" → `wipe_org`.
4. Success → signed out → Sign-in, with one line confirming the deletion.
- Reachable when the company is billing-locked and during 2FA set-up (the server already allows it).
- Demo company: the server answers success, signs out, and the account still exists (security requirement 7); the app does nothing special.
- No network: nothing is deleted; says so.
- Never reachable by accident: destructive style, its own screen, password. Answers K2, K3.

### 4.7 The reviewer's ten minutes (needs **D1 = yes**; without it there is no submission, and nothing else in this blueprint changes)

1. Notes give two logins and a PDF of sample labels. Sign in with the **floor login** (no 2FA inside the demo company only).
2. Today: a "Demo company" banner, numbers, Continue.
3. Pick tab → choose the demo show → scan a label from the PDF with the camera (or type the number from the notes) → tick items → Done.
4. Pack tab → scan the same label → contents → recording → Stop → "Packed".
5. Today → Look up a label → the same number → status now *packed*, who packed it.
6. Account → Privacy, Terms, Support → Delete account → signed out. The notes say to test deletion with this login; it is restored nightly (K3).
7. Sign in with the **second login**:
   - **D2 = manager:** Today shows the shows and issue counts; the tabs are the same four. The reviewer never meets a desktop page. The notes say in one sentence that company admins also have a Manage tab with the web console.
   - **D2 = admin:** the same, plus the Manage tab with the desktop console. The reviewer can open desktop pages there (app-review's "moderate" residual 4.2 risk), every one of those routes must be safe inside the sandbox, and security requirement 3 ("not admin") is overruled.
- Wrong scan: the reviewer scanning anything else gets "No order for {code}" and the typed numbers still work.
- Nothing a reviewer does can leave the demo company or break it for the next reviewer (SEC-4, SEC-7, K3) — that is M3's job; the app only needs the banner.

---

## 5. Rules that span screens

1. **Scanning is the same everywhere.** Three inputs on every scan screen: Bluetooth/USB scanner in keyboard mode with nothing tapped, the camera, typing. What a scan *means* depends only on where you are: on Pick → open that order to pick; on Pack → open that box / stop and save; on Today or Track → look that label up; on Sign-in → badge. A scan never performs a money action and never switches tabs by itself.
2. **Language.** English and Spanish for everything a floor role sees: Sign-in, Today, Pick, Cleanup, Pack, Track, Account, system states. Chosen once in Account (default: the device language), applied to native and `/m/` screens together. Manage is whatever the desktop is. Today Pack and all native text are English only (P3).
3. **Offline and retry.** No screen goes blank or falls back to a web error. Reads show the last data with "may be out of date"; writes fail visibly and can be retried; the only thing held on the device is a packing video waiting to upload (N8a).
4. **The server is the record.** The app shows picked / packed only after the server said so. No tab, button or hidden entry is a permission: every role rule is enforced on the server.
5. **Badges and notifications.** 1.0 has no push notifications and no tab badges. When News arrives in 1.1 it gets the first badge; HIG reserves badges for critical information.
6. **Sign-out, help and legal are always in the same place:** the Account tab — Support, Privacy, Terms, Sign out, Delete account. Privacy and Terms are also on Sign-in. Legal and support pages open in an in-app browser sheet, on the domain D6 names.
7. **What a worker can never reach from the app:** the Manage tab or any desktop page; label buying, shipping, cancels, stock adjustments; users, roles, settings, billing, TikTok connection; other people's packing videos; another company's anything. Same for the demo floor login. A manager and cs in 1.0 additionally cannot reach Manage (Q1).
8. **Web content stays in two boxes.** `/m/` pages (our host, phone-built, bridge enabled on the main frame only) and Manage (admin, desktop pages). No `/m/` screen links to a desktop page; mobile-qa should fail a screen that does.
9. **Appearance.** One look across native and `/m/` screens (P2): 1.0 follows the system light/dark setting, with no in-app theme picker. Brand colour per D8 — one rule for native tint and `/m/` alike.
10. **One sign-in, one session.** The native screens and the web views share the session; signing out anywhere signs out everywhere in the app.

---

## 6. The 1.0 scope line

**In:** native Sign-in, role-built tabs, Today, Pick, Table cleanup, Pack, Track, Account, the system states, and Manage for admins. That is app-review's minimum set for 4.2 (review §6, items 1–10) and nothing beyond it.

**Out, deliberately:** More; News, My Schedule, Leaderboard, Onboarding, Documents, Guides, the "my numbers" profile; Live Mode and Match Products; Shows / Issues / Inventory / Shipments for managers on the phone; Scanit for hosts; push notifications; offline picking; an iPad sidebar; a theme picker.

**Why:** a worker's whole day and everything the reviewer is told to try must never touch a desktop page (R2). Every extra screen in 1.0 either has to be rebuilt for the phone first or drags a desktop page back into a worker's path. Of the 16 Nov 5 specs, 7 are in 1.0 (sign-in, today, pick, cleanup, pack, track, and `me` reduced to Account), 1 is dropped (more), 8 wait.

**What real users give up in 1.0, compared with build 5:** workers, managers and cs can no longer open the desktop site inside the app (schedule, news, leaderboard, shows, issues …). Those pages still work in the phone's browser, as they did before the app existed. Hosts get an app with Today and Account only.

**One stated exception to "no desktop page outside Manage":** an account that must enrol in 2FA before it can do anything. In 1.0 the 2FA set-up state presents the existing web enrolment page in a sheet, then returns to Sign-in. It is rare (existing admins are already enrolled), the reviewer never meets it (no 2FA in the demo company), and a native enrolment screen is listed for 1.1. If SEC-1 extends mandatory 2FA to managers, the exception covers them too. If Ofir or app-review will not accept the exception, native enrolment moves into 1.0 (endpoints exist: `/api/2fa/setup`, `/api/2fa/status`).

**First things to cut if 1.0 must shrink further:** badge scan on Sign-in (password only), the packing video inside Track (Q5), the admin sales line on Today.

---

## 7. Open questions for Ofir

Only questions this blueprint raises. D1–D8 are on the board and are not repeated; §9 says what depends on them.

| # | Question | Option A | Option B | Recommendation |
|---|---|---|---|---|
| **Q1** | Who gets the Manage tab (the desktop console)? | **Admin only.** Managers and cs lose the desktop pages in the app until Shows / Issues are phone-built in 1.1; they use the browser meanwhile. With D2 = manager, Apple's reviewer never sees a desktop page. | **Admin, manager and cs.** Nobody loses anything. But with D2 = manager the reviewer lands in desktop pages, and the security pass over the desktop routes (roadmap M8) is needed before submission instead of after. | **A.** |
| **Q2** | Where does label lookup (Track) live? | **Inside Today** — one tap, and scanning on Today is a lookup. Four tabs for the floor, five for admin. | **Its own tab** for everyone. Faster by one tap, but admin then needs six tabs, so something must go (Manage would move inside Account). | **A.** Decide on the tab-bar mockup. |
| **Q3** | Do News and My Schedule have to be in 1.0? | **No** — 1.0 is the work screens; News and My Schedule are the first two screens of 1.1. Costs: workers open the browser for them for a few weeks. | **Yes** — two more `/m/` screens, their checks and device proof before submission; roughly M5 grows by two thirds. | **A.** |
| **Q4** | What does a host get in 1.0? | **Today + Account only**, with a line that host tools are on the website. No extra work; hosts gain nothing from installing the app yet. | **Build Scanit for the phone in 1.0.** A real host tool, but a new screen that has no spec, and it calls the barcode and AI services that SEC-4 has to fence. | **A**, Scanit first for hosts in 1.1. |
| **Q5** | Can cs / manager / admin watch the packing video from a lookup in 1.0? | **Yes.** It is the reason cs opens the app and the listing promises "pull up the video in seconds". Cost: a player in Track, possibly one small server change (N10), and proof on a device. | **No** — video stays on the website; the listing sentence about claims is removed for 1.0 (R3). | **A**, unless N10 turns out to need more than a read-only field. |

---

## 8. Specs that contradict this blueprint (for ios-designer; app-planner does not edit them)

| File | What contradicts | What must change |
|---|---|---|
| `screens/more.md` | The whole spec: fifth More tab, native More list, `/api/mobile/nav`, `/more` web fallback, Appearance/theme picker, search field | Withdraw. Language and Sign out move to Account (`me.md`). |
| `DESIGN_SYSTEM.md` §3.1–3.5 | Native More list; `/api/mobile/nav` as the source of tabs; tab tables (worker: Today/Pick/Pack/Track/More; manager: Today/Shows/Issues/Inventory/More; admin: Today/Shows/Shipments/Insights/More — desktop pages as tabs); "More per role" lists; `.sidebarAdaptable` on iPad; tab URLs `/home`, `/pick`, `/admin/track` | Replace §3 with the app map in §2 of this document; tabs come from the session's capabilities (N3); iPad is tab bar only. |
| `DESIGN_SYSTEM.md` §8, §9, §10 | Bridge `setBadge` and "More list fed by `/api/mobile/nav`"; "Language moves to More"; its own decisions "D1–D4" collide with the board's D1–D8 | Bridge list = scan, pack, haptic, openTab, session-ended; language in Account; renumber or move those four decisions to the board. |
| `screens/today.md` | Path `/home` · `HOME_HTML`; avatar → `/me`; rank tile → `/leaderboard`; "For you" rows → `/onboarding`, `/announcements`, `/my-schedule`, `/documents` (all desktop pages in 1.0); no lookup entry; manager/admin sections "follow later"; no host variant | `/m/today`; avatar → Account tab; drop the rank link and "For you" for 1.0; add "Look up a label" and scan-means-lookup; specify the manager, admin and host variants and the demo banner. |
| `screens/track.md` | "worker tab 4", a tab root; "Managers and admins use it from More"; path `/admin/track`; "Open in Pick" → `/pick?order=` | Pushed from Today; `/m/track`; "Open in Pick" and "Pack this order" through `openTab` / `pack`; add the packing video for cs / manager / admin (Q5); no host access. |
| `screens/pick.md` | Path `/pick` · `PICK_HTML`; "Dark mode and Logout move to More"; avatar → `/me`; "Set as picking iPad" → More → Settings | `/m/pick` (as built); Account instead of More; avatar → Account tab; the picking-station setting is a Manage/desktop matter, not in the app. |
| `screens/cleanup.md` | Path `/admin/cleanup` · `CLEANUP_HTML`; no word on how it is entered | `/m/cleanup`; entered from Pick's two gates (with the show preselected) and from Today; "Go to Pick" through `openTab`. |
| `screens/sign-in.md` | "native sign-in **or** `/badge-login` in a full-screen WebView"; no 2FA step; no Privacy / Terms links; Welcome screen | Native only; add the 2FA code step, the D3 branches, legal links (K1), and the system states of S11; Welcome is not in the app. |
| `screens/me.md` | A web page (`/me` · `ME_HTML`) reached from More; numbers, achievements, recent packages; 2FA QR enrolment; delete by typing DELETE | Becomes the native Account tab (S8): account, language, legal, support, sign out, delete with password (SEC-7) and the last-admin confirm. Numbers / achievements → 1.1. Add the Support row (K4). |
| `screens/pack.md` | Brand colour "passed through `/api/mobile/nav`"; "never block the next scan (it queues)" is not what the code does | Colour per D8 from the session; state the 1.0 upload rule from §4.3 and the missing states (wrong scan while a box is open, camera refused). |
| `screens/announcements.md`, `my-schedule.md`, `leaderboard.md`, `onboarding.md`, `documents.md`, `guides.md`, `live-mode.md`, `match-products.md` | Back button `‹ More`; "More/News badge"; "language is in More"; desktop paths | Mark each "not in 1.0" with its release from §3.2. When one is taken up, it is entered from Today, lives under `/m/`, and gets its row here first. |

Not specs, but the same contradiction — for their owners: `ios/README.md` and `ios/APP_STORE.md` describe Dashboard / Pick / Pack and screens that do not exist (release-manager, R3); `mobile/pick.html`'s browser tab bar still lists Track and More (mobile-engineer, N7).

---

## 9. Review findings, board decisions, and what was not verified

### Which part answers which finding

| Finding | Answered by |
|---|---|
| R1 demo access | flow 4.7; N12; `sandbox` flag in N3 |
| R2 web wrapper (4.2) | §2 (launch on Today, no desktop tab for the floor, no More), §6, rule 5.8 |
| R3 listing ≠ build | §3.1 is the list the listing may describe; Q5 decides the "video for claims" sentence |
| K1 privacy in-app | S1, S8, rule 5.6 |
| K2 deletion findable | S8, flow 4.6 |
| K3 reviewer can wipe the demo | flows 4.6, 4.7 (deletion tested on the floor login; simulated server-side) |
| K4 support contact | S8 Support row (contact from D7) |
| K5, K6 device proof, iPad | §2 iPad table; every flow in §4 is a device-script section |
| K7 dead ends | (a) S1 gate; (b) S2 role-built tabs and the "role without access" rule; (c) server pages — no blueprint part (programmer) |
| K8 purchase call to action | flow 4.1 billing-locked state has no prices or links; listing text is M6 |
| K9, K10 | no blueprint part beyond rule 5.6 (domain per D6); M6 |
| K11 privacy answers | Documents and new-hire uploads are not in the app for floor roles (§3.2); they remain reachable by an admin inside Manage, so the answers must still cover them |
| K12 unrestricted web access | rule 5.8: web content only on our host, Manage admin-only; N11 |
| P1 | S11 update-required state |
| P2, P3 | rules 5.9, 5.2; N8c |
| P4–P8 | no blueprint part |
| SEC-1, SEC-2, SEC-3 | flow 4.1 (2FA step, D3 badge branches, no 2FA only in the demo company) |
| SEC-4 | flow 4.7; Q4 keeps Scanit's outbound calls out of 1.0 |
| SEC-7 | S8 / flow 4.6 (password, last-admin confirm, simulated in the sandbox) |
| SEC-8 | host has no Pack tab and no lookup entry; flow 4.5 expects named fields, not the whole order row |
| SEC-10, SEC-18 | N5 native sign-out |
| SEC-15, SEC-16 | N11, N6 |
| SEC-5, 6, 9, 11–14, 17, 19, 20 | server work with no screen in the app; no blueprint part |

### What depends on D1–D8

| Decision | Effect on this blueprint |
|---|---|
| D1 | yes → flow 4.7 exists. No → no reviewer path; nothing else changes. |
| D2 | manager → the reviewer's second login has four tabs and never sees a desktop page (with Q1 = A). Admin → it also has Manage. The app has no demo-specific code either way. |
| D3 | accepted → badge scan on Sign-in works for floor roles only; others are sent to the password form. Refused → badge signs in any role, as today. |
| D4 | §2 iPad table: proof, screenshots and one build setting; not the map. |
| D5 | public listing → app-review asks for phone-built Shows / Issues before submitting, which pulls two 1.1 rows into 1.0. Unlisted → 1.0 as drawn. |
| D6 | the host of the Privacy / Terms / Support links in S1 and S8. |
| D7 | the Support row's contact and the wording on the delete-account screen. |
| D8 | one colour rule for native tint and `/m/` (rule 5.9); the demo company uses indigo either way. |

### Not verified

- Nothing was run: no tests, no browser, no device. Every statement about Swift and about `app.py` is from reading (grep and targeted reads; `app.py` and `templates.py` were not read whole).
- N4 (the gates blocking `/api/mobile/session`) and N8a (a failed upload deletes the video) are code readings; nobody has reproduced them.
- N10: whether a lookup can already return a playable packing-video link.
- What `/api/today` should show a worker or a host: the endpoint computes the show backlog for every signed-in role; whether floor roles should receive it is a question for the programmer and security-reviewer.
- Which roles count as "packing roles" after SEC-8 — the tab table assumes worker, cs, manager, admin.
- How the floor really uses Live Mode, Match Products, News and My Schedule on phones today; the 1.1 order in §3.2 is a guess until Ofir or the warehouse manager confirms it.
- Whether workers know their passwords or sign in by badge only (affects how much the badge scan on Sign-in matters, and the delete-account password step for floor accounts).
- HIG pages not fetched are listed at the top; Apple's own guideline text for 4.2, 5.1.1 and 2.1 was taken from app-review's report.
- The reading of "don't hide tab bar buttons" in §2 is this document's interpretation, not Apple's wording.

---

## Change log

- 2026-11-10 — first draft, for Ofir's approval.
