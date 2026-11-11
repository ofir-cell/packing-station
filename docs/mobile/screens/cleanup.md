# Table Cleanup — `/admin/cleanup` · `CLEANUP_HTML`

**User:** a worker before picking starts.
**Purpose:** pull cancelled items off the warehouse table, show by show.

## What changes vs. today (`audit/…/pro/worker/admin__cleanup.png`)
The structure is close: cards per show with a green progress bar and "0/0". Fix:
- The 🧹 emoji title → large title "Table Cleanup", subtitle "Pull cancelled items before picking".
- The "NO CANCELLATIONS" 10px uppercase grey tag → `.m-pill--shipped` "Nothing to pull" (green, done state) or `.m-pill--cancelled` "{n} to pull".
- "0/0" with a full green bar for shows that have nothing to do is confusing → those shows go into a collapsed **"Nothing to pull · {n}"** section at the bottom; the main list shows only shows with cancellations.
- Rows: `.m-list` (show name · "{platform} · {n} orders" · trailing big count "{left}" + "to pull" · chevron).

## Show detail (pushed)
Large title = show name. A progress bar "{done} of {n} pulled". `.m-list` of cancelled items: leading 28pt check circle, product name, sub "Sticker #{n} · {buyer}", trailing bin/table. Tapping the row toggles "pulled" (haptic `tap`). Action bar: primary "Done — all pulled" (enabled when all are pulled; haptic `success`, then returns to the list with a toast).

## States
All clean: `.m-empty` with a check icon, "Tables are clean", "No cancelled items to pull. You can start picking." and a button "Go to Pick".
