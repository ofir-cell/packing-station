# LiveOpsHub Mobile Design System

Owner: ios-designer · Status: **draft for Ofir's approval** · Nov 5 2026
Reference CSS: [`mobile/static/mobile.css`](../../mobile/static/mobile.css) (the layer itself) and [`classic-tokens.proposal.css`](classic-tokens.proposal.css) (proposed Classic values).
Mockups: [`mockups/pick.html`](mockups/pick.html) / `pick.png` / `pick-dark.png`, [`mockups/shows.html`](mockups/shows.html) / `shows.png` / `shows-dark.png`.
Screen specs: [`screens/`](screens/) (worker screens come first).

The target is an app that looks and feels like a well-made iPhone app, as judged by App Review and by a warehouse worker using it one-handed with gloves on during a shift. The brand stays the same: indigo → violet, the logo, and the four themes. This document turns them into iPhone tokens and components. It does not invent a new look.

---

## 0. What the baseline audit shows (iPhone 16 Pro, 393×852, run `audit/20261105-223237`)

| Finding | Evidence | Fixed by |
|---|---|---|
| About 20 undersized tap targets and about 10 bits of tiny text on **every** page come from the navigation chrome, not the page itself: Back 86×42, Home 56×42, off-canvas sidebar links 231×31, `brand-sub` 8px, group carets ▾ 11px | `small_target_samples` / `tiny_text_samples` are identical on /home, /admin/track, /admin/shows | §3 native tab bar + G9 (chrome hidden in app), G1, G3 |
| A grey shadow bleeds down the left edge of every screen | `.sidebar` keeps `box-shadow:0 0 60px` while it's translated off-canvas (all screenshots) | G6 |
| Horizontal overflow: `/admin/shows` +150px (row actions `.row-acts` at right=543), `/admin/roster` +53, `/admin/sku-lookup` +33, `/admin/track` and `/dashboard` +30 (Find button at right=423), `/admin/inbound` +26 | `wide_elements` | per-screen specs + G4/G5 |
| Inputs below 16px, so iOS zooms on focus: global search, show search, status select, date pickers (13px); up to 27 per page on `/admin/inbound` | `small_input_samples` | G2 |
| Tables cropped or squeezed on phones: Inventory catalog and Shipments run to 5,914px tall with 165 small targets; Purchasing shows a 5-column header with no rows | screenshots | §7 table → list |
| Pick and Pack have their own top bar ("Switch to Packing" 152×35, ES 43×38, 🌙 22×38, Logout 74×34) and `user-scalable=no` | PICK_HTML | §3 + per-screen spec, viewport rewrite in layer JS |
| Emoji used as icons (🏠 📦 🔎 📺) and `confirm()` dialogs | everywhere | SF-style SVG icons; native action sheets (§8) |
| **The Warehouse Manager's sidebar is nearly empty.** `_navbar()` gates items with `has("admin","cs")`, but `req_role` lets the manager into almost every admin route. The manager's menu only lists Today, Scanit, Purchasing, News and Me, even though Shows, Issues, Inventory and Shipments all return 200 | templates.py:104–165 vs app.py:4127–4140 | §3 server-built nav config (one source of truth) |
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

### 1.6 Color, existing tokens kept and extended
The existing variables stay: `--brand --brand-strong --brand-ink --brand-glow --bg --surface --surface-strong --border --text --text-muted --text-dim`. The new ones are `--brand-2`, `--brand-gradient`, `--on-brand`, the `--m-*` semantic colors, and `--m-material`.

Role of each token on mobile: **`--surface` = grouped page background**, **`--bg` = cells/cards**, `--surface-strong` = fills (search field, segmented track, progress track), `--brand-ink` = brand-coloured text, and `--brand` / `--brand-gradient` = fills with white text.

| Token | Classic (proposed, D1) | Taupe & Teal | Sage & Stone | Slate & Blush |
|---|---|---|---|---|
| `--brand` | #4f46e5 | #0f766e | #5b7355 | #c2607d |
| `--brand-2` (new) | #7c3aed | #0e7490 | #4d6a5a | #9d4d77 |
| `--brand-ink` | #3730a3 | #0a4d48 | #3f5a3a | #8f3f56 |
| `--surface` | #f2f3f7 | #f4f1ec | #eef0ea | #f1f2f4 |
| `--text-muted` | #566072 | #6e6a63 | #5e655a | #5a6572 |

**Dark set** (`html.m.theme-dark`, the same for all themes except the brand row):

