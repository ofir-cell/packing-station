# Sign-in screens — `/login` (`LOGIN_HTML`), `/badge-login` (`BADGE_LOGIN_HTML`), `/welcome` (`WELCOME_HTML`)

**User:** a worker starting a shift (badge), an admin or manager (username/password), and anyone on first launch of the app.
**Purpose:** get signed in fast; workers by badge.

Note: the audit's `login.png` is the Pick screen because the harness was already signed in (`/login` → `/pick`). These specs are from `badge-login.png`, `welcome.png` and the templates.

## In the app: launch → sign in
The app opens on the native sign-in (existing `APIClient` login) **or** `/badge-login` in a full-screen WebView with **no tab bar**. The tab bar appears only after sign-in.

## Badge login (`/badge-login`), at 390pt
- The current screen is close to right: logo tile + "5 SEC Employee sign-in", "Welcome!", "Scan your employee badge to begin", a dashed scan box, and the "Use username & password instead" link. Fixes:
  - The "ES" pill (top right, 1 small target) → a 44pt `.m-iconbtn` in the nav-bar position, under the safe area.
  - The dashed box becomes a **button** in the app: "Scan badge" (primary, 52pt) → `LOHubNative.scan()` (already wired in templates.py:2359). Keep the dashed "Ready to scan" box only when a hardware scanner is attached (iPad station).
  - The "Use username & password instead" pill → `.m-btn--plain` 44pt.
  - Wordmark sub "EMPLOYEE SIGN-IN" at 8px → 12px floor (G3).
- Error: haptic `error`, field shake, "Badge not recognized. Try again or ask your manager." under the box.

## Username/password (`/login`)
`.m-field`s (Username: `autocomplete=username`, `autocapitalize=none`; Password: `autocomplete=current-password` with a show/hide eye button 44pt), primary "Sign in", plain "Sign in with badge". Errors under the field, never `alert()`. Keyboard: Return on the password field submits.

## Welcome (`/welcome`, after badge login on shared devices)
The two big cards (Start Picking / Start Packing) are good for iPad stations. In the app this screen is **skipped**: the user lands on the Today tab, because the tabs already offer Pick and Pack. In browsers: keep it, apply the layer, and make the cards' "Open picker →" links full-card tap targets (the whole card is the `<a>`).
