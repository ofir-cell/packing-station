# TikTok Order Reconciliation — status & how to run

## 1. Deployment verified ✅
- **Production is running the hotfix** `a94a454` (deployment `016cb293`, SUCCESS, 2026-10-29 03:41 UTC).
- **Schema error resolved:** zero `no such column: label` entries on the new deployment (filtered log search returned empty).
- **Automatic sync working again:** `[tiktok] sweep ingested 51 order(s) for 5sec`.

## 2. Important: recovery of recent orders already happened safely (by design)
The fix is self-healing, so the normal production sweep resumed and **already materialized 51 orders** — this was the live poller, not a manual replay. It is **duplicate-safe and progress-safe by construction**, which is exactly what your four categories require:
- `_tt_apply_order` calls **`_tt_order_in_nonapi()` first** and returns immediately (no write) if the order already exists in any **non-API / CSV** shipment — matched by **order_id, tracking number, or package id**. CSV-imported orders are therefore never duplicated or touched (your categories 1 & 2).
- A **final guard** aborts if the target `shipment_id` exists but isn't API-owned → CSV shipment records can't be overwritten.
- Local status in `("picked","issue","packed","shipped","cancelled")` is **preserved** on every sweep — packing progress is never reset. Only a real TikTok CANCELLED overrides.

So the automatic ingest cannot have created duplicates of CSV orders or reset pack progress. The reconciliation below is the explicit audit you asked for, plus coverage of any **older backlog** outside the sweep's 2-hour window.

## 3. The read-only reconciliation (no production impact)
`reconcile_tiktok.py` (delivered) opens every database **strictly read-only** (`sqlite3 … mode=ro`, SELECT-only — verified: DB files are byte-identical before/after a run). It classifies every `tiktok_orders` row against `shipments`/`shipment_items`, matching **only on strong identifiers** — order_id, package_id, tracking number. Buyer/SKU/timestamp are reported as supporting evidence only, never used to decide identity.

It outputs exact counts per category:
1. **PACKED_OR_SHIPPED** — matched, and packed/shipped/has tracking → *do not touch*
2. **AWAITING** — matched, still pending/picked/issue → *do not duplicate*
3. **MISSING** — no match by any strong id → *safe recovery candidate*
4. **AMBIGUOUS** — weak-evidence-only or conflicting matches → *manual review*

### How to run (safest: against a restored backup)
```bash
cd ~/Desktop/packing-app
# 1) restore the latest prod backup to an isolated dir (read-only to Production)
export R2_BACKUP_ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
export R2_BACKUP_ACCESS_KEY_ID="<prod backup key>"
export R2_BACKUP_SECRET_ACCESS_KEY="<prod backup secret>"
export R2_BACKUP_BUCKET="packing-station-prod-backups"
python3 restore_backup.py --run <latest_run_id> --dest /tmp/recon_restore
# 2) reconcile (read-only)
python3 -I reconcile_tiktok.py --data-dir /tmp/recon_restore --show-missing
# machine-readable: add --json
```
(You can also point `--data-dir` at the live Railway volume mount — it only ever reads — but the restored backup is the cleanest zero-touch option.)

Paste me the output and I'll interpret the four counts and, for **category 3 only**, propose a safe recovery (see below).

## 4. Proposed safe recovery (only after you share the counts — not yet executed)
- **Category 3 (MISSING) only.** Recovery uses the existing idempotent `POST /api/tiktok/pull {days:N}` / `regroup-stored`, which run through the same `_tt_apply_order` path — so even if a "missing" order is actually present, the `_tt_order_in_nonapi` guard still prevents a duplicate. Nothing in categories 1, 2, or 4 is replayed.
- **No new labels, no status resets, no CSV overwrites** — the recovery path cannot do any of these.
- **Category 4 (AMBIGUOUS)** is listed per-order for your manual decision; I will not auto-recover any of them.

## 5. Is automatic sync fully operational?
**Yes.** Post-hotfix: the schema error is gone, the sweep is ingesting (51 orders), and the webhook path is acking 200. New LIVE orders will appear in Packing Station automatically. If you'd prefer to **pause** auto-ingest while you run the reconciliation, there's a per-org pause switch — but note it also holds back new live orders, and because auto-ingest is dedup/progress-safe, pausing isn't required. Your call.
