# Leaderboard — `/leaderboard` · `LEADERBOARD_HTML`

**User:** workers (motivation); managers check it too.
**Purpose:** ranking by packages packed or orders picked for a period.

## What changes vs. today (`audit/…/pro/worker/leaderboard.png`)
- 🏆 emoji title → large title "Leaderboard", subtitle "Ranked by packages completed".
- Two stacked button groups (Packers/Pickers, then Today/This week/This month/All time) with 31pt items → **two `.m-seg`**: `Packers | Pickers`, then `Today | Week | Month | All`.
- Empty text centered in grey → `.m-empty` (trophy icon) "No one's on the board yet" / "Pack or pick an order to get started." with a button "Go to Pick" (opens the Pick tab via `LOHubNative.openTab('pick')`, or the `/pick` link in browsers).

## Layout at 390pt
1. Nav bar (pushed from More: `‹ More`). Large title + subtitle.
2. Segmented controls (16pt gutter, 12pt between them).
3. **Podium card** (when ≥3 people): the top 3 side by side with avatars 56/64/56pt and the count under each; 1st place gets the gradient ring.
4. `.m-list` ranks 4+: leading rank number (Title 3, muted, 28pt wide), avatar 32pt, name, trailing count (`.m-row__value`) + "packed"/"picked".
5. **Me row** pinned above the tab bar if I'm not visible: "You · #{rank} · {count}" with a brand tint background (sticky, `.m-actionbar` styling without buttons).

## States
Loading skeleton (podium + 5 rows) · Empty (above) · Error banner + Retry.
