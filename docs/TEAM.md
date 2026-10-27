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
