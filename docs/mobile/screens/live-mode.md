# Live Mode — `/admin/live` · `LIVE_HTML`

**User:** a worker or live assistant after a live, at the table with products and stickers.
**Purpose:** a guided flow that connects each product on the table to the sticker numbers that actually sold.

## What changes vs. today (`audit/…/pro/worker/admin__live.png`)
- "🔴 Live Mode  Ana Picker" + an 11px description → large title "Live Mode", subtitle "Match the table to what sold".
- Step 1 is a card with a native `<select>` "Pick a live…" and a black "Next" button → the step becomes a **list of lives to choose from** (`.m-list` rows: show name, sub "{platform} · {n} sold · {date}", trailing `.m-pill--live` if live now, or "{n} to match"). Tapping a row moves to step 2. No select, no extra "Next" tap.
- The black (#111827) primary button is off-brand → gradient `.m-btn--primary`.

## Flow (each step is a pushed screen with a step indicator "Step {n} of 3" as the eyebrow)
1. **Choose the live** (above).
2. **Scan products**: the hero shows the current sticker # (Title 1 numeral in a brand tile) and "{sold} sold in this live". The primary action bar button is "Scan product" → `scan()`. The auxiliary keyboard button opens a search sheet (catalog search by name, SKU or barcode digits). On a match: haptic `success`, the sticker advances, and the toast reads "#12 → KAY-VAN28". The "Waiting to match" list below shows the remaining sticker numbers as rows (tap one to jump to it).
3. **Review**: a list of matched rows (sticker #, product, qty) plus a "Bulk range" entry (sheet: From # / To # / Scan product → Apply). Primary "Finish".

## States
No lives: `.m-empty` "No lives to match" / "Lives show up here after they end." · Scan not found: sheet "We don't know this barcode" with "Search catalog" / "Skip".

Note: `/admin/match-live` (LIVE_MATCH_HTML) is hidden from the menu (the guided Live Mode replaces it) but is reachable for workers. It gets the global layer only; it is not in the worker nav.
