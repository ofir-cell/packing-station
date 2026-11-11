# Track (label lookup) — `/m/track` (data: `GET /api/shipment/{code}`)

**Blueprint:** S7, flow 4.6, flow 4.8 steps 5 and 8, rules 5.1, 5.7, 5.8, pieces N9, N10. **Release: 1.0.**
**Mockup:** not drawn in this round (HTML mockups exist for Today, Scanit and the tab bar).
**User:** a worker holding a package who needs to know what it is; customer service, a manager or an admin answering "where is my order / an item was missing".
**Purpose:** scan or type a tracking or order number → status, show, buyer, items, who picked and packed it, the last event — and, for cs / manager / admin, **the packing video, played in the app**.

Track is **not a tab** (board Q2). It is **pushed from Today**: the row "Look up a label" opens it empty; a scan made on Today opens it with the result (`/m/track?code=…`). Roles: worker, cs, manager, admin. A host has no entry and no access.

## Layout at 390pt
1. **Nav bar**: `.m-navbar__back` "Today" (history back). Inline title "Look up a label". No trailing button.
2. **Large title** "Look up a label". Subtitle "Scan or type a tracking or order number."
3. **Demo banner** when `sandbox`.
4. **Result** (after a lookup) — or the ready block before the first one.
5. **Sticky action bar:** primary **"Scan label"** (`M.scan()`) + auxiliary keyboard button (`aria-label` "Type a number instead" → `M.typeCode()`; sheet title "Type the number", label "Tracking or order number", button "Look up").

Three inputs as on every scan screen: Bluetooth/USB scanner with nothing tapped, camera, typing. There is no always-visible text field, so the keyboard never covers the result and a hardware scan needs no focus.

### Ready block (no lookup yet)
`.m-empty`: magnifier icon · "Scan a label" · "You'll see its show, its status and who handled it."

### Result
**A. Summary card** (`.m-card`):
- Row 1: status pill (`.m-pill--pending|picked|packed|shipped|cancelled|issue`, word always shown) + platform pill (`.m-pill--brand.m-pill--plain`) when known.
- Title: buyer name (22px/800, 2 lines max). Sub: "{show name} · {n} item(s)".
- Cancelled order: a `.m-banner--error` inside the card, "This order is cancelled — don't ship it."

**B. Details** (`.m-section`, header "Details"; `.m-list`, each row title = label in muted 15px, trailing value 17px/600):
- **Tracking** — monospace digits, middle-ellipsis; tap copies, toast "Copied".
- **Picked by** — "{name} · {time}" or "Not picked yet".
- **Packed by** — "{name} · {time}" or "Not packed yet".
- **Last event** — "{what} · {who} · {time}" from the newest entry of `events`.

**The buyer's address is never shown** — name and items only (blueprint flow 4.6).

**C. Packing video** (`.m-section`, header "Packing video") — **only for accounts allowed to watch it (cs, manager, admin).** For a worker the section does not exist: no locked row, no "ask a manager" (blueprint rule 5.7). What a worker sees instead is the "Packed by {name} · {time}" row above, which answers the floor's question.
- Collapsed: `.m-list` row, lead `play.rectangle` · title "Play packing video" · sub "{recorded date, time} · {duration}" when known.
- Tap → an inline player replaces the row (class `tr-video`): `<video controls playsinline preload="metadata">`, black background, radius 12, full column width, height by the video's aspect ratio, capped at 60dvh, `object-fit: contain`. Native controls only (they include full screen). It never autoplays with sound before a tap.
- States of this section:

| State | Treatment |
|---|---|
| No video yet (order not packed) | row, not tappable, muted: "No video yet — this order hasn't been packed." |
| Packed, video not arrived | row, not tappable: "The video hasn't arrived yet. Check again in a minute." + text button "Check again" (repeats the lookup) |
| Loading | the player box as a `.m-skeleton` at 16:9 with "Loading video…" |
| Playing | native controls |
| Failed / stopped mid-play | in the player box: "The video stopped." + `.m-btn--secondary` "Try again" |
| Link expired (links last 15 minutes) | "Try again" first repeats the lookup to get a fresh link, then plays; the person sees only "Loading video…" |
| Format this phone can't play | "This video can't be played on this phone." (no button) |
| Offline | "Videos need a connection." |

