# R2 Backup Security Configuration — `packing-station-staging-backups` ONLY

## 1–2. Actual capability (verified, not assumed)
| Capability | Available to me? | Evidence |
|---|---|---|
| List / get / create / delete R2 buckets | **Yes** (management plane) | Cloudflare MCP: `r2_buckets_list`, `r2_bucket_get`, `r2_bucket_create`, `r2_bucket_delete` |
| **Manage Bucket Lock** | **No** | no such tool in the MCP |
| **Manage Object Lifecycle rules** | **No** | no such tool in the MCP |
| **Read existing lock/lifecycle rules** | **No** | `r2_bucket_get` returns only name/creation_date/location/storage_class/jurisdiction |
| **Manage/inspect R2 API tokens** | **No** | no token tool; and I must never retrieve secrets |
| Wrangler CLI | **No** | `command -v wrangler` → absent (npx exists but no CF token/login) |
| Cloudflare API token / account creds in sandbox | **No** | `CLOUDFLARE_API_TOKEN`/`CF_*`/`R2_ACCESS_KEY_ID` all absent (presence-checked, never read) |
| Browser automation of the CF dashboard | **No** | no connected browser extension here; and that crosses the approval boundary |

**Conclusion:** I can confirm the bucket exists and is isolated, but I **cannot inspect or change Bucket Lock, Lifecycle, or tokens** from this environment. So I cannot "take full ownership" of applying these — I can only verify what's reachable and hand you exact, ready-to-run configuration. This is a genuine access boundary, reported before any change.

## 3. Existing rules — inspection result
- Bucket confirmed: `packing-station-staging-backups` (ENAM, Standard, created 2026-10-27), distinct from operational `packing-station` and `packing-station-hr`.
- **Existing Lock/Lifecycle rules: UNKNOWN** — not inspectable with my tools. You must read them in the dashboard (bucket → Settings) or `npx wrangler r2 bucket lifecycle list packing-station-staging-backups` / `... lock list ...`. Do not assume "none" — check before adding.

## 4. Proposed retention policy (compatible with 6h schedule + last-known-good)
Backups run every 6h (4/day). The app keeps tiers 8×6-hourly / 7 daily / 6 weekly, but **in-app pruning stays OFF** (`BACKUP_PRUNE_IN_APP=0`) so deletion is governed by R2, not the app. Pair two R2 rules on prefix `db-backups/`:

- **Bucket Lock (immutability) — retain 7 days.** Recent backups (the ones you'd actually restore from) cannot be deleted or overwritten for 7 days → protects the last-known-good set from accidental/malicious deletion.
- **Lifecycle (expiry) — delete after 45 days.** Bounds storage growth; always leaves ~44 days of history. Expiry (45d) **must be longer than** the lock window (7d) so the two never fight (a locked object is only eligible for lifecycle deletion after its lock lapses).

Why this satisfies last-known-good: nothing can delete a backup younger than 7 days (lock), and lifecycle only removes objects older than 45 days, so a verified recent backup is always retained. Adjust numbers to your storage budget — snapshot size is the SQLite DBs only (media stays in the operational bucket), so it's far below the 321MB volume figure; keep lock < expiry whatever you choose.

## Exact configuration to apply (your action — dashboard or Wrangler)
**Dashboard:** R2 → `packing-station-staging-backups` → Settings →
- **Object lifecycle rules → Add rule:** name `expire-db-backups-45d`, prefix `db-backups/`, action *Delete* after `45` days.
- **Bucket lock rules → Add rule:** name `lock-db-backups-7d`, prefix `db-backups/`, condition *Age* `604800` seconds (7 days).

**Wrangler (equivalent):**
```bash
npx wrangler r2 bucket lifecycle add packing-station-staging-backups \
  --name expire-db-backups-45d --prefix db-backups/ --expire-days 45
npx wrangler r2 bucket lock add packing-station-staging-backups \
  --name lock-db-backups-7d --prefix db-backups/ --retention-days 7
```
(Keep `BACKUP_PRUNE_IN_APP` unset/0 — with the lock active, in-app deletes would be denied anyway; let lifecycle handle expiry.)

## 5–6. Credential revocation & scope — verification (I cannot see secrets)
I have no token-introspection tool and must never retrieve secret values, so I **cannot verify** rotation/scope directly. Treat the previously exposed credential as compromised until you confirm. You verify (no secrets displayed):
- **Revocation:** R2 → Manage API Tokens → confirm the OLD token is **deleted/revoked** (absent from the list).
- **Replacement scope:** the NEW token's detail shows **Object Read & Write scoped to `packing-station-staging-backups` only** (not "all buckets", not account-wide).
- **Runtime scope proof (non-secret):** with the new token configured, a cross-bucket probe must be DENIED — e.g. `aws s3api head-bucket --bucket packing-station --endpoint-url …` using the backup token → expect **403 AccessDenied**; and your passing `r2_oneoff_validate.py` run already proved the token works on the backup bucket. (Run this yourself; don't paste keys here.)

## 7. Risks (reported before any change)
- **Lock ≥ expiry would deadlock deletion** — always set lock window < lifecycle expiry (7d < 45d here). 
- **Indefinite lock** would make objects permanently undeletable and grow cost without bound — do NOT use `--retention-indefinite` on `db-backups/`.
- **Applying lock before the schedule is validated** could lock in malformed early backups for 7 days — acceptable (they expire) but validate one real run first.
- **Wrong prefix** (e.g. applying to the whole bucket incl. `validation/`) would lock throwaway test data — scope rules to `db-backups/` only.
- I did **not** apply anything; no operational bucket, Production, Railway, or Safe Mode was touched.

## 8. Boundaries
Did not modify operational buckets, Production, Railway, Safe Mode, or any R2 security policy. Created/changed nothing this phase (only read-only list/get).

## The single action requiring you
Apply the two rules above (dashboard or Wrangler) and confirm token revocation + bucket-scoping — these require Cloudflare dashboard/API access I don't have. Once done, tell me and I'll fold the confirmation into the activation GO/NO-GO. If you'd prefer, grant a Cloudflare API token with R2 **edit** scope to this environment and I can drive `npx wrangler` directly — but that itself is a credential decision for you to make, and I won't request the secret in chat.
