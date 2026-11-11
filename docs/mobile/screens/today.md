# Today — `/m/today` (launch screen, tab 1, every role)

**Blueprint:** S3, §2 (launch screen), flows 4.3, 4.5, 4.6, 4.8, 4.9, rules 5.1, 5.5, 5.8. **Release: 1.0.**
**Mockup:** [`../mockups/today.html`](../mockups/today.html) → `today-worker.png`, `today-host.png`, `today-manager.png`, `today-worker-dark.png`
**Data:** `GET /api/today` (role-aware), `GET /api/me/stats` (my packed today), `GET /api/pick/my-stats` (my picked today; only for accounts with `can.pick`), capabilities and `sandbox` from the session (blueprint N3).
**User:** everyone, at the start of a shift and between tasks.
**Purpose:** "What should I do now?" — my numbers, the job I was doing, a label lookup, the floor right now. Managers and admins also see where each open show stands.

Today is a **tab root**: no back button. It has **no sticky action bar** — the primary jobs are tabs. It contains **no link to a desktop page**, no "For you" rows (onboarding, news, schedule, documents) and no leaderboard link: those screens are not in 1.0 and Today shows only what exists (blueprint §6: no "coming soon").

## Layout at 390pt — shared frame
1. **Nav bar** (`.m-navbar`, root). Inline title "Today". Trailing: avatar (`.m-avatar`, initials, `aria-label` "Account") → `openTab('account')`.
2. **Large title** "Good {morning|afternoon|evening}, {first name}". Subtitle "{Weekday}, {Mon D} · {company name}".
3. **Demo banner** when `sandbox` (`.m-banner--warn`): "Demo company — sample data. Nothing here is real or leaves the app."
4. Offline / error banners (see States).
5. The sections of the role's variant, below.

A scan made while Today is in front (Bluetooth scanner, nothing tapped) **is a label lookup**: it opens Track with that code (`/m/track?code=…`, pushed). This holds only for accounts with `can.track`; for a host a scan on Today does nothing but say so (toast "Open Scanit to scan a product").

## Variant: worker (also the demo floor login)
3 sections after the frame:

**A. Hero — "You today"** (`.m-card--hero`, not tappable): eyebrow "YOU TODAY"; two numbers side by side, each 28px/800 with a 13px label: **{packed}** "packed" · **{picked}** "picked". No rank, no team line.

**B. Continue** (`.m-section`, header "Continue"; shown only when there is something to continue): `.m-list`, `.m-row--lead`:
- lead `checklist` · title "Keep picking {show}" · sub "{left} left to pick" · chevron → `openTab('pick')` (Pick already opens on the remembered show).
- The show is the one Pick remembers for this device (`localStorage.pickShow`), shown only if it still has orders to pick. No remembered show → the section is omitted; the Pick tab is one tap away.

**C. Look up** (`.m-section`, header "Look up"): `.m-list`, one row:
- lead `magnifyingglass` · title **"Look up a label"** · sub "Scan or type a tracking or order number" · chevron → Track (`/m/track`, pushed).

**D. Floor now** (`.m-section`, header "Floor now"): `.m-stats` 2 columns — **Orders to pick** (`backlog.orders`) · **Waiting to pack** (`floor.waiting_to_pack`). Under them, when `tables_to_clean` > 0, a `.m-list` row: lead `archivebox` · title "{n} table(s) to clear before picking" · chevron → Table cleanup (`/m/cleanup`, pushed).

Workers do not see the per-show list, issues, or sales.

## Variant: cs
As worker (A–D), plus one row in **C. Look up**, under "Look up a label":
- lead `barcode.viewfinder` · title **"Scanit"** · sub "Scan a product for its price and notes" · chevron → Scanit (`/m/scanit?from=today`, pushed).

## Variant: manager (also the demo second login)
**A. Hero — "The floor today"**: eyebrow "THE FLOOR TODAY"; **{floor.packed_today}** "packed" · **{floor.picked_today}** "picked"; footer line 13px: "{pickers_online} picking · {packers_online} packing now".

**B. Continue** — as worker, when applicable.

**C. Look up** — "Look up a label" and "Scanit" (as cs).

**E. Open shows** (`.m-section`, header "Open shows · {n}", trailing text "Most overdue first"): `.m-list`, one row per show in the server's order (`backlog.shows`), **read-only**:
- title = show name (one line, ellipsis) · sub line 1 = "{date} · {total} orders" · a stacked `.m-progress` (packed / picked / remaining)
- second line of counts, always words + numbers: **"{pending} to pick · {to_pack} to pack"** and, when > 0, `.m-pill--issue` "{n} issue(s)"
- `overdue` > 0 → `.m-pill--cancelled` (red, dash) **"{n} overdue"** before the counts
- Rows are not tappable in 1.0 (there is no show screen on the phone). To act, the manager uses the Pick or Pack tab. No chevron is drawn.
- More than 8 shows: the first 8, then a text button "Show all {n}" that expands in place.

**D. Floor now**: `.m-stats` — Orders to pick · Waiting to pack · **Open issues** (`issues`, `.m-stat--warn` when > 0) · **Tables to clear** (`tables_to_clean`; the tile is a link to `/m/cleanup` when > 0). Four tiles, 2×2.

## Variant: admin
As manager, plus one section after the hero:

