# Sign-in and two-step verification — native (S1, S12) and the system states around them (S11)

> **Re-specified 2026-11-10** on Ofir's decisions of that day, relayed by the lead session: two-step verification is required for **admin, manager and cs**; the second step is **a code sent by email, or the authenticator app** — the person chooses; the person enters and confirms **their own email address** in the native set-up screen. Where `APP_BLUEPRINT.md` still describes another delivery method for the code, read "email code": this file follows the later decision, and app-planner is correcting the blueprint. The Nov 5 version of this file (web `/login`, `/badge-login`, `/welcome`) is withdrawn: none of those pages is shown in the app.

**Blueprint:** S1, S11, S12, flows 4.1, 4.2, rules 5.2, 5.6, 5.10, 5.11, pieces N1, N3, N4, N13, N14. **Release: 1.0. Native SwiftUI — owner: ios-engineer.**
**Mockup:** [`../mockups/sign-in.html`](../mockups/sign-in.html) → `sign-in.png` (a web approximation of native screens: it shows layout, order and copy, not exact system controls).
**User:** everyone, on first launch and whenever the session has ended. Floor workers often share a device and sign in by badge; admins, managers and customer service use a password and a code.
**Purpose:** get the right person in quickly; make the second step understandable; never show a desktop page.

Common rules for every screen here: no tab bar (it appears only after sign-in). LiveOpsHub indigo, light and dark by the system setting. English and Spanish (default: the device language; there is no language control before sign-in). Text fields ≥ 17pt; buttons ≥ 50pt high; everything reachable with the keyboard up. No camera or notification prompt appears until the person taps "Scan badge".

---

## 1. Sign-in (S1)

### Layout at 390pt, top to bottom
1. **Logo** — the LiveOpsHub mark, 64pt, and "Live Ops Hub" (Title 2). No company name: the company is not known yet.
2. **Username** — `textContentType(.username)`, no autocapitalisation, no autocorrect; Return moves to Password.
3. **Password** — secure field with a show/hide eye button (44pt, labelled "Show password" / "Hide password"), `textContentType(.password)`; Return submits.
4. **Sign in** — full-width gradient button (52pt). Disabled until both fields have text; shows a spinner while the request runs.
5. **Error line** — under the button, red, with an icon; see States.
6. Divider "or".
7. **Scan badge** — full-width secondary button with the `barcode.viewfinder` symbol → the camera scan sheet (S10). Footer under it: "For warehouse floor accounts." A Bluetooth/USB scanner also works on this screen with nothing tapped: a scan here means "badge" (blueprint rule 5.1).
8. **Legal footer**, pinned to the bottom above the home indicator: "Privacy Policy · Terms of Use" — two links (44pt tall each), opening liveopshub.com in an in-app browser sheet. Then "Live Ops Hub {version}" in footnote.

There is no "create account", no price, no link to buy and no "forgot password" in 1.0 (an admin resets passwords on the web); the error text says whom to ask.

### What happens next
| Server answer | Next |
|---|---|
| signed in | the shell reads the session, builds the tabs, opens **Today** |
| second step needed | §2 |
| signed in, set-up required (`must_setup_2fa`) | §3 "Set-up required" |
| demo (sandbox) company | straight to Today. **Never a code step, never an email** |

### States
| State | Treatment |
|---|---|
| Wrong username or password | "That username or password isn't right." The password field is cleared and focused. Error haptic |
| Too many tries (429) | "Too many tries. Try again shortly." The button stays enabled; no countdown is invented |
| Company suspended (403) | "This company's account is suspended. Ask your admin." |
| No network | "Can't reach LiveOpsHub. Check the connection and try again." What was typed stays |
| Badge not recognised | "Badge not recognised. Try again or sign in with your password." |
| **Badge of an admin, manager or cs** (after SEC-2) | the sheet closes; "This account signs in with a password." The username is **not** filled in from the badge |
| Came here because the session ended | one line above the fields: "You were signed out. Sign in again." |
| After account deletion | "Your account was deleted." |
| App too old | the existing "Update required" screen replaces Sign-in |

---

## 2. The second step

Shown after a correct password when the account has two-step verification on. One screen; its content depends on the methods the account has (the sign-in answer lists them, with the email address masked).

### Layout
1. Nav bar: "Cancel" (left) → back to Sign-in with the fields empty. Title "Two-step verification".
2. **Method**
   - **Email only:** text "We'll email a code to m•••@n•••.com." and the button **"Send code"**. After sending: "Code sent to m•••@n•••.com."
   - **Authenticator only:** text "Enter the 6-digit code from your authenticator app."
   - **Both:** a segmented control **Email | Authenticator app**. The method used last time on this device is selected first. An email is sent only when the person taps "Send code" — choosing the segment sends nothing.
   - The email code is offered to every role that uses two-step verification, admin included.
   - **No email address on file** (an account that set up the authenticator only): the Email option is not shown. One footnote: "Email codes aren't set up for this account. You can add your email in Account after signing in." The app never asks for an email address before sign-in.