| Token | Dark | | Token | Dark |
|---|---|---|---|---|
| `--bg` (cells) | #1c1c22 | | `--text` | #f4f4f7 |
| `--surface` (page) | #0d0d12 | | `--text-muted` | #a7a9b6 (7.3:1 on cells) |
| `--surface-strong` | #2a2a33 | | `--text-dim` | #9496a3 (5.9:1) |
| `--border` | rgba(255,255,255,.10) | | `--m-material` | rgba(28,28,34,.78) |
| `--brand` fill | Classic #5b54f0 · Taupe #0f766e · Sage #4f6849 · Slate #a84e68 (white text ≥4.5:1) | | `--brand-ink` text | Classic #a5b4fc · Taupe #5eead4 · Sage #b7cdb0 · Slate #f0a9bf |

Semantic colors (light → dark): green #15803d → #4ade80, teal #0f766e → #2dd4bf, blue #1d4ed8 → #93c5fd, amber #a16207 → #fcd34d, orange #c2410c → #fdba74, red #dc2626 → #f87171. Each one has a `-tint` background. Text on its own tint is ≥4.5:1.

**Dark mode switch:** `localStorage.lohubMode = light | dark | system`. The default is `system` in the app (the layer script follows `prefers-color-scheme`) and `light` in browsers. It's exposed in More → Appearance. Pick's existing `pickTheme` toggle migrates to this key.

### 1.7 Safe areas
- The layer script rewrites every page's viewport to `width=device-width, initial-scale=1, viewport-fit=cover`. That **removes** `maximum-scale=1, user-scalable=no` from Pick and Pack, because blocking zoom is an accessibility fail.
- `--m-safe-top|bottom|left|right` = `env(safe-area-inset-*)`. The nav bar pads the top. The action bar, sheet and web tab bar pad the bottom. Gutters add left/right in landscape.
- In the app the native tab bar sits outside the WKWebView, so inside the page `--m-tabbar-h: 0` and `env(safe-area-inset-bottom)` is 0. In mobile Safari, `--m-tabbar-h` = 49px + the bottom inset.

---