**F. Sales today** (`.m-section`, header "Sales today"): `.m-list`, one row, not tappable: title "{sold_today} orders sold" · trailing value "${revenue_today}". (First on the cut list if 1.0 must shrink — blueprint §6.)

The Manage tab is in the tab bar; Today has no row that opens it.

## Variant: host
The host has nothing to pick, pack or look up; her Today shows what exists and gets her to Scanit in one tap.

**A.** No hero numbers. A plain `.m-card` (not the gradient): 22px/800 "Ready for your live?" · 15px muted "Scan each product to see its retail price, our target price and its notes."

**G. Scanit** (`.m-section`, no header): `.m-list`, one row at 64pt:
- lead `barcode.viewfinder` · title **"Open Scanit"** · sub "Scan a product" · chevron → `openTab('scanit')`.

Nothing else: no floor numbers, no shows, no lookup, no "coming soon", no pointer to the website.

## States
| State | Treatment |
|---|---|
| Loading | `.m-skeleton` hero (112pt) + 3 skeleton rows; the frame (title, avatar) is drawn at once |
| First day / zeros | numbers show "0". Worker hero footer: "Your numbers show up here after your first pick or pack." |
| No open shows (manager, admin) | section E shows `.m-empty` inside the list card: "No open shows" / "Shows appear here after the next live is imported." No button |
| Error loading | `.m-banner--error` "Couldn't load today." + Retry. Sections that did load stay |
| Offline | `.m-banner--offline` "You're offline. These numbers may be out of date." The last data stays on screen; rows that need the server (Look up, Scanit) still open and say so themselves |
| 403 on one source | that section is omitted; the rest renders |
| Session ended / subscription inactive | tell the shell (bridge "session ended"); never navigate to `/` or `/billing` |
| Demo company | the demo banner under the title |

Refresh: pull to refresh (native), and a silent re-read when the tab becomes visible again if the data is older than 60 s. No polling while visible.

## Copy
| English | Spanish |
|---|---|
| Good morning / afternoon / evening, {name} | Buenos días / Buenas tardes / Buenas noches, {name} |
| You today | Tú hoy |
| The floor today | El piso hoy |
| packed · picked | empacados · recogidos |
| Continue | Continuar |
| Keep picking {show} | Seguir recogiendo {show} |
| {n} left to pick | {n} por recoger |
| Look up | Buscar |
| Look up a label | Buscar una etiqueta |
| Scan or type a tracking or order number | Escanea o escribe un número de rastreo o de pedido |
| Scanit — Scan a product for its price and notes | Scanit — Escanea un producto para ver su precio y notas |
| Floor now | El piso ahora |
| Orders to pick · Waiting to pack · Open issues · Tables to clear | Pedidos por recoger · Esperando empaque · Problemas abiertos · Mesas por despejar |
| Open shows · Most overdue first | Shows abiertos · Los más atrasados primero |
| {n} to pick · {n} to pack · {n} overdue | {n} por recoger · {n} por empacar · {n} atrasados |
| Sales today | Ventas de hoy |
| Ready for your live? | ¿Lista para tu live? |
| Open Scanit — Scan a product | Abrir Scanit — Escanear un producto |
| Demo company — sample data. Nothing here is real or leaves the app. | Empresa de demostración — datos de ejemplo. Nada aquí es real ni sale de la app. |

Spanish is a first draft. "Ready for your live?" is gendered in Spanish (Lista / Listo); use a neutral form if a reviewer prefers ("¿Todo listo para tu live?").

## Components
`.m-screen` `.m-navbar` `.m-avatar` `.m-largetitle` `.m-banner--warn|--error|--offline` `.m-card--hero` `.m-card` `.m-section` `.m-list` `.m-row--lead` `.m-progress` (`__a` packed, `__b` picked) `.m-pill--issue` `.m-pill--cancelled` `.m-stats` `.m-stat` `.m-stat--warn` `.m-skeleton` `.m-empty`. Screen-local classes prefix `td-`.

## Bridge
`openTab('pick' | 'scanit' | 'account')` · scans through `M.onScan` (→ Track). In a browser (no bridge): the Pick and Scanit rows are ordinary links to `/m/pick` and `/m/scanit`; the avatar is not drawn.

## What the spec needs from the server (not all of it exists — see the hand-off)
- Per show: **to pack** and **issues**. `/api/today` → `backlog.shows[]` carries `pending`, `packed`, `total`, `overdue`, but not the picked-not-packed count or an issue count per show; `issues` is one number for the company. Until it does, the row shows "{pending} to pick · {packed} of {total} packed" and the issue pill is omitted from rows (the company total stays in Floor now).
- `/api/today` lists only shows that still have orders **to pick**; a show that is fully picked but not packed drops off "Open shows". The row design assumes it should stay until packed.
- Whether a **worker or host** should receive `backlog.shows` at all (today every signed-in role does). This spec does not draw it for them either way.
- `current_show` in `/api/today` is the show last *packed*, not the show this person is *picking*; the Continue row therefore uses Pick's remembered show.

## Acceptance
Passes DESIGN_SYSTEM §6.3 for all five roles. No element links to `/home`, `/me`, `/leaderboard`, `/onboarding`, `/announcements`, `/my-schedule`, `/documents`, `/scanit` or any other desktop path. Worker at 390pt: hero, Continue and "Look up a label" are visible without scrolling.
