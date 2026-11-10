# My Profile — `/me` · `ME_HTML`

**User:** any employee. Reached from the avatar in the nav bar or from the More profile row.
**Purpose:** my numbers, my achievements, recent packages, account and privacy (account deletion is **required by App Review 5.1.1(v)**, so keep it and make it findable).

## What changes vs. today (`audit/…/pro/worker/me.png`)
The structure is already right (header, numbers, achievements, recent, delete). Changes:
- Remove the ☰ / Back / 🏠 bar (G9). Pushed screen: `‹ More` (or `‹ Back`) and the inline title "Profile".
- Header card: keep the gradient avatar; make it a centered iOS profile header (72pt avatar, name in Title 2, role pill `.m-pill--brand`, "Member since {Mon YYYY}").
- "YOUR NUMBERS" → `.m-section` "Your numbers" + `.m-stats` (Today · This month · All time · Days worked). Drop the "—" placeholders; show "0" with a `.m-stat__delta` "vs. last month" when there's data, and nothing otherwise.
- Achievements: a horizontal `.m-stats--scroll` of 5 badges, 96pt each: earned in color, locked grayscale at 45% with a lock glyph and "{n} to go".
- Recent packages: `.m-list` (buyer · show · time, trailing `.m-pill--packed`). Empty: "No packages yet. Your last 20 packs show up here."
- **Account & privacy** section, moved **above** "Delete" as list rows: Two-factor authentication (exists in ME_HTML today: QR enrollment moves to a pushed screen; the QR is centered at 200pt with the manual key below it, tap to copy) · Privacy policy → `/privacy` · Terms → `/terms`. Then a separate group with a single destructive row **"Delete account"** → pushed confirm screen: an explanation (current copy), a type-to-confirm field "Type DELETE", and a destructive button "Delete my account". Haptic `warning` on open.
- The 2 JS errors on this page in the audit must be gone (mobile-qa).

## Components
`.m-navbar` `.m-card` `.m-pill--brand` `.m-stats` `.m-stats--scroll` `.m-list` `.m-row` `.m-btn--destructive` `.m-field` `.m-empty`.
