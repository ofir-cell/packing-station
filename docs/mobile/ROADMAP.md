# Roadmap — from today to an approved App Store app

_Written Nov 10 2026 by the lead session. **Proposed — not approved. Nothing is built until Ofir approves this map.**_

Sources: `docs/mobile/REVIEW-2026-11-10.md` (app-review: a submission today would be rejected) and `docs/security/2026-11-10-mobile-baseline.md` (security-reviewer: BLOCK for outside sellers and BLOCK for a no-2FA demo account; company isolation itself holds on every endpoint the app calls). Finding ids below (R1…, K1…, SEC-1…) refer to those two reports.

## The shape of it

```
M0 decisions ─┬─ M1 device round on build 5 (no code) ────────────────┐
              ├─ M1b app blueprint ── (gates M4 and M5)                │
              ├─ M2 server security fixes ── M3 demo company ─────────┤
              ├─ M4 native shell (sign-in, Account, role tabs) ───────┼─ M7 rehearsal → Ofir submits → Apple
              ├─ M5 phone screens (Today, Track, Cleanup) ────────────┤
              └─ M6 listing, policy, public pages ────────────────────┘
                                                        M8 outside sellers (after approval)
```

M1, M1b, M2 and M6 can start side by side once M0 is answered. M4 and M5 wait for the approved blueprint (M1b). M3 waits for M2. M7 waits for everything.

What touches the live warehouse: **M2 and M3 change shared server logic** (`app.py`) — each fix is its own PR, labelled as such, through programmer → qa → security-reviewer, merged outside packing hours. M4 is `ios/` only (reaches phones through TestFlight). M5 adds new `/m/` pages; the desktop is untouched but a merge redeploys the server.

---

## M0 — Decisions and approval of this map

- **Owner:** Ofir.
- **What:** the decisions in `BOARD.md` → "Waiting on Ofir", and a yes on this map.
- **Done when:** each decision has an answer on the board. D1–D3 block the start of M2/M3/M4; the rest block M6 or later.

## M1 — First real-device round on the current build (no code)

- **Built:** `docs/mobile/device-tests/5.md`, a 10-minute script: sign-in, Pick, Bluetooth scanner on Pick and Pack, camera scan, packing video on iPhone, then the same on iPad in portrait and both landscapes, then Wi-Fi off.
- **Agent:** device-test-lead (script, then files what comes back as bugs for ios-engineer / mobile-engineer).
- **Ofir on the phone:** run the script on the iPhone and the iPad with the Bluetooth scanner. Until the demo company exists this is on the real company — use real orders that are actually being packed, never invented activity.
- **Done when:** every line of the script is in `PROVEN.md` as proven or as a filed bug, and the iPad question (D4) is answered by evidence: iPad stays in 1.0 only if it passes this round.

## M1b — App blueprint (no code)

- **Built:** `docs/mobile/APP_BLUEPRINT.md` — the app planned as one product before more screens are built: the tab bar and launch screen for each role, every screen with where it lives (native · phone-built `/m/` · desktop page inside the admin-only Manage tab · not in the app), the end-to-end flows (first sign-in, a picker's shift, scan → pack → next box, a manager checking a show, label lookup, account deletion, the reviewer's ten minutes), the rules that span screens (scanning, language, offline), and the 1.0 scope line. It also settles the contradictions between the Nov 5 screen specs (a fifth "More" tab) and this roadmap (Today / Pick / Pack / Account + Manage).
- **Agents:** app-planner (new) → ios-designer aligns `docs/mobile/screens/` and mockups to it → app-review reads it for 4.2 before anything is built.
- **Ofir:** reads the app map and the 1.0 scope line and answers the blueprint's open questions; looks at the tab-bar mockup for each role on the phone.
- **Done when:** the blueprint is marked approved by Ofir, every screen spec agrees with it, and each M4 / M5 item points at a blueprint row.

## M2 — Server security fixes (shared logic)

- **Built, before the demo company can exist:** SEC-1 (2FA on effective roles, not only the primary role), SEC-2 (badge sign-in for floor roles only), SEC-3 (2FA exemption honoured only in a company flagged as sandbox), SEC-4 (per-company outbound fence at every transport: email, carriers, TikTok, AI, barcode lookup, printing), SEC-7 (deletion and company wipe need the password).
- **Built, before any outside seller (recommended now, same owner):** SEC-5 (carrier account number never returned; rate calls behind the buy gate), SEC-6 (deleting a company removes its tokens and stored files).
- **Agents:** programmer (one PR per finding) → qa (invariants) → security-reviewer (verdict per PR).
- **Ofir:** D3 (badge change affects the floor). After each merge, on the phone and at a station: a worker still signs in by badge; an admin is asked for password + 2FA.
- **Done when:** the matching demonstrations in `tests/test_security_mobile_baseline.py` pass with their `xfail` markers removed, the full suite is green, and security-reviewer returns CLEAR on each PR.

## M3 — Demo company and reviewer logins

