> **Not in 1.0 — waits for 1.1; back button and entry point to be re-specified then.** Blueprint §3.2: 1.1, first. Until it is taken up, nothing below is built; paths, `‹ More` back buttons, badges and "language is in More" in this file are out of date (APP_BLUEPRINT §3.2, §8.2).

# News (Team announcements) — `/announcements` · `ANNOUNCEMENTS_HTML`

**User:** all employees. Managers and admins also post here (the composer is specified in the manager round).
**Purpose:** read updates from management; acknowledge the ones that require it.

## What changes vs. today (`audit/…/pro/worker/announcements.png`)
- 📣 emoji title "Team News" → large title **"News"** (matches the menu label), subtitle "Updates from your managers".
- The empty state is a grey box with a 72px emoji → `.m-empty` (megaphone icon tile) "No news yet" / "Announcements from your managers will show up here."

## Layout at 390pt
1. Nav bar `‹ More`. Large title.
2. **Pinned** section (if any): `.m-card` per post, with a brand left rule 3px, a "Pinned" `.m-pill--brand`, title (Headline), body (Body, clamped to 4 lines + "More"), and the author avatar, name and relative time in the footer.
3. **Recent**: the same card without the pin. Unread posts get an 8pt brand dot before the title.
4. Posts that require acknowledgement: in-card `.m-btn--secondary` "Got it" → becomes a "✓ Acknowledged {time}" footnote; haptic `success`.

## Behavior
Opening the screen marks posts as read and clears the More/News badge. Images inside posts are full width (radius 12) and open in a native preview.

## States
Loading: 2 skeleton cards · Error banner · Offline: cached posts plus the offline banner.