3. **Code field** — six digits, large (Title 1, monospaced digits), `textContentType(.oneTimeCode)` and number pad. Submits by itself at six digits; also a **"Verify"** button.
4. **Send again** (email only) — a text button that is disabled with a visible wait: "Send again in 0:30". It becomes "Send again" when the wait ends. The wait length and the number of sends allowed come from the server; 30 s is the drawing value.
5. **Use a recovery code** — text button → the field accepts a recovery code (letters and digits, no auto-submit), with "Use email or authenticator instead" to go back.
6. Footnote: "Can't get a code? Use a recovery code, or ask your admin to reset two-step verification."

### States
| State | Treatment |
|---|---|
| Wrong code | stays here; the field shakes and clears: "That code isn't right. Try again." Error haptic |
| **Expired code** (email) | "That code has expired. Send a new one." — "Send again" is offered at once if the wait allows |
| **Step expired** (5 minutes since the password) | back to Sign-in with "That took too long. Sign in again." |
| **Too many tries** (429 on checking) | "Too many tries. Try again shortly." The field is disabled for the wait the server gives |
| **Send-again limit reached** (429 on sending) | "Send again" is replaced by "No more codes can be sent right now. Use your authenticator app or a recovery code, or try again later." (the first two only when the account has them) |
| **Email slow to arrive** | 20 s after a send with nothing typed, a footnote appears: "It can take a minute. Check your spam or junk folder for an email from Live Ops Hub." If the account has the authenticator: a button "Use authenticator app instead" |
| Email could not be sent | "We couldn't send the email. Try again, or use another method." |
| **No network** | "Can't reach LiveOpsHub. Check the connection." Nothing typed is lost; no code is counted as used |
| Recovery code used | signs in; on Today's first appearance a one-time alert: "You used a recovery code. {n} left. You can make new ones in Account → Two-step verification." |
| **Demo (sandbox) company** | this screen is never shown, and no email is ever requested for a demo account |

---

## 3. Two-step verification set-up (S12)

Entered from two places:
- **Set-up required** — straight after the password, for an admin, manager or cs account that has no method yet. A full-screen state (S11): `lock.shield` symbol, "Protect your account", "Your role needs two-step verification. It takes about a minute.", primary **"Set up now"**. Until it is done the account can only open Account (a text button in the corner), sign out, and delete the account. No tab bar.
- **Account → Two-step verification** — to add a second method, change the address, or turn a method off.

### 3.1 Choose a method
Title "Two-step verification". Two large rows, each with one sentence:
- **Email** — "We email a code to you each time you sign in."
- **Authenticator app** — "Use an app such as Google Authenticator or 1Password. Works without a connection to your inbox."

Footer: "You can add the other one later."

### 3.2 Email — the person's own address
1. **Your email** — `textContentType(.emailAddress)`, email keyboard, no autocapitalisation, no autocorrect. Footer: "Use an inbox you can open on this phone. We use this address only to send sign-in codes." Button **"Send code"**.
   - **An address is already on file for the account:** this step shows it in full to its owner — "We'll send a code to maya@northside.example" — with **"Send code"** and a text button "Use a different email".
2. **Enter the code** — "We sent a code to maya@northside.example." Six-digit field as in §2, "Send again in 0:30", and "Change email" (back to step 1).
3. On success → 3.4. **An address counts only after its code was confirmed**; an unconfirmed address is never used for sign-in codes.

| State | Treatment |
|---|---|
| Not a valid address | under the field, as soon as the button is tapped: "Check the email address." Nothing is sent |
| Wrong / expired code | as §2 |
| Email slow to arrive | as §2: "It can take a minute. Check your spam or junk folder…", plus "Change email" and "Use an authenticator app instead" |
| Send-again limit | "No more codes can be sent to this address right now. Try again later, or use an authenticator app." |
| Email could not be sent | "We couldn't send the email. Check the address, or use an authenticator app instead." |
| No network | "Can't reach LiveOpsHub. Nothing was saved." |

### 3.3 Authenticator app
1. "Scan this code with your authenticator app" — the QR code at 200pt on a white tile (also in dark mode), and under it **"Can't scan? Enter this key"** with the key in monospaced groups of four and a "Copy" button. On the same phone the person usually cannot scan their own screen, so a button **"Open in authenticator app"** opens the set-up link directly.
2. "Enter the 6-digit code the app shows" — field as in §2, **"Turn on"**.
3. Wrong code: "That code didn't match. Check the time on your phone and try again." On success → 3.4.

