# Account — native tab (last tab, every role)

**Blueprint:** S8, flows 4.1 (sign-out), 4.2, 4.7, rules 5.2, 5.6, 5.9, 5.10, pieces N5, N14. **Release: 1.0. Native SwiftUI — owner: ios-engineer.**
**Mockup:** the Account tab's place in the bar is in [`../mockups/tabbar.html`](../mockups/tabbar.html); the screen itself is not drawn in this round.
The file keeps its old name (`me.md`) so existing references still resolve. It no longer describes the web page `/me`: that page is not in the app, and "my numbers", achievements and recent packages wait for 1.1 (blueprint §3.2).

**User:** anyone. **Purpose:** who am I signed in as, language, two-step verification, the legal and support links Apple expects to find, sign out, and account deletion (App Review 5.1.1(v): it must be easy to find).

## Layout at 390pt — `List` in `.insetGrouped` style, large title "Account"
Rows are system list rows (44pt minimum, Dynamic Type), tint = LiveOpsHub indigo (DESIGN_SYSTEM §1.6). No company colour. Top to bottom:

1. **Identity** (one group, not tappable): 56pt circle with initials on the indigo → violet gradient · **{name}** (Title 3) · "{role label} · {company name}" (subheadline, secondary). Role labels: Warehouse Associate (worker) · Host · Customer Service · Warehouse Manager · Admin; several roles are joined with " · ".
   - Demo company: a second line in the group, amber, "Demo company — sample data."
2. **Preferences**
   - **Language** — trailing value "English" / "Español"; opens a pushed list with the two choices and a checkmark. Default: the device language. Applies at once to native screens and to the `/m/` web views (they reload).
3. **Security** — shown only when the session says two-step verification applies to this account (admin, manager, cs)
   - **Two-step verification** — trailing value "On" / "Off" → the native two-step screen (S12, specified in [`sign-in.md`](sign-in.md) §3: email code or authenticator app).
   - Demo company: the row is disabled with the footer "Not available in the demo company."
4. **Help and legal**
   - **Support** — trailing "support@liveopshub.com" → opens a mail draft to that address; if the device has no mail account, an alert shows the address with "Copy".
   - **Privacy Policy** → liveopshub.com, in an in-app browser sheet (`SFSafariViewController`).
   - **Terms of Use** → the same.
5. **Sign out** (its own group, one row, indigo text, centred) → confirmation dialog: title "Sign out of Live Ops Hub?" · [Sign out] · [Cancel]. Signing out ends the session on the server and clears it for native and web views together, then shows Sign-in.
6. **Delete account** (its own group, one row, destructive red, centred) → the Delete account screen below. Footer under the group: "Permanently deletes your account."
7. **Footer**: "Live Ops Hub {version} ({build})", footnote, centred.

No appearance or theme row (the app follows the system light/dark setting). No numbers, achievements or recent packages. No row that opens a desktop page.

## Delete account (pushed, its own screen)
1. Large title "Delete account". Warning haptic on appear.
2. **What happens** — a short text block. The wording mirrors the privacy policy and **waits for Ofir's sign-off** (board D7); placeholder until then: "Your account and sign-in are permanently deleted. Work you recorded — packed and picked orders and their packing videos — stays with {company} as part of its records."
3. **Password** — secure field, label "Password", `textContentType(.password)`; footer "Enter your password to confirm it's you."
4. **Two-step code** — only when the account has two-step verification on: a 6-digit field, and "Email me a code" when the account has a confirmed email address (blueprint flow 4.7 step 2, read with the email decision). It behaves as the second step in [`sign-in.md`](sign-in.md) §2: wait before "Send again", wrong and expired codes.
5. **Delete my account** — full-width destructive button, disabled until the password field is not empty → confirmation dialog: "Delete your account? This can't be undone." · [Delete account] (destructive) · [Cancel].
6. **Last admin of a company** — the server answers that confirming also deletes the company (`need_org_confirm`): a second dialog that names it, "This also deletes {company} and all its data — orders, videos and every user. This can't be undone." · [Delete {company}] (destructive) · [Cancel].
7. Success → signed out → Sign-in with one line: "Your account was deleted."

| State | Treatment |
|---|---|
| Wrong password / wrong code | stays on the screen; red footer under the field: "That password isn't right." / "That code isn't right." Error haptic |
| Too many tries (429) | "Too many tries. Try again shortly." |
| No network | "Can't reach LiveOpsHub. Nothing was deleted." + Try again |
| Deleting | the button shows a spinner and is disabled; fields locked |
| Demo company | nothing special in the app: the server answers success and signs out; the account still exists for the next reviewer. The last-admin dialog cannot appear (no demo login is an admin) |
| Subscription inactive, or two-step set-up required | Account, Sign out and Delete account stay reachable (blueprint flows 4.1, 4.2, 4.7) |

## States of the Account screen
- Loading the session: the identity group shows redacted placeholders; the other rows are drawn at once.
- No network: the screen works from the last session; Sign out still clears the device and tells the server when it can.
- Session ended: the shell shows Sign-in with "You were signed out. Sign in again."

## Copy (EN / ES) — every label needs both
Account / Cuenta · Language / Idioma · Two-step verification / Verificación en dos pasos · On / Activada · Off / Desactivada · Not available in the demo company. / No disponible en la empresa de demostración. · Support / Soporte · Privacy Policy / Política de privacidad · Terms of Use / Términos de uso · Sign out / Cerrar sesión · Sign out of Live Ops Hub? / ¿Cerrar sesión en Live Ops Hub? · Delete account / Eliminar cuenta · Permanently deletes your account. / Elimina tu cuenta de forma permanente. · Password / Contraseña · Delete my account / Eliminar mi cuenta · Delete your account? This can't be undone. / ¿Eliminar tu cuenta? Esto no se puede deshacer. · Your account was deleted. / Tu cuenta fue eliminada. · Cancel / Cancelar. Spanish is a first draft.

## Open points
- A worker who only ever signs in by badge may not know a password; the delete screen needs one (blueprint §9 "not verified"). → app-planner.
- The "what happens" text and the company-deletion sentence are policy wording. → Ofir (D7).
- Security is shown to admin, manager and cs (two-step verification is required for them); the spec shows the group only when the session says so, so a worker or host does not see it in 1.0.

## Acceptance (app-review K1, K2, K4)
Privacy, Terms and Support are each one tap from the Account tab. Delete account is visible without scrolling on a 390×844 screen for a worker, is reachable when the subscription is inactive, and cannot be completed without the password. Nothing on this screen opens a desktop page.
