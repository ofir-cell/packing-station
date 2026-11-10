# Pick (worker tab 2) — `/pick` · `PICK_HTML`

**Mockup:** [`../mockups/pick.html`](../mockups/pick.html) → `pick.png`, `pick-dark.png` (queue state)
**User:** warehouse worker or picker on the floor, one hand, often gloved, phone or iPad, on patchy Wi-Fi. Also opened by managers and admins.
**Purpose:** choose the show you're collecting for, scan a packing label, tick off each item on the table, then finish or report a problem. It is the most-used worker screen.

## What changes vs. today (`audit/…/pro/worker/pick.png`)
| Today | New |
|---|---|
| Custom top bar: ← Back (86×42), 🏠, "5 SEC PICKING" wordmark, "📦 Switch to Packing" pill cut off at the right edge, ES, 🌙 (22×38), Logout | Removed in the app (G9 + this spec). The tab bar provides Today / Pack. ES becomes a nav-bar chip. Dark mode and Logout move to More |
| "STEP 1" plus a centered 34px question and grey cards with 9px "TO PICK" text | Large title "Pick", the current show as a hero card, and an inset list of shows with a "left" count (20px number + 12px unit) |
| Show cards are #eff0f0 boxes with a 1.5px border, platform pill at 10px | `.m-list` rows: title, a `TikTok` pill, order count and who is on it, plus a 4px progress bar |
| Scan state: big 📋 emoji, "Ready to scan" and a hidden input | Scanning is the sticky primary action: in the app it opens the native scanner (`LOHubNative.scan()`); with a hardware scanner the hidden input still receives keystrokes |
| `user-scalable=no` | removed (layer rewrites the viewport) |
| Admin-only "Set as picking iPad" card in the worker flow | moves to More → Settings → "Use this device as a picking station" (admin) |

## Layout at 390pt (state A: queue)
1. **Nav bar** (`.m-navbar`, root, no back). Trailing: `ES` language chip (`.m-iconbtn`, label "Cambiar a español" / "Switch to English") and the avatar (initials) → `/me`.
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
6. **Your numbers** strip: This session · Today · Last 7 days (from `/api/pick/my-stats`).
7. **Sticky action bar:** primary `Scan packing label` (barcode icon) and an auxiliary keyboard button (manual entry sheet: one `.m-field` "Tracking or order #", 17px, `inputmode=numeric`, and a "Find order" button). Disabled with the helper toast "Choose a show first" when there's no current show.

## State B (removed as a separate screen)
The old "Ready to scan" screen goes away. Scanning is the action bar. For iPad picking stations with a USB scanner, the queue screen keeps a hidden focused input (as today) and shows a small `m-banner` "Scanner ready" under the hero.

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
| Offline | `m-banner--offline` under the large title: "You're offline. Ticks are saved on this phone and sync when you're back." (requires queued writes; otherwise "Reconnect to keep picking") |
| Error loading | `m-banner--error` "Couldn't load shows" + Retry |

## Copy (EN / ES keys reuse `T.en / T.es`)
Title "Pick" / "Recoger" · "orders waiting" / "pedidos pendientes" · "YOU'RE PICKING" / "ESTÁS RECOGIENDO" · "left to pick" / "por recoger" · "Scan packing label" / "Escanear etiqueta" · "Done — scan next" / "Listo — siguiente" · "Report a problem" / "Reportar un problema".

## Components
`.m-navbar` `.m-iconbtn` `.m-largetitle` `.m-card--hero` `.m-seg` `.m-section` `.m-list` `.m-row` `.m-progress` `.m-pill--brand` `.m-actionbar` `.m-btn--primary` `.m-sheet` `.m-field` `.m-empty` `.m-skeleton` `.m-banner` `.m-toast`.

## Bridge
`scan()` for the primary action · `haptic('tap'|'success'|'error')` · `pack(tracking)` after an order is fully picked.

## Acceptance
Passes §6.4. One-handed: the primary action sits in the bottom third; no tap target on the queue is above y=140pt except the nav-bar chips.
