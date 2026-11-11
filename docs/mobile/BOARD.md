# Mobile board — Live Ops Hub (iPhone / iPad)

The one place the mobile agents hand work to each other. Read it before you start; update your entry before you stop. Rules: `docs/TEAM.md` → "How the agents talk to each other".

Entry format — newest first inside each section:

```
### <short title>
- Owner now: <agent or Ofir>      State: todo | in progress | in review | blocked | done
- PR / branch: <link or —>
- Done so far: <facts, with evidence: test command + result, CI run link>
- Not verified: <what nobody has checked, especially on a real device>
- Next action: <one concrete step> → <who>
- Blocked on: <who / what decision> (omit if not blocked)
```

## Decided by Ofir (Nov 10 2026)

Roadmap (`docs/mobile/ROADMAP.md`) and app blueprint (`docs/mobile/APP_BLUEPRINT.md`) **approved** with these answers:

| # | Decision |
|---|---|
| D1 | Yes: an isolated demo (sandbox) company signs in without 2FA for Apple's reviewer. |
| D2 | Reviewer logins are **manager + worker**. No admin demo account. |
| D3 | Badge sign-in only for floor roles — **on condition that a 2FA code sent by email works first** (first answer was SMS; changed to email the same evening). The authenticator app stays as the other option. No SMS and no phone numbers in 1.0. |
| D4 | iPad in 1.0 is decided by the first device round (M1): it stays only if every iPad step passes. |
| D5 | **Unlisted** distribution, **US storefront only**. |
| D6 | liveopshub.com is Ofir's; the public pages (privacy, terms, support, marketing) move there. |
| D7 | Public support contact: **support@liveopshub.com**. Policy wording still needs Ofir's sign-off when drafted. |
| D8 | **Always LiveOpsHub indigo** inside the app. |
| Q1 | Manage tab for **admin only**. |
| Q2 | Track lives **inside Today**. |
| Q3 | News and My Schedule wait for 1.1. |
| Q4 | **Scanit (the host's tool) is built for 1.0.** |
| Q5 | Packing video is viewable from Track for cs / manager / admin. |
| Q6 | Void — no SMS provider is needed. |
| Q7 | The person enters their own email address at set-up; it counts only after they type a code sent to it. |
| Q8 | 2FA is required for admin, manager and cs. The emailed code is available to all three. |

## Waiting on Ofir

### Merge PR #39 (documents and tests only)
- Owner now: Ofir      State: blocked
- Done so far: roadmap, blueprint, both reviews, the security demonstrations (`tests/test_security_mobile_baseline.py`), the app-planner agent, this board.
- Next action: merge → Ofir. Code PRs for M2 branch from a `main` that has those tests. The merge redeploys the server with no behaviour change; no TestFlight build.

### Run the first device script (M1)
- Owner now: Ofir      State: blocked
- Next action: run `docs/mobile/device-tests/5.md` on the iPhone and the iPad with the Bluetooth scanner and send back the ✓ / ✗ list → Ofir. Decides D4.
- Done so far: script written (52 steps; needs 3 real orders to pick and 9 real boxes to pack). Expected failures from code reading are listed at its end.

### Read the changed blueprint sections and the mockups
- Owner now: Ofir      State: blocked
- Done so far: specs and mockups aligned by ios-designer (PR for `design/specs-to-blueprint`); blueprint rev 2 written by app-planner (email code; gaps settled).
- Next action: look at `docs/mobile/mockups/tabbar.png`, `today-*.png`, `scanit*.png`, `sign-in.png` and say what to change; read the blueprint sections marked as changed (Scanit, email code) → Ofir.

### Q9. Which address sends the 2FA code emails
- Owner now: Ofir      State: blocked
- Done so far: app-planner could not see the production mail set-up; today's configured sender may be a Gmail address or another brand, which risks the codes landing in junk.
- Next action: choose — a liveopshub.com sender (recommended; a few DNS records, done together with moving the public pages) or today's configured sender → Ofir.

### Mailbox and domain
- Owner now: Ofir      State: todo
- Next action: open the support@liveopshub.com mailbox; be ready to point liveopshub.com (DNS) at the public pages when release-manager and programmer have them (M6) → Ofir.

## In flight

### M1b. Align screen specs to the approved blueprint
- Owner now: Ofir (review)      State: in review
- PR / branch: `design/specs-to-blueprint`
- Done so far: `DESIGN_SYSTEM.md` (tabs per role, no More, indigo only), new `scanit.md`, `today.md`, `track.md`, `me.md` (native Account), `cleanup.md`, `pick.md`, `pack.md`, `sign-in.md` (email code or authenticator, native set-up), `more.md` withdrawn, banners on the waiting specs. Mockups with rendered PNGs: tab bar per role, Today (worker, host, manager, admin, dark), Scanit, Sign-in.
- Not verified: nothing ran on a device or in Safari; Spanish copy is a first draft; no mockup yet for Track, Cleanup, Account, Pack; server facts are from reading `app.py`.
- Next action: Ofir reviews the mockups; mockups for Track, Cleanup and Account → ios-designer when the blueprint rev 2 is in.

### Spec touch-ups after blueprint rev 2
- Owner now: ios-designer      State: todo
- Done so far: blueprint rev 2 written by app-planner (email code throughout; gaps settled — see its change log and §8.1).
- Next action: `sign-in.md` (§3.2 "address on file", §3.5, the 5-minute number), `me.md` (a badge-only worker deletes the account with a fresh scan of their own badge), `today.md` (`open_shows`, browser avatar), `track.md` (Open in Pick, video formats), `pack.md` (videos waiting to upload: kept on the device, at most 10, retried automatically), `DESIGN_SYSTEM.md` §3.4, §3.6, §8, DS-3; mockups for Track, Cleanup and Account → ios-designer, together with Ofir's comments on the first mockups.
- Blocked on: Ofir's comments on the mockups (so both go in one pass).

## Up next (by milestone — see `docs/mobile/ROADMAP.md`)

### M1b. Pieces 1.0 needs that do not exist (from the blueprint)
- Owner now: programmer / ios-engineer / mobile-engineer      State: blocked
- Done so far: named in blueprint §3. programmer: `/api/mobile/session` returns capabilities (`can.pick/pack/track/manage`), 2FA-setup, billing-locked, sandbox and support contact, and is reachable behind the 2FA-setup and billing gates (N3, N4, shared-logic PR); packing-video link from a lookup (N10). ios-engineer: Pack keeps the recording and retries when the upload fails (N8) — today it appears to delete it. mobile-engineer: `/m/pick` no longer links to desktop `/admin/cleanup` and `/me` (N7).
- Next action: each becomes its own PR inside M2 / M4 / M5 once the blueprint is approved.
- Blocked on: PR #39 merged (server pieces); aligned specs (app pieces).

### M2. Server security fixes
- Owner now: programmer      State: blocked
- Done so far: findings and failing demonstrations exist (`tests/test_security_mobile_baseline.py`, strict xfail). Before the demo company: SEC-1, SEC-2, SEC-3, SEC-4, SEC-7. Before outside sellers: SEC-5, SEC-6.
- Not verified: production configuration; the desktop routes outside the app's own calls.
- Next action: one shared-logic PR per finding, first line says so → programmer; then qa, then security-reviewer.
- Blocked on: PR #39 merged. SEC-2 additionally waits for the emailed 2FA code (D3), which needs a spec (product-engineer → architect); staff accounts have no email field today.

### M3. Demo company + reviewer accounts
- Owner now: programmer      State: blocked
- Done so far: none. Requirements: security report, "Requirements for the demo/reviewer company".
- Next action: build the sandbox company, seed, reset and label PDF → programmer; security-reviewer must return CLEAR; app-review confirms R1 and K3 closed.
- Blocked on: M2 (SEC-1, 2, 3, 4, 7). Reviewer logins: manager + worker (D2).

### M4. Native shell: sign-in, Account, role-built tabs
- Owner now: ios-designer      State: blocked
- Done so far: specs `docs/mobile/screens/sign-in.md`, `me.md` exist; `/api/mobile/session` returns the user's roles; `LegalLinks.swift` exists but is unused.
- Next action: confirm the specs cover native sign-in with legal links, Account (sign out, delete, privacy, terms, support) and the tab rules (Pick hidden for roles that cannot pick; Dashboard becomes admin-only "Manage", never the launch tab) → ios-designer; then ios-engineer builds, incl. signed-out Pack (K7), SEC-15, SEC-16; then security-reviewer + app-review.
- Blocked on: M1b (specs aligned to the approved blueprint).

### M5. `/m/today`, `/m/track`, `/m/cleanup`
- Owner now: mobile-engineer      State: blocked
- Done so far: specs exist (`today.md`, `track.md`, `cleanup.md`). `/m/pick` is the reference implementation.
- Next action: build `/m/today` (launch screen), then `/m/track`, then `/m/cleanup` and point `/m/pick`'s two gates at it, each with a browser check → mobile-engineer; then mobile-qa.
- Blocked on: M1b (specs aligned to the approved blueprint). Colour: indigo (D8). Scanit joins this milestone (Q4).

### M6. Listing, policy and public pages
- Owner now: release-manager      State: blocked
- Done so far: `ios/APP_STORE.md` exists but describes screens the build does not have, lists wrong screenshot sizes and a privacy table that no longer matches the manifest (R3, K11).
- Next action: draft corrected policy wording, support page, description, privacy answers, age-rating answers and reviewer notes → release-manager; page changes → programmer.
- Decided: unlisted, US only, liveopshub.com, support@liveopshub.com. Blocked on: Ofir's sign-off on the drafted policy wording; screenshots wait for M3–M5.

### M7. Submission rehearsal → Ofir submits
- Owner now: app-review      State: blocked
- Next action: full device script on the release build in the demo company → device-test-lead / Ofir; app-review APPROVE and security-reviewer CLEAR; Ofir submits.
- Blocked on: M1–M6.

### M8. Outside sellers
- Owner now: programmer      State: blocked
- Next action: SEC-8 to SEC-14, security pass over the desktop routes reachable from the Manage tab, production configuration check with Ofir.
- Blocked on: Apple's approval; no open BLOCK-EXTERNAL finding.

## Done

### App blueprint approved; first device script written (Nov 10 2026)
- `docs/mobile/APP_BLUEPRINT.md` approved by Ofir with D1–D8 and Q1–Q5; app-planner folded the answers in. Tabs: worker / manager / cs Today · Pick · Pack · Account; host Today · Scanit · Account; admin adds Manage.
- `docs/mobile/device-tests/5.md` written by device-test-lead. Not run yet.
- Not verified: every code claim in both is from reading.

### App Review and security baselines, roadmap (Nov 10 2026)
- app-review: `docs/mobile/REVIEW-2026-11-10.md` — a submission today would be rejected (R1 demo access, R2 web wrapper, R3 listing does not match the build).
- security-reviewer: `docs/security/2026-11-10-mobile-baseline.md` — company isolation holds on every endpoint the app calls; 4 findings block outside sellers, 3 block the demo account. Evidence: `python3 -m pytest -q tests` → 376 passed, 14 xfailed.
- Not verified: anything Swift (read only), production configuration, whether the public URLs answer.

### TestFlight pipeline (Nov 10 2026)
- PR #36, #37 merged. `.github/workflows/testflight.yml` uploads on every push to `main` touching `ios/`. Builds 4 and 5 uploaded and processed. Evidence: run 42935296933 (success).

### `/m/pick`, Bluetooth scanner, iPad support, Pick tab (Nov 10 2026)
- PR #36 merged. Evidence at merge: `pytest` 370 passed; `scripts/m_pick_check.py` all checks passed; `iOS build` run green.
- Not verified: anything on a real device beyond "installs and opens".
