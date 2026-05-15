# Packing Station — 5 Second Beauty

Internal warehouse system for the 5 Second Beauty packing operation. Records video of every packed order, lets CS/Admin search by tracking number, manages employee badges, and handles giveaway shipping.

**Live**: https://www.getwhatnot.com
**Host**: Railway
**Storage**: Cloudflare R2 (videos/photos), local volume (CSV log + JSON config)

---

## Repository layout

```
packing-app/
├── app.py              # The whole Flask app — routes + HTML templates as strings
├── requirements.txt    # Pinned Python deps
├── Procfile            # Railway entry: gunicorn -w 4 ...
└── README.md           # This file
```

> The app is intentionally single-file today. Refactor to modules is planned —
> see "Roadmap" below.

---

## Tech stack

- **Backend**: Flask 3.1 + Gunicorn (4 workers)
- **Auth**: bcrypt password hashes, badge login (barcode → session)
- **Storage**: Cloudflare R2 (S3-compatible) via boto3
- **Data**: `users.json`, `stations.json`, `packing_log.csv` on Railway volume
- **AI**: Anthropic Claude Haiku (giveaway address parsing only)
- **Badges**: `python-barcode` + `reportlab` (Avery 5160 sheets)

---

## Local development

```bash
git clone https://github.com/ofir-cell/packing-station.git
cd packing-station
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Required env vars (minimum to boot)
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export PORT=8080
# Optional — leave unset to use local disk instead of R2
# export R2_BUCKET=...
# export R2_ENDPOINT=...
# export R2_ACCESS_KEY_ID=...
# export R2_SECRET_ACCESS_KEY=...

python3 app.py
# First boot prints initial passwords for admin/cs1/worker1..6 — copy them.
```

Data dir defaults to `~/PackingStationData/` (override with `DATA_DIR`).

---

## Deploy

Push to `main` → Railway auto-builds and deploys.

```bash
git checkout main
git pull
# make changes...
git add . && git commit -m "feat: ..."
git push origin main
```

Required Railway env vars: `SECRET_KEY`, `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `RETENTION_DAYS=30`, `DATA_DIR=/data`, plus `ANTHROPIC_API_KEY` if AI parsing is wanted.

See `DEPLOYMENT.md` in the drafts folder for the full first-time setup (R2 bucket, lifecycle rules, API tokens).

---

## Roles

| Role | What they see |
|---|---|
| `worker` | Pick a station → scan tracking → record 5-10s video → repeat |
| `cs` | Dashboard + analytics + search by tracking + giveaway shipping |
| `admin` | Everything CS has + user management + badge printing + storage stats |

Workers can also log in by scanning a barcode badge — bypasses username/password entirely. Station per machine is remembered in a 10-year cookie.

---

## Roadmap (employee portal expansion)

Tracked on branch `feature/employee-portal`. Order is intentional — each step builds on the previous one.

1. Consolidation & README (this step)
2. Module split (`app.py` → `auth.py`, `packing.py`, `giveaway.py`, `templates.py`)
3. SQLite migration (users.json → `employees` table with profile fields)
4. Employee profile page (`/me`) + Packer-of-the-month (computed from CSV)
5. Leaderboard with daily/weekly/monthly podium + achievement badges
6. Document library (HR docs, manuals — uploaded to R2, downloaded by role)
7. New-hire onboarding checklist (per-employee tasks, admin tracks completion)
8. Announcements / shift schedule / time-off requests

---

## Drafts folder

Iteration snapshots (one per feature commit) live in `~/Desktop/packing station/_archive/`. That folder is **not** part of this repo — it's a scratch area for AI-generated iterations before they get committed here.

---

## Quick troubleshooting

| Symptom | Likely cause |
|---|---|
| `FATAL: SECRET_KEY environment variable is not set` | Missing env var on Railway |
| `FATAL: Partial R2 config` | Need all 4 R2 vars or none |
| Storage page shows `backend: local` in prod | R2 env vars not picked up — redeploy |
| Video upload returns "Storage upload failed" | R2 API token doesn't have write permission |
| Badge login shows "Badge not recognized" | Badge was revoked, or scanner has no Enter suffix |

For more, see `DEPLOYMENT.md` in the drafts folder.
