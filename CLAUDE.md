# packing-station (getwhatnot.com / LiveOpsHub) — rules for AI agents

Warehouse + live-commerce fulfillment SaaS. First tenant: 5 Second Beauty / Peach Beauty (DANIELLE LOOK LLC), ~600–700 orders/day from TikTok Shop and Whatnot lives, Davie FL warehouse.

## Architecture you must respect
- **Single-file Flask app**: `app.py` (routes + logic), `templates.py` (HTML/JS as Python strings). Do not split modules as a side effect of another task.
- **gunicorn `-w 4`, no `--preload`**: every module-level statement and every thread runs in 4 separate processes. Module globals are per-process — never use them as shared state. Cross-process coordination = `_flock(name)` file locks or the DB.
- **Tenancy = one SQLite file set per org** under `/data/orgs/<org>/`. Always go through `sdb()` / `gdb()` / `video_dir()` etc. (they resolve the org from the session). Shared control plane: `users.json`, `stations.json`, `platform.db` (`tiktok_*`, tickets, billing — these DO need `org_id` filters).
- **SQLite**: WAL, `timeout=10`. Take `BEGIN IMMEDIATE` before any read-then-write (stock, status, quotes). Use relative updates (`on_hand=on_hand+?`), check `rowcount`.
- JSON stores: only via `update_json(path)` / `_atomic_write`.
- Storage: Cloudflare R2, keys prefixed by org (`_r2_media_key`).

## Invariants (do not break)
1. **Warehouse progress never goes backwards automatically.** Only a human action (revert, resolve) may move `picked/packed/issue/shipped` back. API sync may set `cancelled`, nothing else over local progress.
2. **Stock is deducted exactly once per item** (`shipment_items.depleted_qty/depleted_sku`). Any code that deletes or rebuilds items must carry depletion + `cancelled` over.
3. **Money actions are idempotent** (label buy, TikTok ship package): claim the quote/intent row first, then call the carrier, then record — and record even if later steps fail.
4. **Every HTML sink escapes** (`esc()` in JS, escape in Python-built HTML). No new `innerHTML` with server data unescaped.
5. **Webhooks verify signatures before any side effect.**
6. External HTTP calls have explicit timeouts and a per-request wall-clock budget well under 300s.
7. Times: store UTC; convert TikTok epochs and "today" with the org's timezone (America/New_York for 5sec).

## Workflow
- Branches: work on a feature branch → PR into `staging` → Ofir tests on staging → Ofir merges to `main` (Railway auto-deploys main). **Never push to `main`.**
- Before every commit: `python3 -m py_compile app.py templates.py && python3 check_js.py && python3 -m pytest -q tests`.
- Every bug fix / feature adds a test in `tests/` that fails before and passes after.
- Agent team and change flow: `docs/TEAM.md` (product-engineer → architect → product-designer → programmer → qa → Ofir).
- Keep diffs minimal and targeted; mention line numbers in the PR body.
- Never commit data files (`*.csv`, `users.json`, `.env`).
- Business deliverables/UI text in English. Ofir talks in Hebrew.

## Known open issues
See `AUDIT_2026-10.md` (P0/P1/P2 list). Check it before touching TikTok sync, imports, inventory, labels or users.
