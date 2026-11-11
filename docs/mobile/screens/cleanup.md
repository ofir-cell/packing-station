# Table cleanup — `/m/cleanup` (data: `GET /api/cleanup/shows`, `GET /api/cleanup/{show}`, `POST /api/cleanup/{show}/mark`, `POST /api/show/cleanout`)

**Blueprint:** S5, flow 4.3 step 3, rule 5.8, pieces N7, N9. **Release: 1.0.**
**Mockup:** not drawn in this round.
**User:** a worker before picking a show starts; also cs, manager, admin. A host has no access.
**Purpose:** pull cancelled items off the warehouse table, show by show, and confirm a new show's table is cleared so picking can start.

## How it is entered
| From | Opens | Back button |
|---|---|---|
| **Pick**, a show whose cancelled items are not all pulled (`cleanup_blocked`, or the queue row's "to clear" state) | `/m/cleanup?show={name}` — that show's detail, pushed in the Pick tab | "Pick" |
| **Pick**, a new show whose table must be cleared first (`cleanout_required`, or the queue row's "Clean table" state) | `/m/cleanup?show={name}&prepick=1` — the same detail | "Pick" |
| **Today**, the "tables to clear" row or tile | `/m/cleanup` — the list of shows, pushed in the Today tab | "Today" |

These replace the three jumps `/m/pick` makes today to the desktop `/admin/cleanup` (blueprint N7). There is no other entry, and the page links to no desktop page.

## Layout at 390pt — list of shows (`/m/cleanup`)
1. Nav bar: `.m-navbar__back` "Today". Inline title "Table cleanup".
2. Large title "Table cleanup". Subtitle "Pull cancelled items before picking."
3. Demo banner when `sandbox`.
4. **To clear** (`.m-section`, header "To clear · {n}"): `.m-list`, one row per show with `groups_pending` > 0 — title = show name · sub = platform pill + "{shipments} orders" · a 4px `.m-progress` (`groups_done` / `total_groups`) · trailing big number "{groups_pending}" + "to pull" + chevron → that show's detail.
5. **Nothing to pull** (`.m-section`, header "Nothing to pull · {n}", collapsed by default; tap the header to expand): the other shows, each with `.m-pill--shipped` "Clean". Not tappable.

No action bar on the list.

## Layout at 390pt — one show (`/m/cleanup?show=…`)
1. Nav bar: back "Pick" (entered from Pick) or "Table cleanup" (entered from the list). Inline title = show name.
2. Large title = show name (2 lines max). Subtitle "{groups_done} of {total_groups} pulled".
3. `.m-progress` (6px) with `role=progressbar` and the same words as its label.
4. **Items to pull**, grouped by Part (`.m-section` per part, header "Part 1", "Part 2", … or "No part"): `.m-list`, one row per (SKU, part) group, at least 64pt:
   - leading 28pt check circle (the `pk-check` look from Pick) · title = product name (2 lines) · sub = "{SKU} · {order_count} order(s)" · trailing **"×{total_qty}"** (the number of pieces to take off the table; amber when > 1).
   - Tapping the whole row toggles "pulled" (`POST …/mark`, haptic `tap`). The row shows as pulled **only after the server said so**; a failed toggle reverts with the toast "Couldn't save that. Try again." Pulled rows dim to 55% and show "Pulled by {name} · {time}" as the sub line. Tapping again un-marks.
5. **Sticky action bar** — one primary:
   - items still to pull → disabled **"Pull every item first"**.
   - all pulled (or the show has none) → **"Table cleared — start picking"** → `POST /api/show/cleanout` for this show → haptic `success`, toast "Table is clean" → back to where the person came from: Pick opens this show (`/m/pick?show={name}`); from the list, `openTab('pick')` after returning the list to its updated state.
   - Shown for every show's detail, not only with `prepick=1`, so a worker who came through Today can finish and go on to pick (this is what the desktop page does).

## States
| State | Treatment |
|---|---|
| Loading | 3 skeleton rows |
| All tables clean (list) | `.m-empty`: check icon · "Tables are clean" · "No cancelled items to pull. You can start picking." · button "Go to Pick" → `openTab('pick')` (in a browser: a link to `/m/pick`) |
| Show has no cancelled items (detail) | `.m-banner--ok` "No cancelled items for this show." The action bar offers "Table cleared — start picking" |
| Show not found / too old | `.m-banner--error` "That show isn't open any more." + back |
| Offline | `.m-banner--offline` "You're offline. Reconnect to mark items." Rows are not tappable while offline; nothing is queued |
| Error loading | `.m-banner--error` "Couldn't load the table." + Retry |
| Wrong role (403) | `.m-empty`: "Your account can't open this." / "Ask your manager." |
| Session ended / subscription inactive | tell the shell (bridge "session ended") |

Two people may clear the same table: the detail re-reads the show when the page becomes visible again and every 20 s while it is open, so a row someone else pulled shows as pulled.

## Copy (EN / ES)
Table cleanup / Limpieza de mesa · Pull cancelled items before picking. / Retira los artículos cancelados antes de recoger. · To clear / Por despejar · to pull / por retirar · Nothing to pull / Nada que retirar · Clean / Limpia · {x} of {n} pulled / {x} de {n} retirados · Part {n} / Parte {n} · Pulled by {name} / Retirado por {name} · Pull every item first / Retira todos los artículos primero · Table cleared — start picking / Mesa despejada — empezar a recoger · Table is clean / La mesa está limpia · Tables are clean / Las mesas están limpias · Go to Pick / Ir a Recoger. Spanish is a first draft.

## Components
`.m-screen--has-actionbar` `.m-navbar` `.m-navbar__back` `.m-largetitle` `.m-section` `.m-list` `.m-row` `.m-progress` `.m-pill--shipped` `.m-pill--brand` `.m-banner--ok|--error|--offline` `.m-empty` `.m-skeleton` `.m-actionbar` `.m-btn--primary` `.m-toast`. Screen-local prefix `cu-`; the check circle reuses Pick's look.

## Bridge
`haptic()` · `openTab('pick')` · session ended.

## Notes for the builders
- The cancelled items are **groups** — one row per SKU and Part with a total quantity and an order count — not one row per sticker and buyer as the Nov 5 draft said. That is the shape `/api/cleanup/{show}` returns.
- `POST /api/show/cleanout` is the call behind "Table cleared — start picking" on the desktop page; the blueprint's data list for S5 does not name it. By reading, it accepts admin, cs, picker and worker (a manager through the server's manager → admin rule) and takes the show name in the JSON body as `label`.

## Acceptance
Passes DESIGN_SYSTEM §6.3 for worker, cs, manager, admin. After this page exists, `/m/pick` contains no `/admin/cleanup` URL.
