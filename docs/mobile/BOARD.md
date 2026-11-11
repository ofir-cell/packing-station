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

## Waiting on Ofir (decisions)

Roadmap: `docs/mobile/ROADMAP.md` (milestones M0–M8). Reviews behind it: `docs/mobile/REVIEW-2026-11-10.md`, `docs/security/2026-11-10-mobile-baseline.md`.

### Approve the roadmap
- Owner now: Ofir      State: blocked
- Done so far: app-review and security-reviewer ran on `main` @ b032603 (Nov 10 2026); roadmap written from their findings. Tests: 376 passed, 14 xfailed (the 14 are the open security demonstrations).
- Next action: approve or change `docs/mobile/ROADMAP.md` → Ofir. Nothing is built before that.

### D1. Demo company for Apple's reviewer signs in without 2FA
- Owner now: Ofir      State: blocked
- Done so far: nothing built. Without it the app is rejected (R1). Security-reviewer's conditions: the exemption lives on a sandbox company, not on a user; nothing can leave that company; deletion is simulated; resettable (12-point checklist in the security report).
- Next action: yes / no → Ofir. Blocks M3.

### D2. Role of the reviewer account
- Owner now: Ofir      State: blocked
- Done so far: reviewers disagree. app-review: an admin login plus a worker login, so Apple sees every account type. security-reviewer: the no-2FA account must not be admin; a manager-level role plus a worker.
- Next action: choose → Ofir. Lead's recommendation: manager + worker. It costs nothing with Apple if the admin-only Manage tab is described in the notes, and a no-2FA admin is the one account an attacker would want.

### D3. Badge sign-in only for floor roles (SEC-2)
- Owner now: Ofir      State: blocked
- Done so far: today a badge alone opens an admin session if the badge holder is an admin (proven by test). The fix means admins, managers and CS sign in with password + 2FA; workers and pickers keep the badge.
- Next action: confirm this is acceptable on the floor, or name the roles that must keep badge sign-in → Ofir. Blocks M2.

### D4. iPad in version 1.0
- Owner now: Ofir      State: blocked
- Done so far: iPad is declared, so Apple reviews it and requires 13-inch screenshots; nothing on iPad is proven on a device.
- Next action: decide after the M1 device round — keep iPad only if it passes; otherwise ship 1.0 iPhone-only → Ofir.

### D5. Unlisted or public listing, and which countries
- Owner now: Ofir      State: blocked
- Done so far: app-review recommends unlisted for 1.0 (customers install by link; still goes through App Review). US-only storefront keeps the "request access" sentence; worldwide needs it removed (K8).
- Next action: choose both → Ofir. Blocks M6.

### D6. Public pages on liveopshub.com
- Owner now: Ofir      State: blocked
- Done so far: privacy, terms, support and marketing URLs given to Apple are on getwhatnot.com, a domain built on another company's trademark (K9).
- Next action: confirm liveopshub.com is yours and may serve the public pages (the server address can move later) → Ofir. Blocks M6.

### D7. Privacy policy wording and a public support contact
- Owner now: Ofir      State: blocked
- Done so far: the policy says TikTok access is read-only (the app creates labels) and "encrypted credentials" (they are not); subprocessors are missing; the support URL is a sales form (K4, K10, security report "Privacy answers vs. reality").
- Next action: approve corrected wording when release-manager drafts it (legal text — yours to sign off) and give the support email to publish → Ofir. Blocks M6.

### D8. Brand colour in the app
- Owner now: Ofir      State: blocked
- Done so far: `/m/` screens use each company's own brand colour, as the desktop site does. Mockups Ofir approved were indigo/violet; a company whose colour is pink sees pink.
- Next action: choose — keep per-company colour (current), or always LiveOpsHub indigo inside the app → Ofir. Needed before M5 screens and screenshots.

### Approve the app blueprint and answer Q1–Q5
- Owner now: Ofir      State: blocked
- Done so far: `docs/mobile/APP_BLUEPRINT.md` (draft). Proposed: every role opens on Today; worker / manager / cs get Today · Pick · Pack · Account; host gets Today · Account; admin also gets Manage (the desktop site). No More tab. 1.0 = native sign-in, Today, Pick, Cleanup, Pack, Track, Account, Manage for admin; everything else waits for 1.1.
- Next action: approve or change, and answer — Q1 Manage for admin only (recommended) or also manager and cs · Q2 Track inside Today (recommended) or its own tab · Q3 News and My Schedule after 1.0 (recommended) or in it · Q4 host gets Today + Account only (recommended) or Scanit is built now · Q5 packing video shown in Track for cs / manager / admin (recommended) or the listing sentence is cut → Ofir.

## In flight

_Nothing in flight. Building starts when the roadmap is approved._

## Up next (by milestone — see `docs/mobile/ROADMAP.md`)

