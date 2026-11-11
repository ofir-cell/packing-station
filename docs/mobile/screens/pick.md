# Pick (tab 2) — `/m/pick` (built: `mobile/pick.html`, `mobile/static/pick.js`)

**Blueprint:** S4, flow 4.3, rules 5.1, 5.8, piece N7. **Release: 1.0. Exists** — this is the reference `/m/` screen. Roles: worker, cs, manager, admin. A host has no Pick tab.
**Aligned to the blueprint on 2026-11-10.** What the built screen must still change is listed in "Changes to the built screen" below; everything else describes it as built.

**Mockup:** [`../mockups/pick.html`](../mockups/pick.html) → `pick.png`, `pick-dark.png` (queue state)
**User:** warehouse worker or picker on the floor, one hand, often gloved, phone or iPad, on patchy Wi-Fi. Also opened by managers and admins.
**Purpose:** choose the show you're collecting for, scan a packing label, tick off each item on the table, then finish or report a problem. It is the most-used worker screen.

## What changed vs. the desktop page (`audit/…/pro/worker/pick.png`, the old `/pick`)
| Today | New |
|---|---|
| Custom top bar: ← Back (86×42), 🏠, "5 SEC PICKING" wordmark, "📦 Switch to Packing" pill cut off at the right edge, ES, 🌙 (22×38), Logout | None of it exists on `/m/pick`. The tab bar provides Today / Pack. Language and Sign out are in the **Account** tab; light/dark follows the system |
| "STEP 1" plus a centered 34px question and grey cards with 9px "TO PICK" text | Large title "Pick", the current show as a hero card, and an inset list of shows with a "left" count (20px number + 12px unit) |
| Show cards are #eff0f0 boxes with a 1.5px border, platform pill at 10px | `.m-list` rows: title, a `TikTok` pill, order count and who is on it, plus a 4px progress bar |
| Scan state: big 📋 emoji, "Ready to scan" and a hidden input | Scanning is the sticky primary action: in the app it opens the native scanner (`LOHubNative.scan()`); with a hardware scanner the hidden input still receives keystrokes |
| `user-scalable=no` | not present on `/m/pick` |
| Admin-only "Set as picking iPad" card in the worker flow | **not in the app.** The picking-station setting is a desktop matter (admins reach it inside Manage) |

## Layout at 390pt (state A: queue)
1. **Nav bar** (`.m-navbar`, root, no back). Trailing: the avatar (`.m-avatar`, initials, `aria-label` "Account") → `openTab('account')`. The `ES` language chip (`#langBtn`) is shown **only in a phone browser**; inside the app the language is chosen once in Account (blueprint rule 5.2).
2. **Large title** "Pick". Subtitle: "{Weekday}, {Mon D} · {N} orders waiting".
3. **Hero card** (`.m-card--hero`, tap → state C for the next order in this show, or opens the scanner) — shown only when the worker has a current show (`localStorage.pickShow` or server `current_show`).
   - Eyebrow "YOU'RE PICKING" + chip "{Platform} · Table {X}" (table only if known)
   - Title: show name (Title 2, wraps to 2 lines max)
   - Meta: "Started {time} · {N} orders"
   - Three numbers: **left to pick** · **picked** · **issue(s)** (issues only if >0)
   - White progress bar (picked / total)
4. **Segmented** `To pick {n}` | `Done today {n}`.
5. **Section "Shows"** (trailing hint "Tap to switch"). `.m-list` rows sorted by most to pick, with the current show first and marked with a 3px brand inset bar:
   - title: show name · sub: platform pill + "{N} orders · {You | first name of the picker on it | No one yet}" (+ "· {n} cancelled" if >0)
   - progress 4px · trailing: big number "{left}" + "left" and a chevron
   - Tap → sets the current show (haptic `tap`, toast "Picking {show}") and stays on the queue with the hero updated.
   - A show whose table must be cleared first carries a pill ("{n} to clear" or "Clean table"); tapping it opens **Table cleanup** for that show — `/m/cleanup?show={name}` or `/m/cleanup?show={name}&prepick=1`, pushed in the Pick tab (spec: [`cleanup.md`](cleanup.md)). Scanning a label of such a show does the same after the toast that says why.
6. **Your numbers** strip: This session · Today · Last 7 days (from `/api/pick/my-stats`).
7. **Sticky action bar:** primary `Scan packing label` (barcode icon) and an auxiliary keyboard button (manual entry sheet: one `.m-field` "Tracking or order #", 17px, `inputmode=numeric`, and a "Find order" button). Disabled with the helper toast "Choose a show first" when there's no current show.

## State B (removed as a separate screen)
The old "Ready to scan" screen is gone. Scanning is the action bar, and a Bluetooth/USB scanner works with nothing tapped (`mobile.js` catches its keystrokes at document level — no hidden input). Once a scanner has been seen on the device, a `.m-banner--ok` "Scanner ready — scan a label any time" sits under the hero.

