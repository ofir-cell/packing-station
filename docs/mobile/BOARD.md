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
| D3 | Badge sign-in only for floor roles — **on condition that 2FA by SMS code exists first**, offered in addition to the authenticator app. |
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

## Waiting on Ofir

### Merge PR #39 (documents and tests only)
- Owner now: Ofir      State: blocked
- Done so far: roadmap, blueprint, both reviews, the security demonstrations (`tests/test_security_mobile_baseline.py`), the app-planner agent, this board.
- Next action: merge → Ofir. Code PRs for M2 branch from a `main` that has those tests. The merge redeploys the server with no behaviour change; no TestFlight build.

### Run the first device script (M1)
- Owner now: Ofir      State: blocked
- Next action: run `docs/mobile/device-tests/5.md` on the iPhone and the iPad with the Bluetooth scanner and send back the ✓ / ✗ list → Ofir. Decides D4.
- Blocked on: device-test-lead finishing the script (in flight).

### SMS provider for 2FA codes (from D3)
- Owner now: Ofir      State: blocked
- Done so far: nothing built; today 2FA is authenticator-app only. SMS needs a paid provider account, a sending number approved for US business texting, and its credentials in Railway variables (entered by Ofir, never in the repo or chat).
- Next action: say which provider to build against, or ask for a short comparison → Ofir. Blocks the SMS part of M2 and therefore SEC-2.

### Mailbox and domain
- Owner now: Ofir      State: todo
- Next action: open the support@liveopshub.com mailbox; be ready to point liveopshub.com (DNS) at the public pages when release-manager and programmer have them (M6) → Ofir.

## In flight

### Blueprint → approved version
- Owner now: app-planner      State: in progress
- Next action: fold the decisions above into `docs/mobile/APP_BLUEPRINT.md` (Scanit in 1.0, SMS 2FA, indigo only, manager + worker demo logins) → app-planner; then ios-designer aligns the specs.

### M1. First on-device test script (build 5)
- Owner now: device-test-lead      State: in progress
- Next action: write `docs/mobile/device-tests/5.md` → device-test-lead; Ofir runs it.

## Up next (by milestone — see `docs/mobile/ROADMAP.md`)

### M1b. Align screen specs to the blueprint
- Owner now: ios-designer      State: blocked
- Done so far: app-planner wrote `docs/mobile/APP_BLUEPRINT.md` (draft, Nov 10 2026) and listed every contradiction: `more.md` (withdraw), `DESIGN_SYSTEM.md` §3.1–3.5 and §8–10, `today.md`, `track.md`, `pick.md`, `cleanup.md`, `sign-in.md`, `me.md`, `pack.md`, and the eight specs that wait for 1.1.
- Not verified: the blueprint is from reading code only; N4, N8 and N10 (blueprint §3) are unreproduced.
- Next action: after Ofir approves the blueprint, bring the specs and mockups in line with it → ios-designer; app-review reads blueprint §2 and §6 for 4.2 and for the per-role tab sets.
- Blocked on: app-planner's approved version (in flight). Blocks M4 and M5.

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
- Blocked on: PR #39 merged. SEC-2 additionally waits for SMS 2FA (D3), which needs a spec (product-engineer → architect) and Ofir's provider choice.

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

### App Review and security baselines, roadmap (Nov 10 2026)
- app-review: `docs/mobile/REVIEW-2026-11-10.md` — a submission today would be rejected (R1 demo access, R2 web wrapper, R3 listing does not match the build).
- security-reviewer: `docs/security/2026-11-10-mobile-baseline.md` — company isolation holds on every endpoint the app calls; 4 findings block outside sellers, 3 block the demo account. Evidence: `python3 -m pytest -q tests` → 376 passed, 14 xfailed.
- Not verified: anything Swift (read only), production configuration, whether the public URLs answer.

### TestFlight pipeline (Nov 10 2026)
- PR #36, #37 merged. `.github/workflows/testflight.yml` uploads on every push to `main` touching `ios/`. Builds 4 and 5 uploaded and processed. Evidence: run 42935296933 (success).

### `/m/pick`, Bluetooth scanner, iPad support, Pick tab (Nov 10 2026)
- PR #36 merged. Evidence at merge: `pytest` 370 passed; `scripts/m_pick_check.py` all checks passed; `iOS build` run green.
- Not verified: anything on a real device beyond "installs and opens".
