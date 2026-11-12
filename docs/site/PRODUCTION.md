# Production facts — the website

_Owner: site-ops. Started Nov 12 2026. Every line is either confirmed by Ofir (with the date) or marked unknown. No secret values here, ever — only "set / not set"._

| Fact | State | Source |
|---|---|---|
| Branch that deploys the server | `main` → Railway | `CLAUDE.md` |
| Staging | `staging` branch has diverged from `main`; no staging step today | `docs/TEAM.md` |
| `SHIPPING_LABEL_ORGS` lists every one of Ofir's own companies | **unknown — ask** (needed before PR #43) | PR #43 |
| Accounts with `admin` as an extra role and no 2FA | **unknown — ask** (needed before PR #44) | PR #44 |
| Which backup job runs (legacy weekday copies / Backup V2 `db-backups/`) | **unknown — ask** | PR #46 |
| `BACKUP_PRUNE_IN_APP` | **unknown — ask** | PR #46 |
| Backup bucket: may the backup key delete; lock, expiry or versioning on the bucket | **unknown — ask** (set at the storage provider) | PR #46 |
| Mail transport in production and the sender address | **unknown — ask** (decides Q9, the sender of 2FA codes) | spec in PR #42 |
| liveopshub.com DNS — who serves it today | **unknown — ask** | board D6 |
| A restore from backup has been rehearsed | **unknown — ask** | — |
| Changes Ofir made to the site on Nov 11 2026 | **not found in the repository** — location unknown | lead session |
