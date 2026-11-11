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

### Demo company for Apple's reviewer signs in without 2FA
- Owner now: Ofir      State: blocked
- Done so far: nothing built. Apple's reviewer cannot receive a 2FA code, so without a login that skips it the app is rejected (baseline review, finding 1).
- Next action: approve or reject "2FA is skipped only for one isolated demo company with seeded fake data that cannot reach real companies or send anything outside" → Ofir. On approval: programmer builds it, security-reviewer must return CLEAR before merge.

### Brand colour in the app
- Owner now: Ofir      State: blocked
- Done so far: `/m/` screens use each company's own brand colour, as the desktop site does. Mockups Ofir approved were indigo/violet; a company whose colour is pink sees pink.
- Next action: choose — keep per-company colour (current), or always LiveOpsHub indigo inside the app → Ofir.

## In flight

_Nothing in flight._

## Up next (in order)

### 1. Native Account screen
- Owner now: ios-engineer      State: todo
- Done so far: none. Required by Apple (account deletion reachable in-app, privacy policy, sign out).
- Next action: build an Account tab in `ios/` — name, role, company, sign out, delete account (existing server flow), privacy policy and terms links → ios-engineer; then security-reviewer + app-review.

### 2. Demo company + reviewer accounts
- Owner now: programmer      State: blocked
- Blocked on: Ofir's 2FA decision above.

### 3. Hide the Pick tab for roles that cannot pick
- Owner now: ios-engineer      State: todo
- Done so far: a Host sees "Access denied" in the Pick tab. `/api/mobile/session` already returns the user's roles.
- Next action: show Pick only when the session's roles include picker / worker / cs / admin / manager → ios-engineer.

### 4. `/m/today` (worker home) and `/m/track`
- Owner now: mobile-engineer      State: todo
- Done so far: specs exist (`docs/mobile/screens/today.md`, `track.md`). `/m/pick` is the reference implementation.
- Next action: build `/m/today`, then `/m/track`, each with a browser check like `scripts/m_pick_check.py` → mobile-engineer; then mobile-qa.

### 5. `/m/cleanup` (table clean-out)
- Owner now: mobile-engineer      State: todo
- Done so far: `/m/pick` sends a picker to the desktop `/admin/cleanup`, which returns to `/m/pick` in the app. Spec exists (`docs/mobile/screens/cleanup.md`).
- Next action: build `/m/cleanup` and point `/m/pick`'s two gates at it → mobile-engineer.

### 6. First on-device test script
- Owner now: device-test-lead      State: todo
- Done so far: build 5 is installed on Ofir's iPhone and opens. Nothing else is proven — see `docs/mobile/device-tests/PROVEN.md`.
- Next action: write `docs/mobile/device-tests/5.md` covering the Bluetooth scanner (Pick and Pack), camera scan, packing video on iPhone and on iPad in both orientations → device-test-lead; Ofir runs it.

## Done

### TestFlight pipeline (Nov 10 2026)
- PR #36, #37 merged. `.github/workflows/testflight.yml` uploads on every push to `main` touching `ios/`. Builds 4 and 5 uploaded and processed. Evidence: run 42935296933 (success).

### `/m/pick`, Bluetooth scanner, iPad support, Pick tab (Nov 10 2026)
- PR #36 merged. Evidence at merge: `pytest` 370 passed; `scripts/m_pick_check.py` all checks passed; `iOS build` run green.
- Not verified: anything on a real device beyond "installs and opens".
