# My Schedule — `/my-schedule` · `MYSCHEDULE_HTML`

**User:** a worker checking upcoming shifts.
**Purpose:** see the next shifts the manager published.

## What changes vs. today (`audit/…/pro/worker/my-schedule.png`)
- "🗓️ My Schedule  Ana Picker" and an 11px grey sentence → large title "My Schedule", subtitle "Published by your manager".
- Empty → `.m-empty` (calendar icon) "No shifts published yet" / "Check back after your manager approves the week."

## Layout at 390pt
1. Nav bar `‹ More`. Large title.
2. **Next shift** hero (`.m-card--hero`): "Next shift" eyebrow, "Thu, Nov 6" (Title 2), "9:00 AM – 5:00 PM · 8 h", role/station pill, and a secondary white button "Add to Calendar" (app: creates an `.ics` and opens it with native EventKit; browser: `.ics` download).
3. **This week / Next week** sections: `.m-list` rows per day with a leading date block (weekday 12/700 uppercase muted, day number Title 3), title = time range, sub = station / notes, trailing = hours. Days off are shown as a muted "Off" row so the week reads complete.

## States
Loading skeleton · Error banner · Offline: last fetched schedule + banner "Last updated {time}".
