> **Not in 1.0 — waits for 1.1; back button and entry point to be re-specified then.** Blueprint §3.2 lists this screen as "later" (after 1.1). Until it is taken up, nothing below is built; paths, `‹ More` back buttons, badges and "language is in More" in this file are out of date (APP_BLUEPRINT §3.2, §8.2).

# Match Products (pre-show) — `/admin/preshow` · `PRESHOW_HTML`

**User:** a worker preparing the table before a live, often several people in parallel "lanes" (Parts).
**Purpose:** for each sticker number, scan the real product barcode so sales map to SKUs.

## What changes vs. today (`audit/…/pro/worker/admin__preshow.png`)
- The page is 3 long cards with uppercase blue 13px headings, two side-by-side selects plus a number field, a disabled-looking scan area, a "Search catalog" grey button, a bulk card and a 4-column table (22 small targets, 22 tiny texts) → **a setup sheet plus one focused scanning screen**:
- "ES" grey button at the top right → language is in More (and the nav-bar chip like Pick).

## Layout at 390pt
**Setup** (first visit or "Change" tapped): a bottom sheet "Set up matching" with three `.m-field`s: Show (a list picker row → pushed list), Your lane (`.m-seg` None | 1 | 2 | 3 | 4), and Start at sticker # (number, 16px+). Help text: "Each lane is separate — several people can match at once without clashing." Primary "Start matching".

**Matching screen:**
1. Nav bar: back + inline title "Match Products". Trailing "Change" (reopens setup) and "…" (Bulk range, Search catalog).
2. Summary line (subhead): "{show} · Lane {n}".
3. **Sticker hero**: a big centered tile with "STICKER" eyebrow and the number at 64px/800 in `--brand-ink` on `--brand-glow`, with ‹ › stepper buttons (44pt) on both sides to correct the number.
4. Last match card: product thumbnail 48pt, name, SKU, "#{n} matched by {you}", undo (plain button, 10 s).
5. Section "Matched this show · {n}": `.m-list` rows (sticker #, product, lane, by), newest first. Replaces the 4-column table.
6. **Action bar**: primary "Scan barcode" → `scan()`; auxiliary keyboard button → search sheet (catalog search by name, SKU or barcode digits). A USB scanner types into the hidden focused input as today.

## Feedback
Match → haptic `success`, the sticker advances, and the hero briefly flashes green. Unknown barcode → haptic `error` and a sheet "No product with barcode {code}" with [Search catalog] [Skip sticker].