## 2. Brand expression
- **Primary action** = `--brand-gradient` (indigo → violet at 135°) with `--m-shadow-brand`. **One per screen**, in the sticky action bar.
- **Hero card** (`.m-card--hero`) uses the same gradient. At most one per screen, for "what you're doing now" (Pick: the current show; Today: today's count).
- Everything else is neutral: white cells on a grouped grey background, with brand used only for ink, active states, progress and focus.
- Logo: the app icon and launch screen are native. On web pages the logo appears only on Login / Badge login / Welcome. In-app screens show no wordmark, because the tab bar and title carry the identity.
- Emoji are not used as UI icons. Use 24×24 / 1.9-stroke SVG icons matching SF Symbols: `house`, `checklist`, `shippingbox`, `magnifyingglass`, `ellipsis`, `play.tv`, `exclamationmark.triangle`, `archivebox`, `barcode.viewfinder`, `keyboard`, `plus`, `line.3.horizontal.decrease`. Natively, use the SF Symbol of the same name.

---

## 3. Navigation model (inside the iOS app)

### 3.1 Decision: **native SwiftUI tab bar and native "More" list; web nav bar per page**
| Piece | Native or web | Why |
|---|---|---|
| Tab bar (≤5 tabs, role-based, badges) | **Native** `TabView` | App Review 4.2 ("minimum functionality"): a WebView with a web menu is the classic "repackaged website" rejection. A native tab bar, native More, native scanner and Pack, and haptics make the shell a real app. Also, the site does full page loads: a web tab bar would re-render and flash on every navigation, couldn't keep a back stack per tab, and would sit under the WebView's own safe-area handling. |
| One WKWebView per tab | Native | Each tab keeps its own history, so switching tabs never loses a worker's place. `allowsBackForwardNavigationGestures = true` gives native swipe-back. |
| "More" list | **Native** `List(.insetGrouped)` | It lists the rest of the role's nav. Tapping an item pushes a WKWebView onto the More tab's `NavigationStack`. |
| Pack tab | Native (exists) | camera scan → record → upload |
| Nav bar / large title / page actions | **Web** (`.m-navbar` + `.m-largetitle`) | Page actions (Import CSV, Filter, Select) live in the page's JS. Keeping the bar in the web avoids a per-screen native↔web toolbar protocol in phase 1. Phase 2 (optional): native `UINavigationBar` fed by `<meta name="lohub:title">` / `lohub:actions`. |
| Pull to refresh | Native `UIRefreshControl` on the WKWebView scroll view | Reloads the page. Pages with live polling can opt out with `<meta name="lohub:refresh" content="off">`. |
| Confirm / alert | Native via `WKUIDelegate` (`UIAlertController`) | So any remaining `confirm()` looks native (see §8). |

### 3.2 Single source of truth: `GET /api/mobile/nav`
The server builds the nav for the signed-in user **from route permissions**, using the same check as `req_role` (including the manager → admin elevation and `_MANAGER_BLOCK_PREFIXES`). It does not use `_navbar()`'s `has()` gates. This fixes the manager-menu bug and keeps the app, the web tab bar and the More page in sync.

```json
{ "role": "worker",
  "tabs": [ {"id":"today","title":"Today","symbol":"house","url":"/home"},
            {"id":"pick","title":"Pick","symbol":"checklist","url":"/pick"},
            {"id":"pack","title":"Pack","symbol":"shippingbox","native":"pack"},
            {"id":"track","title":"Track","symbol":"magnifyingglass","url":"/admin/track"},
            {"id":"more","title":"More","symbol":"ellipsis","native":"more"} ],
  "badges": {"issues": 3},
  "more": [ {"section":"Work","items":[{"title":"Live Mode","symbol":"dot.radiowaves.left.and.right","url":"/admin/live"}, …]}, … ],
  "profile": {"name":"Ana Picker","role_label":"Warehouse Associate","initials":"AP","url":"/me"} }
```
The app fetches this at launch, on foreground, and after a role change. Badge counts refresh every 60 s while the app is in the foreground.

### 3.3 Tabs per role (≤5, order fixed)
| Role | Tab 1 | Tab 2 | Tab 3 | Tab 4 | Tab 5 |
|---|---|---|---|---|---|
| **Worker** (worker / picker) | Today `/home` | Pick `/pick` | Pack *(native)* | Track `/admin/track` | More |
| **Warehouse Manager** | Today `/home` | Shows `/admin/shows` | Issues `/admin/issues` *(badge = open issues)* | Inventory `/admin/inventory` | More |
| **Admin** (and cs) | Today `/home` | Shows `/admin/shows` | Shipments `/admin/shipments` | Insights `/admin/packer-analytics` | More |

If a user holds several roles, the highest one picks the tab set (admin > manager > worker), and More includes everything from all of their roles.

### 3.4 "More" per role (native inset-grouped list; profile header row at top → `/me`)
**Worker**
- *Work*: Live Mode `/admin/live` · Match Products `/admin/preshow` · Table Cleanup `/admin/cleanup`
- *Me*: My Schedule `/my-schedule` · Leaderboard `/leaderboard` · Documents `/documents` · Onboarding `/onboarding` (with a badge for items left)
- *Help*: News `/announcements` (unread badge) · Guides `/guides`
- *App*: Appearance (System / Light / Dark + theme) · Language (English / Español) · Sign out (destructive, confirmed)

**Warehouse Manager**
- *Orders*: Shipments `/admin/shipments` · Shipment Health `/shipping-status` · Combine & Labels `/admin/combine` · Track `/admin/track` · Customers `/customers` · Giveaways `/giveaway`
- *Live*: Live Mode `/admin/live` · Match Log `/admin/match-log` · Scanit `/scanit` · Table Cleanup `/admin/cleanup`
- *Floor*: Pick `/pick` · Pack *(native)* · Packing Videos `/admin/videos`
- *Inventory*: Purchasing `/admin/purchasing` · Inbound Labels `/admin/inbound` · Stock Take `/admin/stocktake` · After-Live Cleanup `/admin/product-cleanup` · SKU Reconciliation `/admin/sku-lookup`
- *Team*: Roster `/admin/roster` · New Hires `/admin/hires` · Warehouse Analytics `/admin/packer-analytics` · Picker Analytics `/admin/picker-analytics`
- *Help*: News · Guides · Equipment `/admin/equipment` · Support `/support`
- *Me*: My Schedule · Documents · Onboarding
- *App*: Appearance · Language · Sign out
- (Only routes that return 200 for this manager are listed; the server filters them.)

**Admin**
- *Orders & Live*: Live Mode · Match Log · Scanit · Combine & Labels · TikTok Shop `/admin/tiktok` · Shipment Health · Track · Issues `/admin/issues` · Giveaways · Inbound Labels · Customers · Packing Videos · Table Cleanup
- *Inventory*: Inventory · After-Live Cleanup · Purchasing · SKU Reconciliation · Stock Take
- *Analytics*: Host Analytics `/admin/hosts` · Profit `/admin/profit` · Geography `/admin/geo-analytics` · Analytics `/analytics` · Repeat Customers `/admin/repeat-customers`
- *Team*: Users `/users` · New Hires · Badges `/users/badges` · Roster
- *Settings*: Company setup `/setup` · Settings `/admin/settings` · Permissions & PIN `/admin/permissions` · Audit log `/admin/audit` · Data check `/admin/data-check`
- *Help*: News · Guides · Support · Equipment
- *App*: Appearance · Language · Sign out
- The global search (`/api/search`) becomes a native `.searchable` field at the top of More for admin/cs.

### 3.5 What happens to the web sidebar and hamburger on phones
- **In the app:** `.sidebar`, `.sb-toggle` (☰), `.sb-nav2` (Back + 🏠), `.sb-mbar` and `.sb-ov` are hidden (G9), and `body` loses its 62px top padding. Back is the `.m-navbar__back` chevron plus native swipe-back. "Home" is the Today tab.
- **Mobile Safari <600px:** the layer renders a web `.m-tabbar` from the same `/api/mobile/nav` (server-injected HTML, no extra request), and More becomes a web page `/more` that renders the same sections. The hamburger and Back/Home are hidden (G8).
- **iPad (≥600px, browser or app):** the native app uses `TabView` with `.sidebarAdaptable`, so iPadOS shows a sidebar. In the browser, the existing web sidebar stays, with G6 applied.
- **Desktop (>820px):** unchanged.

### 3.6 Pushed screens
Every non-root screen shows `.m-navbar` with `‹ Back` (the label is the previous screen's title when known, otherwise "Back") and an inline title that fades in once the large title scrolls under the bar. Tab roots (marked server-side with `<html data-m-root>` when `request.path` is a tab URL for this role) show no back button. Modal flows (Issue report, Import CSV) use a bottom sheet with **Cancel** on the left and the confirm action on the right or in the action bar.

---

## 4. Components (CSS in `mobile.css §2`; all classes prefixed `m-`)

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
| Action sheet | `.m-sheet` containing `.m-list` of `button.m-row` plus a separate Cancel `.m-list` | for destructive confirmations (Delete show, Sign out). In the app, prefer `confirm()` → native |
| Form field | `.m-field` `.m-field__label` `.m-field__control` `.m-field__help` `.m-field--error` `.m-field__scan` | label above, 48pt control, ≥16px text, help or error below. **Any barcode/SKU/tracking field has a `.m-field__scan` button** (visible only in the app) that calls `LOHubNative.scan()` |
| Empty state | `.m-empty` `.m-empty__icon` `.m-empty__title` `.m-empty__body` + a `.m-btn` | always gives the next step ("Check back after your manager publishes the week" / "Import a CSV") |
| Loading | `.m-skeleton` | shaped like the content (rows, tiles); never a bare "Loading…" |
| Error / offline | `.m-banner--error` `.m-banner--warn` `.m-banner--offline` | says what happened and what to do, with a Retry button. Offline: "You're offline — scans are saved and will sync" (where that's true) |
| Toast | `.m-toast` (`--success --error`) `.is-shown` | above the action bar; 2.5 s; paired with `LOHubNative.haptic('success'|'error')` |
| Web tab bar | `.m-tabbar` `.m-tab[aria-current=page]` | **browser fallback only**, hidden in the app and at ≥600px |

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
- **Row actions** (Done / Edit / Delete on Shows) are never inline buttons on phones. Use a trailing swipe (`Done` green, `Delete` red) and the same actions in the detail screen's `…` menu → action sheet.
- **Scanning:** in the app, the primary scan action calls `LOHubNative.scan()`. A USB or Bluetooth scanner still types into the focused field. The keyboard button (`.m-actionbar__aux`) opens manual entry in a sheet.
- **Haptics:** `success` after a successful scan, pick, mark-done or save; `error` on a failed lookup, cancelled order or validation error; `warning` before destructive confirmations; `tap` on segmented and tab changes.
- **Copy:** sentence case, verbs on buttons, numbers before nouns ("14 left"), no ALL CAPS in body text (uppercase only in 13px section headers). Every string has an ES translation (workers switch EN/ES).

---

## 6. The global mobile layer

### 6.1 What gets injected and where
In `app.py` `_security_headers` (after_request), alongside the existing `_CSRF_SHIM`, for `text/html` responses that contain `</head>` and not `id="m-layer"`:

1. Before `</head>`: `<style id="m-layer">` + the contents of `mobile.css` (minified, about 9 KB; cache it as a module constant `_MOBILE_CSS`).
2. Immediately after it, a **synchronous** `<script id="m-layer-js">` (about 1.5 KB) that:
   - adds `html.m` when `matchMedia('(max-width:820px)')` matches **or** the UA contains `LiveOpsHubiOS`, and re-evaluates on change;
   - adds `html.lohub-ios` early from the UA (the bridge adds it again at document end, which is harmless);
   - applies dark mode: `lohubMode` (default `system` in the app, `light` elsewhere) → `theme-dark` on `<html>`;
   - rewrites `<meta name=viewport>` to `width=device-width,initial-scale=1,viewport-fit=cover`;
   - after DOMContentLoaded: toggles `.m-navbar.is-scrolled` on scroll; fills `td[data-label]` from `th` text for `table[data-m=list]`; in the app, enhances `input[data-scan]` with a scan button; maps `window.alert/confirm` only when not in the app (the app has native panels).
3. For users with a role (not login pages) on `<600px` and not in the app: the server inserts the `.m-tabbar` HTML before `</body>`, built from the same function as `/api/mobile/nav`.

Pages that don't use `__NAVBAR_CSS__` (Pick, Pack station, Login, Badge login, Welcome) get the layer too, because injection happens at the response level.

### 6.2 Selectors
- **Tokens and `m-*` components:** unscoped. They define only new variables and only style elements that carry `m-` classes, so desktop pages are unaffected.
- **Fix-ups:** `html.m …` only. `html.m` exists only at ≤820px or in the app.
- **Chrome replacement:** `html.lohub-ios …` only.
- **Table → list:** `html.m` inside `@media (max-width:599px)`.

### 6.3 The rules (each one fixes a class of audit failures on every screen at once)
| # | Rule | Fixes | Desktop risk | Phone/iPad risk |
|---|---|---|---|---|
| G1 | `button, [role=button], input[type=submit|button], select, .btn, a[class*=btn]` → `min-height:44px; touch-action:manipulation`; checkboxes and radios 22px; a label wrapping a checkbox is ≥44px tall | <44px targets; double-tap zoom delay | none (html.m only) | dense toolbars get taller and may wrap. Per-screen specs restyle those toolbars |
| G2 | `input` (except checkbox/radio/range), `select`, `textarea` → `font-size:max(16px,1em) !important` | iOS zoom on focus (13px search, date, select) | none | a few compact filter rows grow. Acceptable |
| G3 | 12px floor for `small, th, .brand-sub, .txt, .lbl, .label, .badge, .tag` and inline `font-size:8–11px` | <12px text (the 8px brand-sub, 9px "to pick", 10px "tiktok") | none | uppercase micro-labels get wider and may wrap. Specs replace them with the type scale |
| G4 | media `max-width:100%`; `pre` wraps; children of inline-flex rows get `min-width:0`; un-annotated tables scroll inside their own box | most overflow sources | none | a scrolling table is a stopgap. Annotate tables per §7 |
| G5 | `body{overflow-x:clip}` | anything G4 missed | none | can hide real bugs. **QA keeps measuring element right edges (`wide_elements`), not just `scrollWidth`** |
| G6 | the sidebar shadow appears only when `body.sb-open` | grey bleed on every screen's left edge | none (the shadow only exists at <900px) | none |
| G7 | `table[data-m=list]` → grid rows (primary / secondary / trailing / detail) at <600px | cropped tables (Inventory, Shipments, Purchasing) | none | needs `data-m` on `<td>`. Tables without it fall back to G4 |
| G8 | Mobile Safari <600px with `.m-tabbar`: hide ☰, Back/Home bar and top padding | hamburger as primary nav | none | none |
| G9 | In the app: hide `.sidebar .sb-toggle .sb-nav2 .sb-mbar .sb-ov`, remove body padding | duplicate chrome, 20 small targets and 10 tiny texts per page | none | **Pick and Pack must keep a way out.** In the app that's the tab bar. Their own `.top` bar is replaced per spec |
| G10 | In the app: `-webkit-touch-callout:none` (except inputs), `overscroll-behavior-y:none` | long-press link previews and rubber-band reveal of the white background | none | none |

### 6.4 Acceptance per screen (mobile-qa)
At 375 (SE), 393 (16 Pro), 430 (Pro Max) and 820 (iPad) widths, in light and dark: overflow 0 (element right edges), 0 targets <44, 0 inputs <16, 0 text <12 (excluding `.m-tab`), no JS errors except third-party, and a screenshot reviewed against the screen spec. Desktop at 1440: a pixel diff of every screen before and after the layer must be **0** (only `html.m` and new classes are allowed to change anything).

---

## 7. Table → list (phones) and when tables stay

- **Phones (<600px):** every data table becomes a list. Preferred approach: the screen renders `.m-list` rows from the same JSON on phones. Cheap approach: annotate the existing table:
  ```html
  <table data-m="list"> … <td data-m="primary">Jasmine Rivera</td>
     <td data-m="secondary">5700000000001 · KAY-VAN28</td>
     <td data-m="trailing"><span class="m-pill m-pill--packed">Packed</span></td>
     <td data-m="detail" data-label="Weight">0.8 lb</td> <!-- optional, max 2 -->
     <td>…</td> <!-- any un-annotated column is hidden on phones -->
  ```
  Rule of thumb: **primary** = what a person scans for (buyer / show / SKU name), **secondary** = the identifier (tracking / SKU code) plus at most one fact, **trailing** = status pill or the one number that matters. Everything else goes to the row's detail screen.
- Row checkboxes for bulk actions become a **Select** mode (header "Select" button → checkmarks on rows → action bar with the bulk verbs).
- Lists over 50 rows paginate with "Show 50 more" (or infinite scroll with a skeleton). Never render 1,000 rows on a phone (Shipments currently renders a 5,914px page).
- **Tables stay** on iPad (≥600px) and desktop when there are ≥4 meaningful columns that people compare (Inventory catalog, Shipments, Roster, Profit). On iPad they get a sticky header, 44pt rows, and horizontal scroll inside their own card only.

---

## 8. Native affordances via the bridge
- `LOHubNative.scan()` — any barcode, SKU, tracking or badge field (`<input data-scan>`), plus the primary "Scan" actions on Pick, Track, Match Products, Live Mode and Inventory Receive. Always feature-detect: `if (window.LOHubNative)`.
- `LOHubNative.pack(code)` — "Pack this order" from Track results and from Pick when an order is fully picked (offer "Pack now").
- `LOHubNative.haptic(style)` — see §5.
- `confirm()` / `alert()` — the iOS shell must implement `WKUIDelegate` `runJavaScriptConfirmPanelWithMessage` / `AlertPanel` as `UIAlertController`. Destructive confirmations in specs use an action sheet with a clear verb ("Delete show" / "Cancel"), never a paragraph in `confirm()`.
- Requested bridge additions (for the mobile-engineer and iOS): `LOHubNative.setBadge(tabId, n)` and `LOHubNative.openTab(id)`. The More list and tab bar are fed by `/api/mobile/nav`.

---

## 9. Accessibility and language
- Contrast ≥4.5:1 for all text tokens in light and dark (values above were chosen against `--bg` and their tints). The status pills carry text and a distinct shape (dot / dash / "!").
- Icon-only buttons need an `aria-label`. Segmented controls use `role=tablist` / `tab` with `aria-selected`. Progress bars use `role=progressbar` with a label ("63% picked").
- rem-based type: the iOS shell sets `WKWebView` `pageZoom` from the Dynamic Type size category (100% at Large, up to 135% at accessibility sizes). Layouts must survive 135%, so no fixed heights on text containers.
- EN/ES: the worker screens keep the existing `data-i18n` system. Language moves from a top-bar "ES" button to More → Language and the nav-bar `ES` chip on Pick.

---

## 10. Decisions needed from Ofir
- **D1. Default brand.** The Classic theme in `_NAVBAR_CSS` is currently 5 Second Beauty pink (#d9748f). The app brief says indigo/violet. Proposal: make Classic indigo #4f46e5 → violet #7c3aed everywhere (desktop too), and let tenants keep their own color via `_brand_style()`. Alternative: indigo only inside the iOS app.
- **D2. Manager tabs.** Today / Shows / Issues / Inventory is proposed. Option: swap Inventory for Shipments if the manager works shipments more than receiving.
- **D3. Pack in browsers.** The worker web tab bar on phones includes Pack → `/` (the web packing station). OK, or should phones in the browser get a "Get the app" prompt?
- **D4. Manager nav bug.** Fix `_navbar()` now (desktop too) so managers see Shows, Issues, Inventory and the other routes they can already open, or wait for `/api/mobile/nav`?
