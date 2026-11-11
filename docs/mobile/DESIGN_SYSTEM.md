# LiveOpsHub Mobile Design System

Owner: ios-designer · Status: **aligned to the approved app blueprint, 2026-11-10** (first draft Nov 5 2026)
Authority: [`APP_BLUEPRINT.md`](APP_BLUEPRINT.md) decides tabs, which screens exist, where each lives, the flows and the 1.0 scope. This document decides how they look and which CSS classes they use. Where the two disagree, the blueprint wins and this file is wrong.
Real CSS: [`mobile/static/mobile.css`](../../mobile/static/mobile.css) (components, `m-` classes) and [`mobile/static/shell.css`](../../mobile/static/shell.css) (base tokens and `/m/` page chrome). Reference screen: `/m/pick` (`mobile/pick.html`).
Mockups: [`mockups/tabbar.html`](mockups/tabbar.html) (tab bar per role), [`mockups/today.html`](mockups/today.html), [`mockups/scanit.html`](mockups/scanit.html), [`mockups/pick.html`](mockups/pick.html). `mockups/shows.html` is a Nov 5 exploration of a screen that is **not in 1.0** (blueprint §3.2).
Screen specs: [`screens/`](screens/).

The target is an app that looks and feels like a well-made iPhone app, as judged by App Review and by a warehouse worker using it one-handed with gloves on during a shift. Inside the app the brand is **always LiveOpsHub indigo → violet** (board decision D8): no company colour, no theme picker. The company's *name* is shown; its colour is not.

Decision ids: **D1–D8 and Q1–Q8 in this document always mean the board's** (`BOARD.md` → "Decided by Ofir"). This document's own open points are numbered **DS-1…** in §10.

---

## 0. What the baseline audit shows (iPhone 16 Pro, 393×852, run `audit/20261105-223237`)

History: this is the audit of the **desktop** pages on a phone, taken before `/m/` existed. It is why screens are rebuilt under `/m/` instead of patched. The "Fixed by" column is kept for the record; the desktop pages themselves are not edited by mobile work.

| Finding | Evidence | Fixed by |
|---|---|---|
| About 20 undersized tap targets and about 10 bits of tiny text on **every** page come from the navigation chrome, not the page itself: Back 86×42, Home 56×42, off-canvas sidebar links 231×31, `brand-sub` 8px, group carets ▾ 11px | `small_target_samples` / `tiny_text_samples` are identical on /home, /admin/track, /admin/shows | §3 native tab bar; `/m/` screens carry no desktop chrome |
| A grey shadow bleeds down the left edge of every screen | `.sidebar` keeps `box-shadow:0 0 60px` while it's translated off-canvas (all screenshots) | G6 |
| Horizontal overflow: `/admin/shows` +150px (row actions `.row-acts` at right=543), `/admin/roster` +53, `/admin/sku-lookup` +33, `/admin/track` and `/dashboard` +30 (Find button at right=423), `/admin/inbound` +26 | `wide_elements` | per-screen specs + G4/G5 |
| Inputs below 16px, so iOS zooms on focus: global search, show search, status select, date pickers (13px); up to 27 per page on `/admin/inbound` | `small_input_samples` | G2 |
| Tables cropped or squeezed on phones: Inventory catalog and Shipments run to 5,914px tall with 165 small targets; Purchasing shows a 5-column header with no rows | screenshots | §7 table → list |
| Pick and Pack have their own top bar ("Switch to Packing" 152×35, ES 43×38, 🌙 22×38, Logout 74×34) and `user-scalable=no` | PICK_HTML | §3 + per-screen spec, viewport rewrite in layer JS |
| Emoji used as icons (🏠 📦 🔎 📺) and `confirm()` dialogs | everywhere | SF-style SVG icons; `M.confirm` sheets (§4) |
| **The Warehouse Manager's sidebar is nearly empty.** `_navbar()` gates items with `has("admin","cs")`, but `req_role` lets the manager into almost every admin route. The manager's menu only lists Today, Scanit, Purchasing, News and Me, even though Shows, Issues, Inventory and Shipments all return 200 | templates.py:104–165 vs app.py:4127–4140 | not a mobile matter any more: the app draws tabs from the session's capabilities (§3.2). The desktop sidebar is DS-2 |
| Every page has 1 JS error: `ERR_TUNNEL_CONNECTION_FAILED` loading Google Fonts | `js_errors` | Self-host DM Sans (it also fixes bad Wi-Fi in the warehouse) |

