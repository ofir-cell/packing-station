# Cycles 1–6 — Production Release Plan (FINAL — awaiting your confirmation)

**Status: READY. Nothing has been merged or deployed. I am requesting your final confirmation before any merge/deploy — per your instruction.**

Independently re-verified this session against the real Git remote. No push, merge, deploy, Railway, or R2 change was made.

## 1. What ships
- **Deploy commit:** `25f0f21` (branch `release/prod-deploy`).
- **Contents:** Cycles 1–6 (all the security/QA/integration work, tasks #23–#44) **on top of** the Backup V2 hotfix already live in production (`e5cf7a0`).
- **How it was built:** the verified release candidate (131/131) with `git merge -s ours origin/main` recording production `e5cf7a0` as a parent. Net effect: **`25f0f21`'s tree is identical to the verified RC, and production `e5cf7a0` is an ancestor → a clean fast-forward, no merge conflicts to resolve at deploy time.**

## 2. Verification (re-run this session, not recalled)
| Check | Result |
|---|---|
| Full test suite on `25f0f21` | **131 passed / 0 failed** |
| `py_compile` | clean |
| JS screen gate | 63/63 valid |
| Fast-forward over production (`main` is ancestor) | **YES — no conflicts** |
| Shipping-permission gate vs production | **byte-identical** — `_can_buy_labels` / `_SHIP_LABEL_ORGS` / `SHIPPING_LABEL_ORGS` diff is empty between `e5cf7a0` and `25f0f21` |
| Business data / schema | no destructive migration; additive only |

**Shipping permissions are preserved exactly.** The Oct-16 org allowlist that restricts label purchases to the authorized org is unchanged by this release. No new auth logic is introduced or removed.

## 3. Recoverability before deploy (your independent restore)
Latest verified production backup: **run `20261028T030309Z` (14 files)** in `packing-station-prod-backups`.
I cannot run a data-plane restore (no prod R2 data creds, by design). You verify on your Mac:
```bash
cd ~/Desktop/packing-app
export R2_BACKUP_ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
export R2_BACKUP_ACCESS_KEY_ID="<prod backup token key>"
export R2_BACKUP_SECRET_ACCESS_KEY="<prod backup token secret>"
export R2_BACKUP_BUCKET="packing-station-prod-backups"
python3 restore_backup.py --run 20261028T030309Z --dest /tmp/prodcheck
# expect: downloads 14 files, SHA-256 + PRAGMA integrity_check pass, "RESTORE OK"
```
This proves the latest production backup is independently restorable **before** you deploy. (Restore writes to `/tmp/prodcheck` only — it refuses the live data dir.)

## 4. Deployment instructions (your action, after you confirm)
```bash
cd ~/Desktop/packing-app
# load the verified deploy commit from the bundle
git fetch /path/to/release-prod-deploy-25f0f21.bundle \
  release/prod-deploy:release/prod-deploy
git log --oneline -1 release/prod-deploy      # expect 25f0f21
# fast-forward production
git checkout main && git pull
git merge --ff-only release/prod-deploy        # clean FF — refuses if not
git push origin main                           # Railway auto-deploys production
```
Then verify health: app boots, `/healthz` (or your health route) 200, and a label-rate call still returns for the authorized org.

## 5. Rollback
- **Instant:** redeploy the prior production commit `e5cf7a0` (Railway → Deployments → Redeploy).
- Backup V2 keeps running throughout (it's already live and unchanged by this release).
- No schema rollback needed — the release is additive.

## 6. The one decision I need from you
**Reply "deploy Cycles 1–6" to authorize the fast-forward of `main` to `25f0f21` and the Railway production deploy.** Until then I will not merge or deploy.

Bundle: `release-prod-deploy-25f0f21.bundle` (delivered).
