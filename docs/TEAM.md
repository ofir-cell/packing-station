# Agent team — packing-station / getwhatnot.com

Two groups of agents. **Build team** (in this repo, `.claude/agents/`) changes the software. **Operations agents** (separate Railway service, planned) run the Peach Beauty warehouse through the app's API.

## Build team — how a change flows

```
Ofir / ops-agent report
   → product-engineer   writes docs/specs/<date>-<slug>.md (problem, acceptance criteria)
   → architect          adds Design section (state, concurrency, failure modes, rollback)
   → product-designer   adds UX section + docs/mockups/<slug>.html   (only if screens change)
   → programmer         implements + tests, PR → staging
   → qa                 PASS/FAIL per criterion + invariants
   → Ofir               tests on staging, merges staging → main (Railway deploys)
```

| Agent | Writes | Never |
|---|---|---|
| product-engineer | `docs/specs/` | product code |
| architect | `docs/` (ARCHITECTURE.md, Design sections) | app.py / templates.py |
| product-designer | spec UX sections, `docs/mockups/` | app.py / templates.py |
| programmer | app.py, templates.py, tests | push/merge to main |
| qa | `tests/` | approve with failing tests |

Bug fixes from `AUDIT_2026-10.md` may skip product-engineer and designer: programmer → qa → Ofir.

### The site track (added Nov 12 2026)

Work on the site itself — desktop screens, the server, production, security — has its own board, **`docs/site/BOARD.md`**, with four tracks: security, product, production and delivery, housekeeping. The app keeps `docs/mobile/BOARD.md`; an item lives on one board and the other points to it. The hand-over rules below ("How the agents talk to each other") apply to both boards.

What changed in the flow above:
- **PRs target `main`.** `staging` has diverged and is not a step today (site board C3); until it is rebuilt, the safety net is qa + security-reviewer + site-ops' deploy checklist + merging outside packing hours.
- **security-reviewer** reviews any site PR that touches sign-in, sessions, roles, company isolation, deletion, uploads, webhooks or outbound calls — after qa, before Ofir.
- **site-ops** (new) writes the deploy checklist on every server PR, keeps the open PRs mergeable and in a safe order, and owns `docs/site/PRODUCTION.md`, CI, dependency updates, staging and backups.

| Agent | Writes | Never |
|---|---|---|
| site-ops | `docs/site/` (board queue, `PRODUCTION.md`), `.github/workflows/ci.yml`, test infrastructure, dependency files, PR deploy checklists | product behaviour; merge, deploy, roll back or change a Railway variable; see a secret; requests to production beyond a public GET |
| security-reviewer | `docs/security/`, failing tests that show a finding | fix product code; CLEAR what it could not exercise |

## Mobile team — iPhone/iPad app (added Nov 2026)

The iOS app (`ios/`) is a native SwiftUI shell around the real dashboard (WKWebView) plus native Pack (camera or Bluetooth scanner + packing video). Making the app App-Store-grade means rebuilding every screen mobile-first.

**How (Ofir, Nov 10 2026): as a separate front end.** Mobile screens live in `mobile/` and are served under `/m/` (first one: `/m/pick`). The desktop screens in templates.py are not edited. Both use the same login, data and `/api/*` endpoints.

```
app-planner        docs/mobile/APP_BLUEPRINT.md — the app as a whole: tabs per role, every screen and where it lives, flows, 1.0 scope
   → Ofir             approves the blueprint
   → ios-designer     docs/mobile/screens/<screen>.md (spec) for each blueprint row — design system already in docs/mobile/DESIGN_SYSTEM.md
   → mobile-engineer  builds the /m/ screen in mobile/            ┐ in parallel when a screen
   → ios-engineer     builds the native piece in ios/, if any     ┘ needs both
   → programmer       only if the screen needs a server change (new field/endpoint) — own PR
   → mobile-qa        PASS/FAIL per screen at SE / 16 Pro / Pro Max / iPad, in a real browser, against server state
   → security-reviewer  on anything touching sign-in, roles, org data, the demo account, the bridge
   → Ofir             merges the PR to main  → Railway deploys the server, TestFlight uploads the app
   → release-manager  release note for the build; fixes the pipeline if the upload fails
   → device-test-lead 10-minute on-device script for Ofir / the warehouse; files what comes back
   → app-review       before any App Store submission: guideline-by-guideline verdict
```

