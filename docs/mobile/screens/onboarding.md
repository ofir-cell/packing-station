> **Not in 1.0 — waits for 1.1; back button and entry point to be re-specified then.** Blueprint §3.2 lists this screen as "later" (after 1.1). Until it is taken up, nothing below is built; paths, `‹ More` back buttons, badges and "language is in More" in this file are out of date (APP_BLUEPRINT §3.2, §8.2).

# Onboarding checklist — `/onboarding` · `ONBOARDING_HTML`

**User:** a new hire in their first days, often on their own phone.
**Purpose:** finish the required onboarding steps (safety training, handbook, floor tour …).

## What changes vs. today (`audit/…/pro/worker/onboarding.png`)
Keep the concept (header card + checklist). Fix:
- The header card is pink-tinted with a grey progress bar and a pink "0 / 5 complete" → **hero** `.m-card--hero`: eyebrow "ONBOARDING", title "Your checklist", body "Finish these to get fully set up at {company}.", a progress ring (64pt, white on gradient) showing "0/5", and a white progress bar.
- Checklist items have 20pt radio circles plus 10px "REQUIRED" / "SAFETY" tags → `.m-list` rows ≥64pt: a 28pt leading check circle (empty, or a brand-filled check when done), title (17/600), sub (15, 2 lines max), and pills underneath (`.m-pill` 12px: "Required" = `--pending`, category = `--brand --plain`). Tapping the row opens the step detail (pushed): description, the "Open guide/video/document" action, and the primary action bar button **"Mark as done"** (or the step's own completion, such as "Sign handbook").
- Completed steps move to a collapsed "Done · {n}" section at the bottom.

## States
All done: the hero turns green-tinted (`--m-green`) with "You're all set" and confetti off (keep it calm), plus a button "Go to Today". · Loading skeleton · Error banner.

## Copy
"Your checklist" · "{x} of {n} done" · "Mark as done" · "You're all set — welcome to the team."