- **Built:** an isolated sandbox company with fully fake seed data, two logins (floor worker + the reviewer account, role per D2), no 2FA inside the sandbox only, nothing can leave it, deletion is simulated, resettable from the platform console plus a nightly re-seed, "Demo company" banner, a PDF of scannable sample labels. The full 12-point checklist is in the security report ("Requirements for the demo/reviewer company").
- **Agents:** programmer → qa → security-reviewer (must return CLEAR on every checklist line) → app-review (confirms a reviewer can complete every flow, including account deletion, and cannot break the demo for the next reviewer — K3).
- **Ofir:** D1, D2. Enter the reviewer password in the platform console (never in the repo or in chat). On the phone: sign in to the demo company, pick an order, pack one by scanning the label PDF off a screen.
- **Done when:** security-reviewer CLEAR, app-review confirms R1 closed, and Ofir's phone run is recorded in `PROVEN.md`. From here on all device testing uses the demo company.

## M4 — Native shell

- **Built:** native sign-in with Privacy and Terms links; native Account screen (name, role, company, sign out, delete account, privacy, terms, support); tab bar built from the user's roles (Pick hidden for roles that cannot pick; Dashboard becomes an admin-only "Manage" tab and is never the launch tab); signed-out Pack no longer opens the camera; SEC-15 and SEC-16 (exact-host checks, bridge ignores sub-frames); remove the unused photo-library permission string; iPhone-only target if D4 says so.
- **Agents:** from the approved blueprint (M1b): ios-designer (specs: `sign-in.md`, `me.md`, tab rules) → ios-engineer → programmer only if an endpoint is missing (own PR) → security-reviewer → app-review.
- **Ofir on the phone:** each TestFlight build — sign in, open Account, sign out, sign in as a worker and as an admin and see different tabs. Account deletion is tried only on the demo company.
- **Done when:** `iOS build` green, device script for that build proven, security-reviewer CLEAR, app-review marks K1, K2, K7 closed.

## M5 — Phone-built screens

- **Built:** `/m/today` (the launch screen), `/m/track` (label lookup), `/m/cleanup` (table clean-out, replacing the hop to the desktop page), each with a browser check modelled on `scripts/m_pick_check.py`. Colour per D8.
- **Agents:** from the approved blueprint (M1b): ios-designer (specs exist; update if D8 changes colour) → mobile-engineer → mobile-qa (PASS at SE / 16 Pro / Pro Max / iPad for every role) → security-reviewer on any new `/m/api/` route.
- **Ofir on the phone:** each screen in the demo company, in English and Spanish.
- **Done when:** mobile-qa PASS, each screen proven on a device, and app-review judges 4.2 (R2) no longer a realistic rejection: the app opens on Today, a worker never sees a desktop page.

## M6 — Listing, policy and public pages

- **Built:** privacy policy corrected (TikTok access is not read-only; credentials wording; full subprocessor list; what remains after deletion; third-party AI disclosure — K10 and the security report's privacy section); a real support page (K4); public pages on the domain chosen in D6 (K9); description and What's New rewritten to match the submitted build (R3, K8); App Privacy answers reconciled with the manifest (K11) and the new-hire document uploads either declared or kept out of the app; age-rating questionnaire (K12); screenshots at today's required sizes from the demo company; reviewer notes with the two logins and the label PDF; unlisted-distribution note if D5 says so.
- **Agents:** release-manager (listing, notes, screenshots, `ios/APP_STORE.md`); programmer for the page and template changes; app-review checks the result.
- **Ofir:** D5, D6, D7. Approve the policy wording (legal text — a lawyer's read is worth it) and give a public support contact. App Store Connect entries are made by Ofir; release-manager prepares the text to paste.
- **Done when:** every public URL answers (checked from outside), `ios/APP_STORE.md` has no open "☐ Ofir" item, app-review marks R3, K4, K8–K12 closed.

## M7 — Submission rehearsal, submission, Apple's review

- **Built:** nothing new. Full device script on the release build against the demo company, on iPhone (and iPad if kept); app-review full pass; security-reviewer final pass on everything merged since the baseline.
- **Agents:** device-test-lead → app-review (verdict APPROVE) + security-reviewer (CLEAR) → release-manager (submission checklist).
- **Ofir:** runs the script, then submits in App Store Connect. If Apple rejects: paste the message; app-review maps it to a guideline and an owner, and the fix goes back through the same path.
- **Done when:** Apple's status is "Ready for Distribution".

## M8 — Outside sellers (after approval)

- **Built:** SEC-5 and SEC-6 if not already done in M2; SEC-8 to SEC-14; a security pass over the desktop routes reachable from the Manage tab (several hundred, not covered by the baseline); production configuration check with Ofir (storage bucket privacy, headers, proxy settings); onboarding for a first outside company.
- **Agents:** programmer → qa → security-reviewer; architect for the route pass plan.
- **Ofir:** chooses the first outside seller; walks through their sign-up and first pick/pack on their phones.
- **Done when:** security-reviewer has no open BLOCK-EXTERNAL finding and the first outside company has packed a real order with the app.

---

## What is not known yet

- Whether the public pages on the production site answer today: the review tools could not reach the site, and the security review deliberately sent nothing to production.
- Everything Swift: both reviews judged it by reading the code. Only M1 and the later device rounds turn that into "proven".
- Apple's handling of 4.2 for a B2B app is a reviewer's judgement; M4 + M5 lower the risk, they do not remove it.
