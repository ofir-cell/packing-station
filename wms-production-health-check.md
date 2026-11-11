# Production Health Check — live system after deploying `25f0f21`

Read-only audit of the live Production service (`refreshing-surprise` / `authentic-curiosity`, env `production`). No writes, no label purchases, no config/deploy changes. Evidence is from Railway runtime logs, HTTP logs, metrics, and the deployed code.

**Scope note on "agents":** the specialized assets we built are the repo's **test suites / QA harnesses** (unit, concurrency, tenant-isolation, E2E), not live monitoring daemons. I applied them where they bear on a running system and otherwise gathered real Production evidence (logs/metrics/HTTP). I did not invent agents.

## Headline
- **Production is up and serving** (`25f0f21`, deployment `963928d9` SUCCESS, 2026-10-29 03:20 UTC). CPU ~4–6%, memory ~0.74 GB (peak 0.99 GB). No crashes, no tracebacks.
- **One CRITICAL issue:** automatic TikTok order → shipment materialization is failing for every order that has a live **room id**, with `OperationalError('no such column: label')`. Orders are captured but **do not reach the packing floor**.
- **This is NOT a Cycles 1–6 regression** — the identical error was logged by the *previous* production build `e5cf7a0` at 03:21:30, minutes before the new deploy. It is a **pre-existing schema-migration gap**. (Reported here as its own incident, like the UPS item.)
- **Backup V2 is healthy** — a fresh 14-file backup completed right after deploy.

## PASS / WARNING / FAIL by area

| # | Area | Status | Evidence |
|---|---|---|---|
| 1 | Railway deploy health, logs, crashes | **PASS** | `963928d9` SUCCESS; CPU avg 0.06 / max 0.32 cores; mem avg 0.83 / max 0.99 GB; no `Traceback` entries; no restarts |
| 2 | Auth, permissions, admin, org isolation | **PASS** (not directly re-probed) | Authed endpoints (`/api/today`, `/api/pack/mystats`, `/api/heartbeat`) all 200; no 401/403 anomalies; code unchanged + covered by `test_authz`/`test_tenant_isolation`/`test_cycle4_access`. No live multi-org probe performed (would need second-org creds) |
| 3 | TikTok OAuth, webhooks, **auto order sync** | **FAIL** | Webhooks arriving + acking 200 (`POST /api/tiktok/webhook`, TikTok IP 139.177.251.x); OAuth/token code intact. **But** order materialization fails: `[tiktok] sweep apply failed <id>: OperationalError('no such column: label')` firing continuously |
| 4 | LIVE session data + order association | **FAIL** | Order→show grouping runs through `_tt_room_label`, the exact function throwing the `label` error. Room-based show association is broken for affected orders |
| 5 | Packing stations, scanning, printing | **PASS** (reduced input) | `/api/pack/mystats` 200, packing mechanics unaffected by the bug; but fewer orders arrive because of #3 |
| 6 | Shipment consolidation, ShipStation, labels | **PASS** + separate UPS note | No label/ShipStation errors in window; `_can_buy_labels` gate intact. The **UPS carrier-account issue is tracked separately** (not an app regression), per your instruction |
| 7 | DB integrity, duplicates, missing data | **WARNING** | No duplication (dedup guards intact). **Data gap:** room orders are parked in `tiktok_orders` but not written to `shipments` until #3 is fixed — recoverable (a re-sweep will materialize them once the column exists) |
| 8 | Backup V2 status + monitoring | **PASS** | `[backup-v2] scheduler started (6h; bucket=packing-station-prod-backups; safe_mode=False)` + `[backup-v2] ok run=20261029T032138Z files=14`. `/api/ops/backup-status` available |
| 9 | Frontend, iPad usability, critical endpoints | **PASS** (minor perf) | All sampled endpoints 200; `/api/today` consistently ~2.3–2.9 s (see #10) |
| 10 | Background workers, sync delays, performance | **WARNING** | Sweep worker runs under single-leader flock (correct); but every apply errors (#3). `/api/today` ~2.5 s is slow though non-failing. CPU/mem healthy |

## CRITICAL issue — order materialization broken (`tiktok_rooms.label`)

**Symptom (Production logs, continuous):**
`[tiktok] sweep apply failed 5776401…: OperationalError('no such column: label')` — dozens of distinct live order IDs, every sweep cycle.

**Root cause (code-verified):** `_tt_room_label()` runs
`SELECT label,named,start_ts,custom_name FROM tiktok_rooms WHERE room_id=?` (app.py line ~14954).
The live `tiktok_rooms` table (per-tenant `shipments.db`) was created by an older schema and is **missing the `label` / `start_ts` / `named` columns**. The migration helper `_tt_rooms_ensure()` only backfills `custom_name` (one `ALTER TABLE … ADD COLUMN custom_name`), never the others. `CREATE TABLE IF NOT EXISTS` is a no-op on the existing table, so the columns are never added.

**Blast radius:** both sync paths call `_tt_apply_order` without a label → `_tt_label_for_order` → `_tt_room_label` → throws:
- background sweep (`_tt_sweep_once`), and
- webhook ingest (`_tt_ingest_order` → `_tt_apply_order(sc, o)`).
Every order carrying a room id (i.e. essentially all live orders) fails to become a shipment. The row is still parked in `tiktok_orders`, so **no data is lost** — it just never reaches the packing queue.

**Confirmed pre-existing, not a release regression:** the same SELECT and the same `custom_name`-only `_tt_rooms_ensure` exist verbatim in `e5cf7a0`, and `e5cf7a0` logged the identical error before `25f0f21` deployed.

**Recommended fix (additive migration — awaiting your approval to build + deploy):** extend `_tt_rooms_ensure` to backfill every missing column, mirroring the existing `custom_name` pattern:
```python
def _tt_rooms_ensure(c):
    c.execute("""CREATE TABLE IF NOT EXISTS tiktok_rooms(
        room_id TEXT PRIMARY KEY, label TEXT, start_ts INTEGER, named INTEGER DEFAULT 0)""")
    cols={r[1] for r in c.execute("PRAGMA table_info(tiktok_rooms)").fetchall()}
    for name, ddl in (("label","label TEXT"), ("start_ts","start_ts INTEGER"),
                      ("named","named INTEGER DEFAULT 0"), ("custom_name","custom_name TEXT")):
        if name not in cols:
            try: c.execute("ALTER TABLE tiktok_rooms ADD COLUMN "+ddl)
            except Exception: pass
```
Low-risk and additive (no data rewrite). Once deployed, the next sweep (~5 min) will materialize the backlog from `tiktok_orders` automatically. I can prepare this as a tested hotfix branch + bundle immediately on your go — I will not deploy without approval.

## Other observations (non-critical)
- **`[backup-v2] scheduler started` prints 4×** — one per gunicorn worker before the flock leader election; only one actually runs (single `ok run` line). Cosmetic; could be demoted to post-election logging.
- **`/api/today` ~2.5 s** under light load — worth a profiling pass later (not failing).
- **UPS carrier-account issue** — tracked separately as you directed; no evidence it is an application regression (no UPS label purchases in this window, and labels are gated/disabled paths).

## What I did NOT do
No writes, no label purchases, no order edits, no config or env changes, no deploy. I did not re-run the release test suites (you asked to focus on live behavior); the only new tests referenced are the status mappings already verified pre-release.