| Agent | Owns / writes | Never |
|---|---|---|
| app-planner | `docs/mobile/APP_BLUEPRINT.md` (app map, screen inventory, flows, 1.0 scope) | screen specs, visual design, product code |
| ios-designer | `docs/mobile/` (design system, screen specs, mockups) | product code; add a screen or tab that is not in the blueprint |
| mobile-engineer | `mobile/` (the `/m/` screens), their tests, the `mobile/` wiring in app.py | Swift; desktop templates; merge; change data/permissions |
| ios-engineer | `ios/` (SwiftUI shell, Pack, scanner, camera, Account, bridge) | server code; call Swift "working" without a device test |
| mobile-qa | `tests/`, `scripts/mobile_audit.py`, `scripts/m_*_check.py`, `audit/` | approve with a hard fail |
| security-reviewer | `docs/security/`, failing tests that show a finding | fix product code; CLEAR what it could not exercise |
| release-manager | `.github/workflows/testflight.yml`, `ios/APP_STORE.md`, `docs/mobile/releases/` | submit, add testers or touch App Store Connect; see keys or passwords |
| device-test-lead | `docs/mobile/device-tests/` (scripts, `PROVEN.md`) | mark anything proven without a real device |
| app-review | `docs/mobile/REVIEW-*.md` | product code |

### How the agents talk to each other

Agents do not share a conversation; each one starts cold. They talk through files in the repo, and the lead session (the Claude conversation Ofir is in) dispatches them.

- **`docs/mobile/BOARD.md` is the one shared board.** Every piece of work in flight has one entry: what, who owns it now, state, the PR, what is blocked on whom. An agent reads the board first and updates its entry last. Format is at the top of the file.
- **A handoff names its receiver and is complete on its own**: what was done, the evidence (test run, CI run link, screenshots), what is *not* verified, and the exact next action. "Done, please review" is not a handoff.
- **Requests across lanes go through the board**, not by editing someone else's files: mobile-engineer needs a native piece → entry for ios-engineer; anyone needs a server change → entry for programmer; a reviewer finds a problem → entry for the owner with the reproduction.
- **Disagreements go to Ofir as a choice**, in plain words: the two options, what each costs, the recommendation. Reviewers (mobile-qa, security-reviewer, app-review) cannot be overruled by the engineer whose work they reviewed.
- **Three states of "works"**, never blurred: *tests pass* (pytest + browser check), *compiles* (iOS build run), *proven on a device* (listed in `docs/mobile/device-tests/PROVEN.md`).

Rollout order (Ofir, Nov 5 2026): **warehouse workers → warehouse manager → admin**. Same brand (indigo/violet, logo, themes), iPhone quality.
Note: `staging` has diverged from `main`; mobile PRs target `main` (Railway deploys `main`).

## Operations agents (planned, Peach Beauty)

| Agent | Job | Runs |
|---|---|---|
| Orchestrator | detects live end, runs the post-live playbook, talks to Ofir (Hebrew), daily summary | event + manual |
| Fulfillment | wait for sync → combine → validate (weights, address, cancels) → ship package → labels → batch per show → PrintNode | after each live |
| Warehouse | negative stock, stuck orders, issues queue, TikTok vs local reconcile, low stock | hourly + end of day |
| API health | token expiry, webhook rejections, sweep lag, order-count diff, 429s | every 5–15 min |
| Improvement | reads post-live reports weekly → hands top-3 ideas to product-engineer | weekly |

### Permission tree
- **L0 read** — all ops agents.
- **L1 reversible internal state** (notes, flags, mark issue) — ops agents alone.
- **L2 reversible external + print** (TikTok combine/uncombine, send batch to PrintNode) — Fulfillment, **after warehouse-manager one-tap approval**.
- **L3 money / irreversible** (ship package / buy labels, cancel order, stock adjustment) — **Ofir's approval only**, daily cap.
- **L4 code** — build team via PR; **only Ofir merges to main**.

Mechanics: ops agents use a dedicated `agent` role with per-agent API tokens, every action written to `audit_log` with the agent name, one global kill switch (`AGENTS_ENABLED=0`). Agents never get DB or R2 credentials.

### Learning loop
Each live produces a post-live report: combine rate, failures, minutes from live end to all labels printed, mispacks, late cancels. Improvement agent → product-engineer → normal build flow.

### Prerequisites before ops agents go live
1. P0 items in `AUDIT_2026-10.md` fixed (TikTok #1–#3 done in `fix/tiktok-critical`).
2. TikTok app approved for the **Fulfillment** scope; combine / ship-package / shipping-document endpoints implemented in the app behind admin-only, idempotent routes.
3. PrintNode API key + printer IDs per station.
