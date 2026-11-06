# Track (worker tab 4) — `/admin/track` · `TRACK_HTML` (data: `/api/shipment/{code}`)

**User:** worker holding a package or label who needs to know which show or order it belongs to, and its status, before opening anything. Managers and admins use it from More.
**Purpose:** scan or type a tracking number and see the show, the buyer, the status, and who picked and packed it.

## What changes vs. today (`audit/…/pro/worker/admin__track.png`)
| Today | New |
|---|---|
| **+30px horizontal overflow**: the input and the "Find" button sit side by side, with the button ending at x=423 | stacked: a full-width search field with an inline scan button, plus the sticky primary action |
| 🔎 emoji title and an 11px tip about barcode scanners | large title "Track", 15px subtitle |
| empty white page below the field | a "Recent lookups" list (today's log, which already exists as `logBody`) with an empty state |
| pink 13px placeholder input | 17px `.m-search` |

## Layout at 390pt
1. Nav bar (root for worker). Trailing: "Clear" text button (only when there's history) → action sheet "Clear recent lookups?" [Clear] [Cancel].
2. Large title "Track". Subtitle "Scan a label to see which show it's from."
3. **Search field** `.m-search` (type=search, `inputmode=text`, `autocapitalize=characters`, placeholder "Tracking or order number"), with a trailing `.m-search__scan` (barcode icon, app only). Enter → lookup. A USB scanner works because the field is focused on load (iPad only; not on phones, where it would pop the keyboard).
4. **Result card** (after a lookup, `.m-card`, inserted above the list and animated in):
   - Row 1: status pill (`pending|picked|packed|shipped|cancelled|issue`) + platform pill
   - Title: show name (Headline) · sub: "{buyer} · {n} items"
   - Key/value list (`.m-list` inside the card): Tracking (monospace, tap to copy, toast "Copied") · Picked by · Packed by · Last event + time
   - Actions: in the app, primary `.m-btn--secondary` "Pack this order" → `LOHubNative.pack(track)` (only when status is picked). Plain button "Open in Pick" → `/pick?order=…` (when pending).
   - Haptic `success` when found; `error` and the card variant `m-banner--error` "No order found for {code}. Check the number or scan again." when not found.
5. **Section "Recent lookups"** (`tally` → section header "Today · {n}"): `.m-list` rows: title = buyer, sub = show · time, trailing = status pill. Tap → shows that result card again.
6. **Sticky action bar** (app only): primary "Scan label" → `scan()` → lookup. In the browser, no action bar; the field is the action.

## States
Empty history: `.m-empty` with a magnifier icon, "Scan a label to start", "Each lookup is listed here until midnight." · Loading lookup: the result card as a skeleton · Offline: banner "You're offline — lookups need a connection."

## Components
`.m-navbar` `.m-largetitle` `.m-search` `.m-search__scan` `.m-card` `.m-pill--*` `.m-list` `.m-actionbar` `.m-empty` `.m-skeleton` `.m-toast`.
