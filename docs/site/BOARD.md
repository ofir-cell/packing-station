# Site board — the website and server

_The shared board for work on the site itself: the desktop screens, the server (`app.py`, `templates.py`), production, security, CI. The iPhone/iPad app has its own board, `docs/mobile/BOARD.md`; an item lives on one board only, and the other points to it._

**Format** — every entry: `Owner now` · `State` (todo / in progress / in review / blocked / done) · `PR / branch` · `Done so far` (with evidence) · `Not verified` · `Next action → who` · `Blocked on`. An agent reads this board first and updates its entry last. Ofir merges; a merge to `main` deploys the server.

**Tracks:** A. Security · B. Product (features and fixes on the desktop site) · C. Production and delivery · D. Housekeeping.

## Waiting on Ofir

### Tell us what the site track should build first
- Owner now: Ofir      State: blocked
- Done so far: this board, seeded from what the reviews and specs of Nov 10–11 already found. Track B (product) has only the two old open PRs — Ofir's own list of site tasks is not here yet.
- Next action: name the tasks or problems on the site you want worked on, in any order and in plain words; each becomes an entry (product-engineer writes the spec) → Ofir.

### Where are the changes made to the site on Nov 11?
- Owner now: Ofir      State: blocked
- Done so far: no commit by Ofir on `main` or any branch on Nov 11; the only commits that day are the agents' PRs #41–#46.
- Next action: say where they are (a local copy not pushed, another session, Railway settings, another repository) → Ofir. Until then the four server PRs below are tested against a `main` that may not match production.

