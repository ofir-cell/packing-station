# Today (tab 1, all roles) — `/home` · `HOME_HTML` (data: `/api/today`)

**User:** worker at the start of a shift and between tasks. Managers and admins get the same screen with their sections (manager/admin specs follow later).
**Purpose:** "What should I do now?" It shows my numbers, the job I was doing, and anything I've been asked to do (onboarding, news, next shift).

## What changes vs. today (`audit/…/pro/worker/home.png`)
| Today | New |
|---|---|
| ☰ / ← Back / 🏠 bar (none of them 44pt-clean); grey shadow on the left | no web chrome (G9). This is a tab root |
| "GOOD EVENING / Hello, Ana Picker" plus a lone "0 PACKED TODAY" card | Large title "Good evening, Ana" plus a hero card with **Packed** and **Picked** today and the rank |
| 4 big emoji tiles (Back to packing, Picking, Leaderboard, My profile) that duplicate navigation | removed. Those destinations are tabs or More. Replaced by "Continue" and "For you" sections |
| 20 small targets, 10 tiny texts | 0 / 0 |

## Layout at 390pt
1. Nav bar (root): trailing avatar → `/me`.
2. Large title: "Good {morning|afternoon|evening}, {first name}". Subtitle: "{Weekday, Mon D} · On shift since {time}" (or "Not clocked in" when unknown, hidden if there's no data).
3. **Hero card** (`.m-card--hero`): two numbers, **{packed_today}** "packed today" and **{picked_today}** "picked today", plus a third, "#{rank}" "on the leaderboard" (tap → `/leaderboard`). Footer line: "Team: {packed} of {total} orders out today" with a white progress bar (`pct`).
4. **Continue** (`.m-section`, shown if `current_show` exists): one `.m-list` row, lead icon `checklist`, title "Keep picking {show}", sub "{left} left · you picked {n}", trailing chevron → `/pick`. A second row appears if Pack has an unfinished session: "Resume packing" → native Pack.
5. **For you** (only rows that apply, max 4):
   - Onboarding: "{done} of {total} onboarding steps done" + progress → `/onboarding`
   - News: "{n} new announcement(s)" → `/announcements` (the unread dot is the badge)
   - Next shift: "{Day} {start}–{end}" → `/my-schedule`
   - Documents to sign: "{n} documents to sign" → `/documents`
6. **Floor now** (`.m-stats` 2-col): Orders to pick (`pending`) · Packers online (`packers_online`). Workers see these two only.

No action bar on this screen. The primary jobs are tabs.

## States
- Loading: skeleton hero plus 2 skeleton rows.
- First day (no numbers yet): the hero shows "Welcome, {name}" and "Your numbers show up here after your first pick or pack." "For you" leads with Onboarding.
- Error: `m-banner--error` "Couldn't load today. Pull down to try again."
- Offline: `m-banner--offline` "You're offline — numbers may be out of date."

## Copy
"Good evening, Ana" · "packed today" · "picked today" · "on the leaderboard" · "Keep picking Peach LIVE · Nov 5 Evening" · "3 of 5 onboarding steps done" · "Next shift Thu 9:00–5:00".

## Components
`.m-largetitle` `.m-card--hero` `.m-section` `.m-list` `.m-row--lead` `.m-progress` `.m-stats` `.m-skeleton` `.m-banner`.