## State C: order checklist (pushed screen, `?order={id}`)
1. Nav bar: `‹ Pick` back (asks "Leave this order? Items you ticked stay ticked." only if 0 < picked < total) · inline title = buyer name.
2. Large title: buyer name. Subtitle "Order {short id} · {N} items · {show}".
3. If the order was cancelled → full-screen red interstitial (keep today's behavior, restyled): icon, **"Don't pick this order"**, "The customer cancelled it. Put any items back and scan the next label.", primary "Scan next label". Fires haptic `error`.
4. Progress row: "{x} of {n} picked" plus a 6px gradient progress bar.
5. `.m-list` of items, one row each, at least 64pt: a 28px leading checkbox circle, title = product name (2 lines max), sub = SKU · "Qty {n}" (qty ≥2 shown as a bold `×{n}` pill), trailing = table/bin if known. Tapping the whole row toggles it (haptic `tap`); picked rows are dimmed to 55% with a strikethrough on the SKU. Giveaway items get `.m-pill--brand` "Giveaway".
6. Sticky action bar:
   - not all picked → primary disabled "Tick items as you pick" + auxiliary ⚠ button "Report a problem"
   - all picked → primary **"Done — scan next"** (haptic `success`, toast "Order picked"). In the app it also shows a secondary text button "Pack now" → `LOHubNative.pack(tracking)`.
7. **Report a problem** → bottom sheet: title "What's wrong?", 4 preset rows (Item missing · Damaged · Wrong SKU on table · Can't find the table) as a radio list, an optional note field (16px), then Cancel and **"Report & skip"** (destructive tint). Copy under the title: "Your manager gets it in Issues. You can keep picking."

## States
| State | Treatment |
|---|---|
| Loading shows | 3 skeleton rows plus a skeleton hero |
| Empty (no shows with orders to pick) | `.m-empty`: checklist icon, "Nothing to pick right now", "New orders show up here after the next live is imported.", button "Refresh" |
| Done today segment empty | "No finished shows yet today." |
| Lookup failed (label not in this show) | haptic `error`, sheet: "Label not in {show}" · "It belongs to **{other show}**." Buttons: "Switch to {other show}" / "Cancel" |
| Not found | toast error "No order for {code}" with a "Type it instead" action |
| Offline | `m-banner--offline` under the large title: **"You're offline. Reconnect to keep picking."** Nothing is queued in 1.0: a tick that fails says so and is not shown as done (blueprint flow 4.3, rule 5.4) |
| Cancelled order scanned | the full-screen stop (state C.3) |
| Wrong role (403) | `.m-empty`: "Your account can't open this." / "Ask your manager." |
| Session ended / subscription inactive | tell the shell (bridge "session ended"); today `mobile.js` navigates to the desktop `/` and `/billing` |
| Demo company | demo banner under the large title |
| Error loading | `m-banner--error` "Couldn't load shows" + Retry |

## Copy (EN / ES keys reuse `T.en / T.es`)
Title "Pick" / "Recoger" · "orders waiting" / "pedidos pendientes" · "YOU'RE PICKING" / "ESTÁS RECOGIENDO" · "left to pick" / "por recoger" · "Scan packing label" / "Escanear etiqueta" · "Done — scan next" / "Listo — siguiente" · "Report a problem" / "Reportar un problema".

## Components
`.m-navbar` `.m-iconbtn` `.m-largetitle` `.m-card--hero` `.m-seg` `.m-section` `.m-list` `.m-row` `.m-progress` `.m-pill--brand` `.m-actionbar` `.m-btn--primary` `.m-sheet` `.m-field` `.m-empty` `.m-skeleton` `.m-banner` `.m-toast`.

## Bridge
`scan()` for the primary action · `haptic('tap'|'success'|'error')` · `pack(tracking)` after an order is fully picked · `openTab('account')` from the avatar · session ended.

## Changes to the built screen (blueprint N7, N16 — mobile-engineer)
| In `/m/pick` today | Must become |
|---|---|
| Four jumps to the desktop `/admin/cleanup?show=…` (`pick.js`: two from a queue row, two after a scan) | `/m/cleanup?show=…` (and `&prepick=1`), pushed in the Pick tab — once `/m/cleanup` exists |
| Avatar links to the desktop `/me` | `openTab('account')`; in a browser the avatar is not a link |
| Home button `.m-homebtn` links to the desktop `/home` (wide browsers) | `/m/today` |
| Browser tab bar lists Today `/home`, Pick, Pack `/?force=pack`, Track `/admin/track`, More `/me` | only tabs with an `/m/` root: Today `/m/today`, Pick `/m/pick` (DESIGN_SYSTEM §3.6); strings `tab_track`, `tab_more` removed |
| `__BRAND_STYLE__` injects the company's colour (`mobile/__init__.py` `_brand_css()`) | renders empty: always indigo (D8) |
| `ES` chip always shown | browser only; in the app the language comes from Account |
| A lost session navigates to `/`, a billing lock to `/billing` (`mobile.js` `M.api`) | bridge "session ended" in the app |
| No demo banner | `.m-banner--warn` when the session says `sandbox` |

## Acceptance
Passes DESIGN_SYSTEM §6.3. The page contains no URL outside `/m/` (no `/home`, `/me`, `/admin/cleanup`, `/admin/track`, `/?force=pack`), and its computed `--brand` is LiveOpsHub indigo for every company. One-handed: the primary action sits in the bottom third; no tap target on the queue is above y=140pt except the nav-bar chips.