### Production facts needed before the server PRs merge
- Owner now: Ofir      State: blocked
- Next action: answer the "unknown — ask" lines in `docs/site/PRODUCTION.md` → Ofir (the lead can read Railway variable names and set / not-set with Ofir's go-ahead; bucket settings only Ofir can see).

## Ready for Ofir to merge (in this order)

| # | PR | What | Before merging | Right after deploy |
|---|---|---|---|---|
| 1 | #41, then #42 | Documents only (specs, mockups, blueprint rev 2; email-2FA spec, sandbox design) | — | — |
| 2 | #43 | SEC-5: carrier routes gated, UPS account number never returned | `SHIPPING_LABEL_ORGS` lists every own company | `/admin/inbound`: strip shows "UPS ups-direct", Get Rates returns prices; rates on one giveaway |
| 3 | #44 | SEC-1: 2FA on effective roles | list users with admin as extra role and no 2FA | such a user signs in, QR draws on Me, enrolling releases the hold |
| 4 | #45 | SEC-6: company deletion cleans up; founding company cannot be wiped; session bound to its company | — | worker and admin still signed in; badge sign-in; "View as" and exit; `unfinished_deletions: []`; app opens Pick |
| 5 | #46 | SEC-6i: backups of a deleted company erased after 30 days (sits on #45) | #45 merged | backup-status fresh and OK; latest run has the warehouse `shipments.db` |

All four server PRs touch `app.py` and the same test file: after each merge the next is brought up to date with `main` and the full check re-run before Ofir merges it (site-ops). Evidence for each is "tests pass" only; none ran against production.

## A. Security

### A1. Platform-owner account signs in with a password only (SEC-1a)
- Owner now: programmer      State: todo
- Done so far: reproduced by security-reviewer (`docs/security/2026-11-11-sec-1-effective-roles.md`): the superadmin cannot enrol 2FA (403 on set-up) and can impersonate into any company. Blocks outside sellers.
- Next action: allow and require 2FA for the platform owner, with a recovery path that does not lock Ofir out → programmer; then qa, security-reviewer.

### A2. Deletion needs no password (SEC-7)
- Owner now: programmer      State: blocked
- Done so far: decided shape — real companies: the password, or for a badge-only floor worker a fresh scan of their own badge (blueprint N21); demo company: simulated. Design in PR #42 (sandbox note, PR "D").
- Blocked on: #45 merged (same code).

### A3. 2FA code by email, then badge sign-in for floor roles only (SEC-2)
- Owner now: architect      State: blocked
- Done so far: spec `docs/specs/2026-11-10-email-2fa.md` in PR #42 (roll-out in five steps so nobody on the floor is locked out). Staff accounts have no email field today.
- Next action: Design section → architect; then programmer. SEC-2 merges only after the emailed code is proven in production.
- Blocked on: #42 merged; Ofir's answers to the spec's open questions (sender address Q9, O1–O7).

### A4. Demo (sandbox) company: flag, 2FA exemption, outbound fence (SEC-3, SEC-4)
- Owner now: programmer      State: blocked
- Done so far: design `docs/specs/2026-11-10-sandbox-demo-company.md` in PR #42 — build order as PRs A–G. Serves the app's M3 (see mobile board).
- Blocked on: #42 merged; Ofir's three answers (demo logins app-only, who records the sample packing video, forbid founding self-wipe — the last is already done in #45).

### A5. Carrier follow-ups (SEC-5a–5d)
- Owner now: programmer      State: blocked
- Done so far: listed in `docs/security/2026-11-11-sec-5-carrier-gate.md` — failed purchases return and store carrier error text with the account number; redaction is exact-match only; "prefer" answers 500 and logs the carrier error; tracking refresh calls USPS on platform credentials for every company.
- Blocked on: #43 merged.

### A6. Deletion follow-ups (SEC-6d, 6f, 6j)
- Owner now: programmer      State: blocked
- Done so far: webhook payloads arriving after deletion are stored with no company; TikTok access is not revoked at TikTok; a deleted company's tokens stay readable inside `platform.db` until it is compacted.
- Blocked on: #45 and #46 merged.

### A7. Remaining baseline findings (SEC-8 to SEC-14)
- Owner now: programmer      State: todo
- Done so far: each has a strict-xfail demonstration in `tests/test_security_mobile_baseline.py`: host reads full orders and can mark packed (8); upload accepts any bytes up to 250 MB in memory (9); password reset and logout do not end sessions (10); login throttle has no per-account cap (11); TikTok OAuth state not bound to the session (12); hire-document reader falls back to the founding company's legacy key (13); `/api/orgs/create` answers 500 (14).
- Next action: one PR each, SEC-12 and SEC-10 first → programmer; then qa, security-reviewer.

### A8. What the architect found on the way
- Owner now: product-engineer      State: todo
- Done so far: a manager can reach TikTok connect, WARP settings, hires and the 2FA routes; WARP calls have no staging guard; a new company is seeded with a real company's handbook text.
- Next action: decide per item whether it is a bug or intended, as short specs → product-engineer; Ofir confirms what a manager should reach.

### A9. Security pass over the rest of the desktop site
- Owner now: security-reviewer      State: todo
- Done so far: the Nov 10 baseline covered only what the app calls plus sign-in, sessions, deletion and media. Several hundred desktop routes are unreviewed.
- Next action: plan the pass by area (orders, inventory, labels, HR/hires, billing, platform console) → architect; then security-reviewer area by area.

## B. Product

### B1. Scan-to-verify while picking (PR #24, open since Oct 29)
- Owner now: qa      State: todo
- Next action: is it still wanted and still mergeable against today's `main`? → Ofir decides; if yes qa reviews it.

### B2. TikTok critical sync fixes (PR #6, open since Oct 27)
- Owner now: site-ops      State: todo
- Done so far: `docs/TEAM.md` says TikTok fixes #1–#3 are done in `fix/tiktok-critical`, but the PR is still open.
- Next action: find out what of it is already on `main` and what is not → site-ops; then Ofir decides.

## C. Production and delivery

### C1. Production facts file
- Owner now: site-ops      State: in progress
- Done so far: `docs/site/PRODUCTION.md` started with the open unknowns.
- Next action: list every environment switch the code reads and what it does when unset → site-ops; Ofir confirms the values that matter.

### C2. The test suite reaches the network
- Owner now: site-ops      State: todo
- Done so far: qa measured about 20 outbound attempts to TikTok hosts per suite run on `main`, from a background sweep thread; a fix exists only inside PR #45 (`tests/conftest.py`).
- Next action: after #45 merges confirm it is gone on `main`; add a guard that fails any test opening a real socket → site-ops.

### C3. Staging has diverged from `main`
- Owner now: site-ops      State: todo
- Next action: compare, and propose either a rebuilt staging (own database, safe mode, fake carriers) or retiring it → site-ops; Ofir decides.

### C4. Dependency updates waiting since July (PRs #1–#5)
- Owner now: site-ops      State: todo
- Done so far: bcrypt 5, boto3, reportlab 5, python-barcode, gunicorn 26 — untouched for four months.
- Next action: review each (changelog, what we use, full check), security-relevant first → site-ops.

### C5. Backups: which job runs, and a rehearsed restore
- Owner now: site-ops      State: blocked
- Blocked on: Ofir's answers in `PRODUCTION.md`.

### C6. Public pages and mail on liveopshub.com
- Owner now: release-manager      State: blocked
- Done so far: decided (mobile board D6, D7): privacy, terms, support and marketing pages move to liveopshub.com; support@liveopshub.com.
- Blocked on: Ofir's DNS access and the policy wording he signs off (mobile board M6). The server pages are programmer's work on this board when unblocked.

## D. Housekeeping

### D1. Documents the team is told to read do not exist
- Owner now: architect      State: todo
- Done so far: `AUDIT_2026-10.md` and `docs/ARCHITECTURE.md` are referenced by `docs/TEAM.md` and by agent definitions; neither is in the repository.
- Next action: write `docs/ARCHITECTURE.md` from the code (subsystems, per-company databases, background loops, outbound transports); ask Ofir whether the October audit exists elsewhere → architect.

## Done

_Nothing yet on this board. The Nov 10–11 reviews and fixes are recorded on `docs/mobile/BOARD.md` and in PRs #39–#46._
