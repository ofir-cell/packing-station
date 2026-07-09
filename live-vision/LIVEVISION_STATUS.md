# LiveVision — Deployment & First Test · Status

_Running checklist. Updated as we go._

| Phase | Status | Notes / Blockers |
|---|---|---|
| **1. Code review & repo setup** | 🟡 In progress | Review done (see below). `.gitignore` added. Repo not yet created — needs your input. |
| **2. Railway deployment** | ⬜ Not started | Needs env values from you; needs repo pushed first. |
| **3. Product catalog** | ⬜ Not started | Waiting for your product export CSV. |
| **4. First test on recorded show** | ⬜ Not started | Waiting for the .mp4 recording + confirm you have ffmpeg/Python on Windows. |
| **5. Evaluation & calibration report** | ⬜ Not started | Needs ground truth for a sample. |
| **6. Order matching dry run** | ⬜ Not started | Needs To_Ship CSV. **Blocker found — see review item B1 (recorded-show start time).** |

## Open decision points / what I need from you
1. **GitHub repo** — I don't have a GitHub connector in this session, so I can't create/push the repo myself. Please either create `ofir-cell/livevision` (empty, private) and I'll give you exact push commands, or tell me you'd rather I hand you a ready-to-run script.
2. **`live-vision/` currently lives inside your `packing-app` (packing-station) folder** and is untracked there. Before anything, we should move it out to its own folder (e.g. `~/Desktop/livevision`) so it never gets committed into packing-station. Confirm and I'll give the move command.
3. **Auth decision (important):** the dashboard + all data endpoints are currently public (no login). Order CSVs contain customer names/addresses. Decide how to protect it before real order data goes in (options in review).
4. **Recorded-show order matching (Phase 6):** the show's start time is set to "now" when the agent runs, but a recording aired earlier — order matching needs the *real air start time*. I recommend a small, safe fix (add a start-time override). Approve and I'll implement.

## Cost/external-action gate
Nothing costing money or sent externally has been done. The first spend will be in Phase 4 (Claude vision calls on the test frames) — I'll estimate and confirm before you run it.