**D. Items** (`.m-section`, header "Items · {n}"): `.m-list`, title = product name (2 lines), sub = SKU, trailing `×{qty}` when > 1. Combined packages and giveaways are listed in the same list, giveaways with `.m-pill--brand` "Giveaway".

**E. Next step** (a row, not a second primary button; only when one applies and the bridge exists):
- status *pending* and `can.pick` → row "Open in Pick" · sub "Scan this label there to start" → `openTab('pick')`.
- status *picked* and `can.pack` → row "Pack this order" → `LOHubNative.pack(tracking)` (opens the Pack tab on that label).
- Otherwise nothing. In a browser neither row is drawn.

The next scan replaces the result. No history list is kept in 1.0 (a list of buyers' names should not sit on a shared phone).

## States
| State | Treatment |
|---|---|
| Looking up | skeleton summary card + 4 skeleton rows; primary disabled until the answer |
| Not found | `.m-banner--error` under the title: **"No order found for {code}"** · "Check the number or scan the label again." Haptic `error`. A product barcode gets the same answer; it is **not** passed on to Scanit |
| Found | haptic `success` |
| Offline | `.m-banner--offline` "Lookups need a connection." The last result stays; a scan gets the toast "Lookups need a connection" |
| Server error | toast "Couldn't look that up. Try again." |
| Wrong role (403; a host after SEC-8) | `.m-empty` only: "Your account can't open this." / "Ask your manager." No action bar |
| Session ended / subscription inactive | tell the shell (bridge "session ended") |
| Demo company | the demo banner |

## Copy (EN / ES)
Look up a label / Buscar una etiqueta · Scan label / Escanear etiqueta · Type the number / Escribir el número · Tracking or order number / Número de rastreo o de pedido · Look up / Buscar · Details / Detalles · Tracking / Rastreo · Picked by / Recogido por · Packed by / Empacado por · Not picked yet / Aún no recogido · Not packed yet / Aún no empacado · Last event / Último evento · Items / Artículos · Packing video / Video de empaque · Play packing video / Ver video de empaque · No video yet — this order hasn't been packed. / Aún no hay video — este pedido no se ha empacado. · The video hasn't arrived yet. Check again in a minute. / El video aún no llega. Revisa en un minuto. · Loading video… / Cargando video… · The video stopped. / El video se detuvo. · Try again / Reintentar · No order found for {code} / No se encontró pedido para {code} · Lookups need a connection. / Las búsquedas necesitan conexión. · Open in Pick / Abrir en Recoger · Pack this order / Empacar este pedido · Copied / Copiado. Status words: DESIGN_SYSTEM §4. Spanish is a first draft.

## Components
`.m-screen--has-actionbar` `.m-navbar` `.m-navbar__back` `.m-largetitle` `.m-banner` `.m-empty` `.m-card` `.m-pill--*` `.m-section` `.m-list` `.m-row` `.m-row--lead` `.m-row__value` `.m-skeleton` `.m-btn--secondary` `.m-actionbar` `.m-actionbar__aux` `.m-toast`. Screen-local prefix `tr-`.

## Bridge
`scan()` · `haptic()` · `openTab('pick')` · `pack(code)` · session ended.

## Assumptions — to be confirmed by their owners
- **N10:** the lookup answer (or one read-only companion call) tells a permitted account whether a video exists and gives a playable link, and tells a worker nothing about it. Today the answer carries no video field (by reading `api_shipment_lookup`), and `/media/video/<file>` redirects to a storage host. → programmer, security-reviewer.
- **Video format:** videos are served as `.mp4` or `.webm` (`serve_v`). Whether an iPhone plays the `.webm` ones recorded at browser stations was not checked; the "can't be played on this phone" state exists for that. → mobile-qa on a device.
- **SEC-8:** the page reads named fields (status, show, buyer name, items, picked/packed by and when, events, platform, tracking), not the whole order row, and never an address.
- "Open in Pick" only switches tabs: `openTab` takes a tab id, so the label is scanned again there. If the bridge later accepts a path inside the tab, this row can open `/m/pick?order=…` directly (which `/m/pick` already understands).

## Acceptance
Passes DESIGN_SYSTEM §6.3 for worker, cs, manager, admin. A worker's page contains no video element, row or text about a video. No link to `/admin/track`, `/pick` or any desktop path.