### 3.4 Recovery codes — shown once
Title "Save your recovery codes". Text: "Each code works once if you can't get a code. Keep them somewhere safe — we can't show them again." The codes in a two-column monospaced grid. **"Copy codes"** (toast "Copied"). A checkbox row "I've saved these codes" enables **"Done"**. Leaving without Done asks: "Leave without saving your codes?" [Stay] [Leave].

After Done: from set-up-required → the shell builds the tabs and opens Today; from Account → back to the Two-step screen.

### 3.5 Two-step verification in Account (after set-up)
A list:
- **Email** — "On · m•••@n•••.com" / "Off" → Change email (3.2) or Turn off.
- **Authenticator app** — "On" / "Off" → Set up (3.3) or Turn off.
- **Recovery codes** — "{n} left" → "Make new codes" (the old ones stop working; shows 3.4).

Every change asks for a **current code first** (from either method the account has). Outside set-up the address is shown masked. An account that must use two-step verification cannot turn off its last method: the row explains "Your role needs at least one method."

| State | Treatment |
|---|---|
| **Demo (sandbox) company** | the Account row is disabled: "Not available in the demo company." Set-up cannot be opened, and nothing here can send an email |
| Worker or host | no Security group in Account in 1.0 (optional two-step for them is 1.1) |
| No network | "Can't reach LiveOpsHub. Nothing was changed." |

---

## 4. Other system states owned by the shell (S11)
All are full-screen native states with a symbol, a title, one sentence and at most one button. None shows a web page.

| State | Title / text | Button |
|---|---|---|
| Can't reach the server | "Can't reach LiveOpsHub" / "Check the connection." | Try again |
| Update required | exists today | Update |
| Session ended | returns to Sign-in with "You were signed out. Sign in again." | — |
| Subscription not active | "Your company's subscription is not active" / "Ask your admin." No prices, no link to buy. Account stays reachable for Sign out and Delete account | Account |
| Account type not supported (`superadmin`) | "The platform console is on the web" | Sign out |
| Role can't open this (stale tab) | "Your account can't open this." / "Ask your manager." | — |

## Copy that needs Spanish
Every string above. First-draft examples: Sign in / Iniciar sesión · Username / Usuario · Password / Contraseña · Scan badge / Escanear gafete · For warehouse floor accounts. / Para cuentas del piso de almacén. · Two-step verification / Verificación en dos pasos · Email / Correo · Authenticator app / App de autenticación · Send code / Enviar código · Send again in {time} / Reenviar en {time} · Verify / Verificar · Use a recovery code / Usar un código de recuperación · That code isn't right. Try again. / Ese código no es correcto. Inténtalo de nuevo. · That code has expired. Send a new one. / Ese código venció. Envía uno nuevo. · Too many tries. Try again shortly. / Demasiados intentos. Inténtalo en un momento. · Protect your account / Protege tu cuenta · Set up now / Configurar ahora · Your email / Tu correo · Check your spam or junk folder / Revisa tu carpeta de spam o correo no deseado · Save your recovery codes / Guarda tus códigos de recuperación · I've saved these codes / Ya guardé estos códigos.

## What these screens need that does not exist yet
- **Email codes on the server** — nothing exists: an email address on the user record (confirmed before it counts), "send code" and "check code" at sign-in and at set-up, the list of methods with the masked address in the sign-in answer, wait lengths and limits in the answers so the app can show them, and a distinct answer for "expired code" versus "wrong code". The blueprint's N13 lists the same needs for its earlier delivery method.
- Set-up routes usable by manager and cs (today admin-gated; cs is refused — blueprint S12).
- `/api/mobile/session` reachable during set-up-required and the billing lock (N4), and carrying the two-step state (N3).
- The demo company must never send an email (the outbound fence, SEC-4 / N17).

## Open points — for app-planner
- **Admin reset of someone's two-step verification:** the footnote "ask your admin to reset" assumes it exists; the blueprint lists it as not checked (§9).
- **Which roles keep a badge after SEC-2** — the spec says "warehouse floor accounts" and treats host as password-only, as the blueprint assumes.
- **"Open in authenticator app"** on the same phone is this spec's addition for a real problem (you cannot scan your own screen). If the blueprint does not want it, the manual key remains.
- **Where an "address already on file" comes from:** staff accounts have no email field today (blueprint N13), so in practice the first set-up always asks for it. The state is specified because the lead asked for it; who may put an address on an account other than its owner is not decided.
- **Is email also the way back in** (a forgotten password)? Not specified here; 1.0 has no "forgot password".
- **A host or worker who also holds a role that must use two-step** — the spec follows the session's "required" flag and draws nothing role-specific.

## Acceptance (app-review K1, K7a; security SEC-1, SEC-2, SEC-3)
Privacy and Terms open from Sign-in without signing in. No screen before sign-in opens the camera unprompted. A demo-company login reaches Today with no code step. A manager with no method meets "Protect your account" and cannot reach Today before finishing. No desktop page appears anywhere in this flow.