---

## 1. Tokens

All sizes are in rem where text is involved (1rem = 16px), so iOS text-size settings and WebKit zoom scale them. The CSS variables are in `mobile.css §1`.

### 1.1 Spacing (4pt grid)
| Token | Value | Use |
|---|---|---|
| `--m-1` | 4px | icon ↔ label |
| `--m-2` | 8px | pill gaps, minimum gap between tap targets |
| `--m-3` | 12px | row gap, card internal small |
| `--m-4` | 16px | **screen gutter** (`--m-gutter`), row padding, card padding |
| `--m-5` | 20px | between sections |
| `--m-6` | 24px | hero spacing |
| `--m-8` | 32px | empty-state padding |

### 1.2 Radii
`--m-r-xs` 6 · `--m-r-sm` 8 (row icon, segmented) · `--m-r-md` 12 (buttons, inputs, stat tiles) · `--m-r-lg` 16 (cards, grouped lists) · `--m-r-xl` 22 (bottom sheet) · `--m-r-pill` 999.

### 1.3 Type scale (DM Sans, mapped to iOS text styles)
| Token | rem / px | Weight | iOS style | Use |
|---|---|---|---|---|
| `--m-fs-largetitle` | 2.125 / 34 | 800, −0.02em | Large Title | screen title |
| `--m-fs-title1` | 1.75 / 28 | 800 | Title 1 | stat values |
| `--m-fs-title2` | 1.375 / 22 | 800 | Title 2 | hero card title |
| `--m-fs-title3` | 1.25 / 20 | 700 | Title 3 | empty-state title, big counts in rows |
| `--m-fs-headline` | 1.0625 / 17 | 700 | Headline | nav title, card title |
| `--m-fs-body` | 1.0625 / 17 | 400–600 | Body | row title, inputs, buttons |
| `--m-fs-callout` | 1 / 16 | 400 | Callout | dense body |
| `--m-fs-subhead` | 0.9375 / 15 | 400–600 | Subheadline | row secondary line |
| `--m-fs-footnote` | 0.8125 / 13 | 600–700 | Footnote | section headers, labels |
| `--m-fs-caption` | 0.75 / 12 | 700 | Caption 1 | pills, units. **Floor: nothing smaller**, except the 10pt tab-bar label the HIG prescribes |

Numbers use `font-variant-numeric: tabular-nums`. Self-host DM Sans (400–800) from `/static/fonts/` and preload it, so the fonts never depend on Google over warehouse Wi-Fi.

### 1.4 Elevation
`--m-shadow-1` (cards and lists, hairline-soft) · `--m-shadow-2` (floating) · `--m-shadow-3` (sheet) · `--m-shadow-brand` (primary button / hero, tinted with brand). In dark mode, shadows are replaced by surface contrast (`--m-shadow-1: none`).

### 1.5 Motion
`--m-ease: cubic-bezier(.2,.8,.2,1)`. Durations: `--m-t-fast` 120ms (press, fade), `--m-t` 200ms (navbar material, toast), `--m-t-slow` 320ms (sheet). Press feedback is `scale(.97–.98)` plus a haptic `tap` in the app. Everything is disabled under `prefers-reduced-motion`.

### 1.6 Color — LiveOpsHub indigo, light and dark
The token names are the ones the desktop uses (`--brand --brand-strong --brand-ink --brand-glow --bg --surface --surface-strong --border --text --text-muted --text-dim`) plus `--brand-2`, `--brand-gradient`, `--on-brand`, the `--m-*` semantic colors and `--m-material`. For `/m/` screens the values are set in `shell.css` (light) and `mobile.css` `html.m.theme-dark` (dark).

Role of each token: **`--surface` = grouped page background**, **`--bg` = cells/cards**, `--surface-strong` = fills (search field, segmented track, progress track), `--brand-ink` = brand-coloured text, and `--brand` / `--brand-gradient` = fills with white text.

