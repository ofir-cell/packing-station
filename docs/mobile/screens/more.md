# More (tab 5, all roles) — native SwiftUI list in the app · web fallback `/more` (new `MORE_HTML`)

**User:** anyone looking for a screen that isn't a tab.
**Purpose:** replace the web sidebar with an iOS-style list. The content comes from `/api/mobile/nav` → `more` (see DESIGN_SYSTEM §3.2–3.4).

## Layout at 390pt (worker)
1. Large title "More".
2. **Profile row** (its own inset group, 72pt): 52pt gradient avatar with initials · name (Headline) · "Warehouse Associate" (subhead) · chevron → `/me`.
3. **Work**: Live Mode · Match Products · Table Cleanup
4. **Me**: My Schedule · Leaderboard · Documents (trailing count of items to sign) · Onboarding (trailing "3 of 5")
5. **Help**: News (trailing unread dot plus count) · Guides
6. **App**:
   - Appearance → a pushed native list: Mode (System / Light / Dark, checkmarks) and Theme (Classic, Taupe & Teal, Sage & Stone, Slate & Blush, each with its two-dot swatch). Writes `localStorage.lohubMode` / `siteTheme` through the bridge `evaluateJavaScript` on all tab WebViews.
   - Language → English / Español (sets `localStorage.lang`, reloads WebViews)
   - Sign out → action sheet: "Sign out of LiveOpsHub?" [Sign out] (destructive) [Cancel]
7. Footer: "LiveOpsHub {version} · {company}" (footnote, centered).

Every row: 44pt minimum, a leading 29pt rounded-square icon tile tinted per section (brand for Work, teal for Me, orange for Help, gray for App), title, trailing chevron. Manager and admin get more sections (listed in DESIGN_SYSTEM §3.4). Admin and cs get a `.searchable` field ("Search orders, people, pages") wired to `/api/search`.

## Web fallback `/more` (Mobile Safari <600px)
The same structure with `.m-largetitle`, `.m-section`, `.m-list` and `.m-row--lead`. Appearance and Language are inline `.m-seg` controls. Sign out is a `.m-btn--destructive` that opens a `.m-sheet` confirm.

## States
Nav config failed to load: the native list shows the last cached config. If there's none, "Couldn't load your menu" + Retry.