### M1. First on-device test script (current build 5)
- Owner now: device-test-lead      State: todo
- Done so far: build 5 is installed on Ofir's iPhone and opens. Nothing else is proven — see `docs/mobile/device-tests/PROVEN.md`.
- Next action: write `docs/mobile/device-tests/5.md` (sign-in, Pick, Bluetooth scanner on Pick and Pack, camera scan, packing video on iPhone and on iPad in every orientation, Wi-Fi off) → device-test-lead; Ofir runs it. Result answers D4.

### M1b. Align screen specs to the blueprint
- Owner now: ios-designer      State: blocked
- Done so far: app-planner wrote `docs/mobile/APP_BLUEPRINT.md` (draft, Nov 10 2026) and listed every contradiction: `more.md` (withdraw), `DESIGN_SYSTEM.md` §3.1–3.5 and §8–10, `today.md`, `track.md`, `pick.md`, `cleanup.md`, `sign-in.md`, `me.md`, `pack.md`, and the eight specs that wait for 1.1.
- Not verified: the blueprint is from reading code only; N4, N8 and N10 (blueprint §3) are unreproduced.
- Next action: after Ofir approves the blueprint, bring the specs and mockups in line with it → ios-designer; app-review reads blueprint §2 and §6 for 4.2 and for the per-role tab sets.
- Blocked on: Ofir's approval of the blueprint (entry above). Blocks M4 and M5.

### M1b. Pieces 1.0 needs that do not exist (from the blueprint)
- Owner now: programmer / ios-engineer / mobile-engineer      State: blocked
- Done so far: named in blueprint §3. programmer: `/api/mobile/session` returns capabilities (`can.pick/pack/track/manage`), 2FA-setup, billing-locked, sandbox and support contact, and is reachable behind the 2FA-setup and billing gates (N3, N4, shared-logic PR); packing-video link from a lookup (N10). ios-engineer: Pack keeps the recording and retries when the upload fails (N8) — today it appears to delete it. mobile-engineer: `/m/pick` no longer links to desktop `/admin/cleanup` and `/me` (N7).
- Next action: each becomes its own PR inside M2 / M4 / M5 once the blueprint is approved.
- Blocked on: roadmap and blueprint approval.

### M2. Server security fixes
- Owner now: programmer      State: blocked
- Done so far: findings and failing demonstrations exist (`tests/test_security_mobile_baseline.py`, strict xfail). Before the demo company: SEC-1, SEC-2, SEC-3, SEC-4, SEC-7. Before outside sellers: SEC-5, SEC-6.
- Not verified: production configuration; the desktop routes outside the app's own calls.
- Next action: one shared-logic PR per finding, first line says so → programmer; then qa, then security-reviewer.
- Blocked on: roadmap approval; D3 for SEC-2.

### M3. Demo company + reviewer accounts
- Owner now: programmer      State: blocked
- Done so far: none. Requirements: security report, "Requirements for the demo/reviewer company".
- Next action: build the sandbox company, seed, reset and label PDF → programmer; security-reviewer must return CLEAR; app-review confirms R1 and K3 closed.
- Blocked on: D1, D2, and M2 (SEC-1, 2, 3, 4, 7).

### M4. Native shell: sign-in, Account, role-built tabs
- Owner now: ios-designer      State: blocked
- Done so far: specs `docs/mobile/screens/sign-in.md`, `me.md` exist; `/api/mobile/session` returns the user's roles; `LegalLinks.swift` exists but is unused.
- Next action: confirm the specs cover native sign-in with legal links, Account (sign out, delete, privacy, terms, support) and the tab rules (Pick hidden for roles that cannot pick; Dashboard becomes admin-only "Manage", never the launch tab) → ios-designer; then ios-engineer builds, incl. signed-out Pack (K7), SEC-15, SEC-16; then security-reviewer + app-review.
- Blocked on: roadmap approval; M1b (approved blueprint).

### M5. `/m/today`, `/m/track`, `/m/cleanup`
- Owner now: mobile-engineer      State: blocked
- Done so far: specs exist (`today.md`, `track.md`, `cleanup.md`). `/m/pick` is the reference implementation.
- Next action: build `/m/today` (launch screen), then `/m/track`, then `/m/cleanup` and point `/m/pick`'s two gates at it, each with a browser check → mobile-engineer; then mobile-qa.
- Blocked on: roadmap approval; M1b (approved blueprint); D8 for colour.

### M6. Listing, policy and public pages
- Owner now: release-manager      State: blocked
- Done so far: `ios/APP_STORE.md` exists but describes screens the build does not have, lists wrong screenshot sizes and a privacy table that no longer matches the manifest (R3, K11).
- Next action: draft corrected policy wording, support page, description, privacy answers, age-rating answers and reviewer notes → release-manager; page changes → programmer.
- Blocked on: D5, D6, D7; screenshots wait for M3–M5.

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