**One brand row. There is no other.** (D8)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand` | #4f46e5 | #5b54f0 | fills under white text (≥4.5:1 both modes), focus ring |
| `--brand-2` | #7c3aed | #7c3aed | gradient end |
| `--brand-gradient` | 135°, `--brand` → `--brand-2` | same | primary button, hero card, progress |
| `--brand-strong` | #4338ca | #818cf8 | pressed state (light); lifted accent (dark) |
| `--brand-ink` | #3730a3 (10.4:1 on white) | #a5b4fc | brand-coloured **text and icons** |
| `--brand-glow` | rgba(79,70,229,.14) | rgba(129,140,248,.18) | tinted fills (secondary button, row icon tile) |
| `--bg` (cells) | #ffffff | #1c1c22 | |
| `--surface` (page) | #f2f3f7 | #0d0d12 | |
| `--surface-strong` | #e7e9f0 | #2a2a33 | |
| `--border` | #e3e5ec | rgba(255,255,255,.10) | |
| `--text` | #141a26 | #f4f4f7 | |
| `--text-muted` | #566072 (6.4:1) | #a7a9b6 (7.3:1 on cells) | |
| `--text-dim` | #5f6b7d (5.4:1) | #9496a3 (5.9:1) | |
| `--m-material` | rgba(255,255,255,.82) | rgba(28,28,34,.78) | nav bar, action bar |

Semantic colors (light → dark): green #15803d → #4ade80, teal #0f766e → #2dd4bf, blue #1d4ed8 → #93c5fd, amber #a16207 → #fcd34d, orange #c2410c → #fdba74, red #dc2626 → #f87171, gray #4b5563 → #c4c7d0. Each one has a `-tint` background. Text on its own tint is ≥4.5:1.

**Native tint** (ios-engineer): one accent colour asset, light #4F46E5 / dark #A5B4FC, used for the selected tab, nav-bar buttons and links. In dark mode the *fill* indigo (#5B54F0) is too dark to be read as 10pt tab-label text on a dark bar, so the tint uses the ink value; filled buttons use #5B54F0 → #7C3AED with white text in both modes.

**What `/m/` pages must not do** (blueprint N16): emit a company colour. Today `mobile/__init__.py` `_brand_css()` injects the company's colour through `__BRAND_STYLE__`; that placeholder must render empty. The `[data-theme="taupe|sage|slate"]` rules still present in `mobile.css` are never matched on a `/m/` page (nothing sets `data-theme`) and can be deleted by mobile-engineer when convenient; no spec refers to them. Company themes and the per-company colour remain a desktop matter and are not described here.

**Light and dark:** the app follows the system setting. There is no in-app appearance picker (blueprint rule 5.9). `mobile.js` already does this: inside the app `theme-dark` follows `prefers-color-scheme`; in a browser the page is light. The `localStorage.lohubMode` override that `mobile.js` reads has no UI in 1.0 and no spec may add one.

### 1.7 Safe areas
- Every `/m/` page declares `width=device-width, initial-scale=1, viewport-fit=cover` and never `maximum-scale` or `user-scalable=no`: blocking zoom is an accessibility fail.
- `--m-safe-top|bottom|left|right` = `env(safe-area-inset-*)`. The nav bar pads the top. The action bar, sheet and web tab bar pad the bottom. Gutters add left/right in landscape.
- In the app the native tab bar sits outside the WKWebView, so inside the page `--m-tabbar-h: 0` and `env(safe-area-inset-bottom)` is 0. In mobile Safari, `--m-tabbar-h` = 49px + the bottom inset.

---

## 2. Brand expression
- **Indigo only** (D8). Same indigo → violet on every native and `/m/` screen, for every company, in light and dark.
- **Primary action** = `--brand-gradient` (indigo → violet at 135°) with `--m-shadow-brand`. **One per screen**, in the sticky action bar.
- **Hero card** (`.m-card--hero`) uses the same gradient. At most one per screen, for "what you're doing now" (Pick: the current show; Today: my numbers).
- Everything else is neutral: white cells on a grouped grey background, with brand used only for ink, active states, progress and focus.
- **Company name, not company colour.** The company name appears as text where it helps (Today subtitle, Account, the delete-company confirm). No company logo or wordmark inside the app.
- Logo: the LiveOpsHub app icon and launch screen are native, and the logo appears once more on the native Sign-in. Signed-in screens show no wordmark: the tab bar and title carry the identity.
- Emoji are not used as UI icons. Use 24×24 / 1.9-stroke SVG icons matching SF Symbols: `house`, `checklist`, `shippingbox`, `barcode.viewfinder`, `person.crop.circle`, `gearshape`, `magnifyingglass`, `exclamationmark.triangle`, `archivebox`, `keyboard`, `play.rectangle`, `tag`. Natively, use the SF Symbol of the same name.
- **A guess never looks like a fact** (blueprint rule 5.12). Anything estimated or unchecked carries a labelled pill (`.m-pill--pending` "Estimate", "Unchecked") next to the value; a checked value carries its source in words. Used on Scanit; the rule holds for any later screen.

---

## 3. Navigation model (inside the iOS app)

Source: blueprint §2. This section restates it for designers and engineers; it adds no tab and no screen.

### 3.1 What is native and what is web
| Piece | Native or web | Notes |
|---|---|---|
| Sign-in, two-step set-up, Account, system states, camera scan sheet | **Native** | no tab bar before sign-in |
| Tab bar (3–5 tabs, built per account) | **Native** `TabView` | a web menu inside a web view is the classic 4.2 rejection |
| One WKWebView per web tab | Native container | each tab keeps its own history; swipe-back on |
| Today, Pick, Table cleanup, Track, Scanit | **Web**, phone-built `/m/` pages | `.m-navbar` + `.m-largetitle` are drawn by the page |
| Pack | **Native** | camera, recording, upload |
| Manage (admin only) | Desktop pages in a web view under a native title | the only place a desktop page appears |
| Pull to refresh | Native `UIRefreshControl` on the web view | a page with live polling may opt out with `<meta name="lohub:refresh" content="off">` |
| Confirm / alert | `/m/` pages use `M.confirm` (a bottom sheet); they never call `confirm()` / `alert()` | |

### 3.2 Where the tabs come from
The tab bar is built **once per account** from the capabilities in `GET /api/mobile/session` (`can: {pick, pack, track, scanit, manage}`, blueprint N3) and rebuilt only when those change (sign-in, sign-out, role changed on the server). It never changes with data: an empty section explains itself. The app does not derive tabs from role names.

**There is no `/api/mobile/nav`, no More tab, no More list and no `/more` page.** Nothing in a spec may refer to them.

| Capabilities | Tabs, left to right |
|---|---|
| `can.pick` (and `can.pack`) | Today · Pick · Pack · Account |
| `can.pick` and `can.manage` | Today · Pick · Pack · Manage · Account |
| `can.scanit` and **not** `can.pick` | Today · Scanit · Account |
| none of the above (should not occur for a valid role) | Today · Account |

### 3.3 Tabs per role (what the rule above produces)
| Role | Tab 1 (launch) | Tab 2 | Tab 3 | Tab 4 | Tab 5 |
|---|---|---|---|---|---|
| `worker` | **Today** | Pick | Pack | Account | — |
| `manager` | **Today** (manager sections) | Pick | Pack | Account | — |
| `cs` | **Today** | Pick | Pack | Account | — |
| `host` | **Today** | Scanit | Account | — | — |
| `admin` | **Today** (manager + admin sections) | Pick | Pack | Manage | Account |
| Demo floor login | exactly as `worker` | | | | |
| Demo second login | exactly as `manager` | | | | |
| `superadmin` | no tabs: a native screen "The platform console is on the web" with Sign out | | | | |

A user with several roles gets the union (the server computes it). Mockup: [`mockups/tabbar.html`](mockups/tabbar.html).

| Tab | id (for `openTab`) | Label EN / ES | SF Symbol | Root |
|---|---|---|---|---|
| Today | `today` | Today / Hoy | `house` | `/m/today` |
| Pick | `pick` | Pick / Recoger | `checklist` | `/m/pick` |
| Pack | `pack` | Pack / Empacar | `shippingbox` | native |
| Scanit | `scanit` | Scanit / Scanit | `barcode.viewfinder` | `/m/scanit` |
| Manage | `manage` | Manage / Administrar | `gearshape` | desktop site, admin only |
| Account | `account` | Account / Cuenta | `person.crop.circle` | native |

Rules:
- Today is the launch tab for every role. Manage is never the launch tab.
- **No badges** on tabs in 1.0 (blueprint rule 5.5).
- A scan never switches tabs by itself (blueprint rule 5.1). Only a tap on a row or button calls `openTab`.
- The selected tab uses the native tint (§1.6); unselected tabs use the system secondary label colour. Labels are always shown.

### 3.4 What is reached from where
| From | Opens | How |
|---|---|---|
| Today | Track `/m/track` | pushed in the Today tab (row "Look up a label", or a scan on Today) |
| Today | Table cleanup `/m/cleanup` | pushed in the Today tab |
| Today | Scanit `/m/scanit` | pushed in the Today tab for accounts **without** a Scanit tab (cs, manager, admin); `openTab('scanit')` for a host |
| Today | Pick, Pack | `openTab('pick')`, `openTab('pack')` |
| Pick | Table cleanup `/m/cleanup?show=…` | pushed in the Pick tab when a show's table must be cleared first |
| Track | Pick, Pack | `openTab('pick')`; `LOHubNative.pack(code)` |
| any `/m/` nav-bar avatar | Account | `openTab('account')` |

No `/m/` screen links to a desktop page (blueprint rule 5.8); mobile-qa fails a screen that does.

### 3.5 iPad
Same tabs per role. **Tab bar only — no sidebar** in 1.0 (no `.sidebarAdaptable`); iPadOS places the bar near the top. `/m/` screens are a centred column (`shell.css`, ≥700px). Whether iPad ships in 1.0 is D4.

### 3.6 Phone browsers
`/m/` pages also open in a phone browser. There the page draws `.m-tabbar` (hidden in the app and at ≥600px). Which tabs it lists is **not settled by the blueprint** (see DS-3): until it is, the web tab bar lists only tabs that have an `/m/` root for this account — Today, Pick, and Scanit for a host — and never a desktop URL. `mobile/pick.html` still lists Track and More and links to `/home`, `/?force=pack`, `/admin/track`, `/me`; that is blueprint N7.

### 3.7 Pushed screens
Every non-root screen shows `.m-navbar` with `.m-navbar__back` (chevron + the previous screen's title: "Today", "Pick") and an inline title that fades in once the large title scrolls under the bar. Tab roots show no back button. A screen that can be either (Scanit: tab root for a host, pushed from Today for others) shows the back button only when pushed. Modal flows (report a problem, type a code) use a bottom sheet.

---

## 4. Components (CSS in `mobile.css §2`; all classes prefixed `m-`)

These class names are the ones `/m/pick` is built with. **They are not renamed.** A screen's own layout classes get a two-letter prefix and live with that screen (`pk-` Pick; proposed: `td-` Today, `tr-` Track, `cu-` Cleanup, `sc-` Scanit).

| Component | Classes | Spec |
|---|---|---|
| Screen | `.m-screen` (+ `--has-actionbar`) | page wrapper: grouped background, DM Sans 17px, bottom padding clears the action bar or tab bar |
| Nav bar | `.m-navbar` `.m-navbar__row` `.m-navbar__back` `.m-navbar__title` `.m-navbar__actions` `.m-iconbtn` (`--filled`) | sticky, 44pt row under the top safe area; transparent at the top, adds `.is-scrolled` (material blur + hairline + inline title) when `scrollY > 40`. Max 2 trailing icon buttons (44×44, `aria-label` required) |
| Large title | `.m-largetitle` (h1 + optional p) · `.m-eyebrow` | 34px/800; subtitle 15px muted, one line, a status summary (for example "Wednesday, Nov 5 · 48 orders waiting") |
| Section | `.m-section` `.m-section__header` `.m-section__footer` | uppercase 13px header with an optional trailing text action ("Select", "See all") |
| List / row | `.m-list` `.m-row` (`--lead`) `.m-row__lead` `.m-row__body` `.m-row__title` `.m-row__sub` `.m-row__trail` `.m-row__value` `.m-row__chev` | inset grouped, radius 16. Row min-height 44; with a subtitle it's about 64. Hairline separators inset to the text. Primary line 17/600 (one line, ellipsis); secondary line 15 muted; trailing value, pill or chevron. The whole row is the tap target |
| Card | `.m-card` `.m-card--tap` `.m-card--hero` | radius 16, padding 16; tappable cards scale to .98 on press |
| Stat tile | `.m-stats` (2-col grid) / `.m-stats--scroll` (horizontal snap) · `.m-stat` `.m-stat__label` `.m-stat__value` `.m-stat__delta` · `--brand --warn --good --bad` | label 13/600 above the value 28/800. Max 2 per row on phones; more than 4 tiles → scroll row |
| Status pill | `.m-pill` + modifier, `--plain` (no dot), `--brand` (platform/tag), `--live` | 22px tall, 12/700, tinted background and ink text, **always includes the word** |
| Progress | `.m-progress` > `span.m-progress__a / __b / __c` | 6px (hero, rows 4px, show cards 8px stacked) |
| Segmented control | `.m-seg` `.m-seg__btn[aria-selected]` `.m-seg__count` | 44pt including the 2pt track (G1 floor); 2–4 segments; counts in muted text |
| Filter chips | `.m-chips` > `.m-chip[aria-pressed]` `.m-chip__count` | horizontal scroll row for >4 filters (Documents, Guides); 44pt pills; the selected chip is filled with brand |
| Search field | `.m-search` (+ `.m-search__scan` when the bridge exists) | 44pt, filled `--surface-strong`, 17px input (never zooms), leading magnifier, `type=search` |
| Button | `.m-btn` + `--primary --secondary --destructive --plain`, `--lg` (52pt full width) | 44pt minimum; primary = gradient. Labels are verbs ("Scan packing label", "Mark done") |
| Sticky action bar | `.m-actionbar` (+ `.m-actionbar__aux` square secondary) | fixed above the tab bar or home indicator, material blur; one primary `.m-btn--lg` plus an optional 52×52 auxiliary |
| Bottom sheet | `.m-sheet` `.m-sheet__grabber` `.m-sheet__title` `.m-sheet__backdrop` (`.is-open`) | radius 22 on top, max 92dvh, drag-to-dismiss, focus trapped. Used for filters, issue reports, row actions |
| Action sheet / confirm | `.m-sheet` with `.m-sheet__title`, `.m-sheet__body`, `.m-sheet__actions` (two `.m-btn--lg`) — built by `M.confirm({title, body, ok, cancel, destructive})` | every destructive or "are you sure" step on a `/m/` page. Never `confirm()` |
| Radio list (in a sheet) | `.m-radios` > `button.m-radio[aria-checked]` > `.m-radio__dot` | one choice out of a few (report a problem) |
| Banner, positive | `.m-banner--ok` | "Scanner ready", "Table is clean" |
| Demo banner | `.m-banner--warn` as the first element under the large title | "Demo company — sample data. Nothing here is real or leaves the app." Shown on every `/m/` root when the session says `sandbox` |
| Nav-bar chips | `.m-avatar` (initials, opens Account), `.m-lang` (see §9) | defined in `shell.css` |
| Form field | `.m-field` `.m-field__label` `.m-field__control` `.m-field__help` `.m-field--error` `.m-field__scan` | label above, 48pt control, ≥16px text, help or error below. **Any barcode/SKU/tracking field has a `.m-field__scan` button** (visible only in the app) that calls `LOHubNative.scan()` |
| Empty state | `.m-empty` `.m-empty__icon` `.m-empty__title` `.m-empty__body` + a `.m-btn` | always gives the next step ("Check back after your manager publishes the week" / "Import a CSV") |
| Loading | `.m-skeleton` | shaped like the content (rows, tiles); never a bare "Loading…" |
| Error / offline | `.m-banner--error` `.m-banner--warn` `.m-banner--offline` | says what happened and what to do, with a Retry button. Offline copy never promises a queue: nothing is saved on the phone in 1.0 except a packing video waiting to upload (blueprint rule 5.3) |
| Toast | `.m-toast` (`--success --error`) `.is-shown` | above the action bar; 2.5 s; paired with `LOHubNative.haptic('success'|'error')` |
| Web tab bar | `.m-tabbar` `.m-tab[aria-current=page]` | **browser fallback only**, hidden in the app and at ≥600px; contents per §3.6 |

### Status pill mapping (shipments)
| Status | Class | Label (EN / ES) | Color | Shape |
|---|---|---|---|---|
| pending | `.m-pill--pending` | To pick / Por recoger | amber | dot |
| picked | `.m-pill--picked` | Picked / Recogido | blue | dot |
| packed | `.m-pill--packed` | Packed / Empacado | teal | dot |
| shipped | `.m-pill--shipped` | Shipped / Enviado | green | dot |
| cancelled | `.m-pill--cancelled` | Cancelled / Cancelado | red | dash |
| issue | `.m-pill--issue` | Issue / Problema | orange | "!" |

Show status: Not started → `.m-pill` (gray) · In progress → `.m-pill--picked` · Live → `.m-pill--live` (solid red, pulsing dot) · Done → `.m-pill--shipped`. Platforms (TikTok, Whatnot) → `.m-pill--brand.m-pill--plain`.

---

## 5. Interaction rules
- **One primary action per screen**, in `.m-actionbar`. Secondary actions go in the nav bar (icons) or in a row's sheet.
- **Row actions** are never inline buttons on phones. The whole row is the tap target; anything destructive goes through `M.confirm`.
- **Scanning is the same on every scan screen** (blueprint rule 5.1), through `mobile.js`: a screen registers one handler with `M.onScan(fn)` and gets codes from (1) a Bluetooth/USB scanner in keyboard mode with nothing tapped, (2) the camera — the primary button calls `M.scan()` → `LOHubNative.scan()`, (3) typing — the keyboard button (`.m-actionbar__aux`) calls `M.typeCode()`. What a scan means depends only on the screen in front. A scan never buys, ships, cancels or changes stock, and never switches tabs.
- **A wrong scan is never dropped silently:** the screen says what the code was and what it expected, with one way forward.
- **Haptics:** `success` after a successful scan, pick, mark-done or save; `error` on a failed lookup, cancelled order or validation error; `warning` before destructive confirmations; `tap` on segmented and tab changes.
- **Copy:** sentence case, verbs on buttons, numbers before nouns ("14 left"), no ALL CAPS in body text (uppercase only in 13px section headers). Every string a floor role sees has an ES translation (§9).

---

## 6. How `/m/` pages load the layer

The Nov 5 plan injected this CSS into every desktop page. That plan is **withdrawn**: mobile screens are a separate front end (`CLAUDE.md`, "Mobile work must not change the desktop"). Nothing is injected into `templates.py` pages and `app.py` `_security_headers` is not touched for it.

### 6.1 Page skeleton (as `/m/pick` does it)
```html
<!DOCTYPE html><html lang="en" class="m"><head>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<link rel="stylesheet" href="/m/static/mobile.css?v=__V__">
<link rel="stylesheet" href="/m/static/shell.css?v=__V__">
</head><body> … <script src="/m/static/mobile.js?v=__V__"></script><script src="/m/static/<screen>.js?v=__V__"></script>
```
- `class="m"` on `<html>` is set in the markup. `mobile.js` adds `lohub-ios` inside the app and `theme-dark` from the system setting.
- Fonts: DM Sans. `/m/pick` loads it from Google Fonts today; self-host it under `/m/static/` so the first paint never waits on an outside host over warehouse Wi-Fi (DS-4).

### 6.2 The fix-up rules in `mobile.css §3`
`html.m` rules G1–G5 apply on `/m/` pages and act as a safety net: G1 tap targets ≥44px, G2 inputs ≥16px, G3 text floor 12px, G4 nothing wider than the screen, G5 `overflow-x: clip`. G6–G9 target desktop chrome (`.sidebar`, `.sb-*`) that `/m/` pages do not contain; they are inert there. G10 (no long-press callout, no rubber-band) applies in the app. A `/m/` screen must pass §6.3 **without** leaning on the safety net.

### 6.3 Acceptance per screen (mobile-qa)
At 375 (SE), 393 (16 Pro), 430 (Pro Max) and 820 (iPad) widths, in light and dark, for every role that can open the screen: overflow 0 (measured by element right edges, not `scrollWidth`), 0 targets <44, 0 inputs <16, 0 text <12 (excluding `.m-tab`), no JS errors, **no link or redirect to a desktop page**, **no company colour** (computed `--brand` is #4f46e5 light / #5b54f0 dark), and a screenshot reviewed against the screen spec. Desktop pages: unchanged, because nothing of theirs was edited.

---

## 7. Lists, not tables

No 1.0 screen shows a table. Anything tabular is an inset list: **primary** = what a person scans for (buyer, show, product name), **secondary** = the identifier plus at most one fact, **trailing** = a status pill or the one number that matters. Everything else goes to a pushed detail. Lists over 50 rows paginate with "Show 50 more". Wide tables remain inside Manage (desktop pages, admin only) and are not restyled by this document.

---

## 8. Native affordances via the bridge

`window.LOHubNative`, available to the **main frame of `/m/` pages on our host only** (SEC-16). Always feature-detect; every `/m/` page must also work in a phone browser without it.

| Call | State | Use |
|---|---|---|
| `scan()` → Promise<code or null> | exists | camera scan sheet, through `M.scan()` |
| `pack(code)` | exists | "Pack this order" on Track: opens the Pack tab on that label |
| `haptic('success' \| 'warning' \| 'error' \| 'tap')` | exists | through `M.haptic()` / `M.toast()` — see §5 |
| `openTab(id)` | **needed** (blueprint N6) | ids in §3.3. Today → Pick / Pack / Scanit, Track → Pick, avatar → Account |
| session ended | **needed** (N6) | a `/m/` page that gets 401, a sign-in redirect or the billing lock tells the shell instead of navigating to `/` or `/billing` (both desktop pages — what `mobile.js` `M.api` does today). The shell shows Sign-in or the "subscription not active" state |
| keep awake (on / off) | **needed** (N6) | on while Scanit is in front, off when it leaves |

The names and signatures of the last two are ios-engineer's to fix; this document only requires that they exist. Proposed: `LOHubNative.sessionEnded(reason)` with `reason` = `signed_out` or `billing`, and `LOHubNative.keepAwake(true|false)`.

Not in the bridge: tab badges (`setBadge` is withdrawn — rule 5.5), theme or colour, navigation menus.

Browser fallbacks: no `scan()` → the type-it sheet (`M.askCode`); no `openTab` → an ordinary link to the `/m/` root of that tab if one exists, otherwise the row is not drawn; no `pack` → the row is not drawn; no keep-awake → nothing.

---

## 9. Accessibility and language
- Contrast ≥4.5:1 for all text tokens in light and dark (values above were chosen against `--bg` and their tints). The status pills carry text and a distinct shape (dot / dash / "!").
- Icon-only buttons need an `aria-label`. Segmented controls use `role=tablist` / `tab` with `aria-selected`. Progress bars use `role=progressbar` with a label ("63% picked").
- rem-based type: the iOS shell sets `WKWebView` `pageZoom` from the Dynamic Type size category (100% at Large, up to 135% at accessibility sizes). Layouts must survive 135%, so no fixed heights on text containers.
- **Language** (blueprint rule 5.2): English and Spanish for everything a floor role sees — Sign-in, two-step set-up, Today, Pick, Cleanup, Pack, Track, Scanit, Account, system states. It is chosen **once, in Account** (default: the device language) and applies to native and `/m/` screens together. `/m/` pages use `M.strings` / `data-t` and read `localStorage.lang`; the shell writes that key and reloads the web views when the choice changes. Stored text (product names and notes, show names, buyer names) is shown as stored.
- The `ES` chip in `/m/pick`'s nav bar (`#langBtn`, `.m-lang`) is hidden inside the app once Account carries the language row, and stays in phone browsers, where there is no Account screen (DS-3).

---

## 10. Open points of this document (DS-n)

Renumbered on 2026-11-10 so they no longer collide with the board's D1–D8. The old ids are given once for anyone following an old note.

| # | Was | Point | State |
|---|---|---|---|
| DS-1 | "D1" default brand | Indigo for the app | **Closed by board D8**: always indigo inside the app. Changing the desktop's default theme is not a mobile matter; `classic-tokens.proposal.css` is kept only as the record of that desktop proposal and is not used by `/m/` (its values live in `shell.css`). |
| DS-2 | "D2" manager tabs, "D4" manager sidebar bug | Manager tabs / desktop sidebar missing entries for managers | **Closed for the app by blueprint §2** (manager: Today · Pick · Pack · Account). The desktop sidebar bug is a desktop matter for product-engineer; not tracked here. |
| DS-3 | "D3" Pack in browsers | What a phone **browser** user gets around `/m/` pages: which tabs the web tab bar lists, where Pack and Account are, how they sign out and change language | **Open — for app-planner.** The blueprint plans the app only. Interim rule in §3.6. |
| DS-4 | — | Self-host DM Sans for `/m/` | Open — mobile-engineer; no decision needed. |
