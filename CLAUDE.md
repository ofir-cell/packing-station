# packing-station — getwhatnot.com / Live Ops Hub

Read this first in every session. Team and hand-offs: `docs/TEAM.md`. Work in flight: `docs/mobile/BOARD.md` (the iPhone/iPad app) and `docs/site/BOARD.md` (the site and server).

## What this is

One Flask app (`app.py` + `templates.py`, gunicorn, deployed on Railway from `main`) that runs live-commerce fulfilment: TikTok Shop / Whatnot orders come in, a warehouse picks and packs them, every box gets a packing video. It runs a real warehouse every day (hundreds of orders) and is being sold to other live sellers, so each company ("org") has its own data.

Three front ends, one server:

| Front end | Where | Who uses it |
|---|---|---|
| Desktop screens | `templates.py`, routes in `app.py` | the warehouse floor today — **do not break** |
| Mobile screens | `mobile/` → `/m/...` | the iPhone/iPad app (and phone browsers) |
| Native iOS app "Live Ops Hub" | `ios/` (SwiftUI, XcodeGen) | tab shell, Pack (camera, video, scanner), web views for the rest |

## Rules that always hold

**Ofir decides and merges.** Work lands as a PR; nobody but Ofir merges to `main` or pushes to it. A merge to `main` deploys the server (Railway) and, if `ios/` changed, uploads a TestFlight build. Prefer merging server changes outside packing hours.

**Mobile work must not change the desktop.** A screen is rebuilt for mobile as a new `/m/<screen>` page in `mobile/`, never by editing its desktop template. `/m/` screens use the same login, data and `/api/*` endpoints, so business rules stay in `app.py`. If mobile work needs a change in shared logic, it is its own PR, says so in the first line, and goes through programmer → qa.

**The data is real.** `/m/` screens and the app act on real orders. Test against a seeded temp database (`tests/conftest.py`, `scripts/mobile_audit.py` `seed()`), and on devices against the demo company once it exists — never invent test activity on a real company.

**Server invariants** (qa checks each one a change touches):
- runs as several gunicorn workers — no in-process state that must be shared;
- one database per org; a user of org A can never read, change or infer org B's data;
- warehouse progress never moves backwards automatically (sync, import, regroup, cancel);
- stock is deducted exactly once (double-submit, re-import, revert, regroup);
- money actions (labels, shipping, cancels) are idempotent and need Ofir's approval path;
- roles are enforced on the server, not by hiding UI;
- all output HTML-escaped; webhooks verified; outbound calls have timeouts.

**Three kinds of "works" — say which one you mean:**
1. *tests pass* — `python3 -m py_compile app.py templates.py && python3 check_js.py && python3 -m pytest -q tests`, plus the browser check for the screen (`scripts/m_pick_check.py` is the model);
2. *compiles* — the `iOS build` workflow is green (there is no Mac here; Swift is never run locally);
3. *proven on a device* — listed in `docs/mobile/device-tests/PROVEN.md`.
Never report 1 or 2 as 3.

**Secrets.** Never ask for, print or commit passwords, 2FA codes, the App Store Connect key, or tokens. They live in Railway variables and GitHub repository secrets, entered by Ofir.

**Language.** Ofir writes in Hebrew; reply in Hebrew. Code, docs, UI copy, commit messages and anything Apple or a customer reads are in English (the app also ships Spanish for the floor).

## The iOS app — fixed facts

- Name **Live Ops Hub** · bundle `com.liveopshub.ios` · team BTRADE LLC `4B4X663V8J` · App Store Connect app id `6833207476` · SKU `liveopshub-ios`
- iPhone + iPad, iOS 17+. Tabs: Dashboard (desktop site in a web view), Pick (`/m/pick`), Pack (native).
- Scanning everywhere = Bluetooth/USB scanner (keyboard mode) + camera + typing.
- TestFlight: `.github/workflows/testflight.yml` (Xcode 26+, signs at export with the `ASC_*` secrets). Pipeline fixes go on a `testflight/<slug>` branch, which runs the workflow.
- Store listing and reviewer notes: `ios/APP_STORE.md`. Last App Review assessment: `docs/mobile/REVIEW-2026-11-05-baseline.md`.

## Where things are

| Need | Look in |
|---|---|
| Who does what, how work is handed over | `docs/TEAM.md`, `.claude/agents/` |
| What is in flight, blocked, next — the app | `docs/mobile/BOARD.md` |
| What is in flight, blocked, next — the site and server | `docs/site/BOARD.md`, production facts in `docs/site/PRODUCTION.md` |
| Mobile design system, screen specs, mockups | `docs/mobile/DESIGN_SYSTEM.md`, `docs/mobile/screens/`, `docs/mobile/mockups/` |
| Reference mobile screen | `mobile/pick.html`, `mobile/static/pick.js`, `tests/test_mobile_pick.py`, `scripts/m_pick_check.py` |
| Shared mobile layer | `mobile/static/mobile.css` (components), `shell.css` (tokens), `mobile.js` (API, sheets, scanning, language) |
| Native app | `ios/README.md` |
