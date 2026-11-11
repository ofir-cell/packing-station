# App Review baseline — LiveOpsHub iOS (2026-11-05)

Reviewer: app-review agent · Branch `feat/mobile-redesign` @ `194e7ca` · Build under review: `ios/` v1.0.0 (1)
Sources read online on **2026-11-05**: App Store Review Guidelines (developer.apple.com/app-store/review/guidelines/, sections 1.5, 2.1, 2.3.1, 2.3.3, 2.3.7, 3.1.1, 3.1.1(a), 3.1.3(b)(c)(e)(f), 4.0, 4.2–4.2.3, 5.1.1(i)(ii)(v), 5.1.2(i)); App Review Help "Provide information for a complete review"; "Offering account deletion in your app"; Guideline reference 5.1.1(v); "Unlisted App Distribution"; App Store Connect "Set distribution methods"; HIG "Tab bars" (change log last entry June 8, 2026). The guidelines page itself shows no last-updated date.

---

## 1. Verdict today

**Would be rejected.** Two blockers would stop review before the reviewer sees anything else, and one more is likely after that:

1. **Guideline 2.1, Information Needed (most likely first rejection).** No demo account exists yet (`ios/APP_STORE.md:62-63`). The planned demo account is an **admin**, and 2FA is **mandatory for admins** (`app.py:764-766`). An admin who hasn't enrolled is held on `/me` until they enroll (`app.py:3913-3923`). The reviewer would need an authenticator app, or a TOTP code that expires in 30 s, which can't go in the Notes. Apple: *"If your app requires an authentication code … include it in the Notes field in advance. Without it, a call may be required"* (App Review Help, complete-review).
2. **Guideline 2.1 / 2.3.1, inaccurate review notes.** The notes tell the reviewer to use a **"Pick tab"** and an **"Account tab"** (`ios/APP_STORE.md:69`). The app has two tabs, **Dashboard** and **Pack** (`ios/LiveOpsHub/App/LiveOpsHubApp.swift:28-37`). Sample tracking numbers are still a placeholder (`ios/APP_STORE.md:71`).
3. **Guideline 4.2 (Minimum Functionality) is the most likely rejection once the reviewer gets in.** The app opens on a full-screen WKWebView of getwhatnot.com (`LiveOpsHubApp.swift:19,55-60`). It shows desktop-derived pages with web chrome (☰ / ← Back / 🏠), horizontal overflow, sub-16 px inputs that make iOS zoom on focus, and unstyled default buttons (evidence in §2). The native **Pack** flow (VisionKit scanner, AVFoundation recording, haptics, upload) is real app functionality and is our main argument. Today it sits on the second tab, and only one web screen (badge login) uses the native bridge.

Things that pass today: sign-in without a badge scanner, account deletion in the UI, camera and microphone usage strings, ATS/encryption flag, and no ad or tracking SDKs.

---

## 2. Ranked findings

Severity: **Blocker** = rejection is near-certain · **High** = likely rejection or a removal risk · **Med** = reviewer-dependent · **Low** = polish or hygiene.

| # | Guideline | Sev | Evidence | Fix |
|---|---|---|---|---|
| 1 | 2.1(a), Before You Submit "full access" | **Blocker** | `ios/APP_STORE.md:62-63` (demo account ☐). `app.py:764-766` (2FA required for every admin). `app.py:3913-3923` (un-enrolled admin locked to `/me`) | Create a demo company plus `appreview` with ~10 sample orders and an **active** (not trialing/expired) subscription. Add a per-user `twofa_exempt: true` flag that `_twofa_required()` honors, and set it only on `appreview`. Also give a non-admin (`appreview-worker`) login in the Notes, as Apple asks for each account type. |
| 2 | 2.1(a) / 2.3.1(a) | **Blocker** | `ios/APP_STORE.md:69` mentions "Pick tab" and "Account tab", which don't exist. `:71` has the sample-tracking placeholder | Rewrite the Notes for the real flow: "Dashboard tab → ☰ → Pick … · ☰ → My Profile → Delete my account · Pack tab → scan label." Paste 3 real demo tracking numbers and attach a printable PDF of sample labels (barcodes the reviewer can scan off a screen). |
| 3 | 4.2 / 4.2.2 (repackaged website) | **High** | `LiveOpsHubApp.swift:19` (default tab = web). Screens: `audit/20261105-223237/pro/admin/admin__shows.png` (page is 543 px wide on a 393 px screen, +150 px overflow, row actions cut off), `pro/admin/home.png` (show names truncated to "S" and "\|", a dark gradient band down the left edge from the off-canvas drawer, web ☰/Back/🏠 header), `pro/admin/admin__inventory.png` (desktop forms, "Choose File" controls, table clipped), `pro/admin/me.png` (unstyled default 2FA buttons). `audit/…/report.md`: 178 screens; e.g. `/admin/inbound` has 27 inputs under 16 px (iOS zooms on focus) and 89 tap targets under 44 px | (a) Make **Pack** (or a native "Today" screen) the launch tab. (b) Add a native top bar and native Account/Settings screen so navigation isn't web chrome. (c) In the web app, under `.lohub-ios`: hide the web header and drawer and set every input to font-size ≥16 px. Fix overflow on `/admin/shows`, `/admin/roster`, `/admin/inbound`, `/admin/sku-lookup`, `/dashboard`. (d) Wire `LOHubNative.scan()` into the inventory, SKU and track inputs and `LOHubNative.pack()` into the pick→pack hand-off, so native capabilities show up across flows, not only on badge login (`templates.py:2359`). (e) In the review notes, name the native features (VisionKit scanner, AVFoundation packing video, haptics, share sheet for exports). |
| 4 | 3.1.1 / 3.1.1(a) / 3.1.3 | **High** (whenever the reviewer lands on it) | `templates.py:12148,12155` ("Choose Starter $149/mo", "Choose Pro $399/mo" buttons that request an invoice). `app.py:3884-3907` redirects **every** page to `/billing` when the trial has expired or the subscription is inactive. Screenshot `pro/admin/billing.png` | 3.1.3(c) Enterprise Services covers us (sold only to companies for their staff). But 3.1.3 says such apps *"cannot, within the app, encourage users to use a purchasing method other than in-app purchase, except for apps on the United States storefront"*. For the iOS client (UA `LiveOpsHubiOS` or `X-Client: lohub-ios`), serve a billing page with **no prices, no plan buttons and no mailto-to-buy**, only: "Your company's plan is managed by your administrator." Keep the demo company's subscription active. The US-only exception (3.1.1(a)) isn't worth relying on if we ship worldwide. |
| 5 | 5.1.1(i) privacy policy reachable in-app | **High** | `ios/LiveOpsHub/Components/LegalLinks.swift:5-11` is defined but **never used** (grep finds no references). The login page has no privacy or terms link (`templates.py:495-514`). The only in-app link is `/me` → `https://liveopshub.com/privacy` (`templates.py:2655`): a different domain, which opens in Safari (`DashboardWebView.swift:112-114`) and isn't the URL in ASC (`getwhatnot.com/privacy`) | Add a native Account/Settings sheet (gear in the Pack nav bar and a Dashboard toolbar item) with Privacy Policy, Terms, Support (mailto), Sign out and Delete account, using `LegalLinks`. Add privacy and terms links under the login form. Change `templates.py:2655` to `/privacy`. |
| 6 | 5.1.1(v) account deletion | **Med** | Deletion exists (`/me`, `templates.py:2652-2657`, API `app.py:4808`). It is **unreachable** in two states: (a) tenant locked → `/me` isn't in `_BILLING_OPEN_PATHS` (`app.py:3888`), so the user is sent to `/billing`; (b) admin with 2FA pending → `/api/account/delete` isn't in `_2FA_SETUP_OPEN` (`app.py:3913`), so the button returns 403. The old native "Delete account" entry was removed | Add `/me` (or a slim `/account/delete` page) to `_BILLING_OPEN_PATHS`. Add `/api/account/delete` and `/api/mobile/session` to `_2FA_SETUP_OPEN`. Put "Delete account" in the native Account sheet (deep-link `/me?delete=1`, which is already supported at `templates.py:2752`). |
| 7 | 5.1.1(i) / 5.1.2(i) policy accuracy, third-party AI | **Med** | `site/privacy.html`: "we do not write to your TikTok Shop", yet the service creates shipping labels (`ios/APP_STORE.md:130` already flags this). The policy lists **Anthropic** for address parsing. 5.1.2(i) now says: *"You must clearly disclose where personal data will be shared with third parties, including with third-party AI, and obtain explicit permission before doing so."* | Ofir/legal: correct the "read only" sentence. Keep the Anthropic disclosure, state that it is a processor acting for the seller (B2B), and make sure the customer agreement and Terms cover consent. If any staff personal data goes to AI, add an in-app disclosure. |
| 8 | 5.1.1 / App Privacy label, privacy manifest accuracy | **Med** | `PrivacyInfo.xcprivacy:9-51` declares Name, UserID, Photos/Videos, Audio. The policy says the app also collects staff **email** and processes buyer **name and shipping address**. `ios/APP_STORE.md:84-86` lists "Other User Content" and claims "This matches PrivacyInfo.xcprivacy", which is false | Add `NSPrivacyCollectedDataTypeEmailAddress` and `NSPrivacyCollectedDataTypeOtherUserContent` (plus PhysicalAddress if the reviewer counts buyer addresses), all linked, App Functionality, not tracking. Mirror them in the ASC nutrition label. |
| 9 | 1.5 Developer Information | **Med** | `ios/APP_STORE.md:20` sets Support URL to `/apply`, a sales lead form, not support. LegalLinks has `supportEmail` but nothing shows it | Point Support URL at a real page (e.g. `/support-info` or the privacy contact section) with email, address and response time. Show a support email in-app (Account sheet). |
| 10 | 2.1 / 4.0 iPad | **Med** | `project.yml:54` sets `TARGETED_DEVICE_FAMILY "1,2"` and `:43-47` enables iPad landscape. Camera preview and recording rotation are hard-coded to 90° (`PackingRecorder.swift:67,173`), so on iPad landscape the preview and the saved video come out sideways. ASC would also require 13" iPad screenshots (`APP_STORE.md:89`) | v1: set `TARGETED_DEVICE_FAMILY: "1"` (iPhone only; it still runs on iPad in compatibility mode). Or use `AVCaptureDevice.RotationCoordinator` and an iPad-specific layout before adding iPad. |
| 11 | 2.3.7 metadata / trademarks | **Med** | Keywords `tiktok shop,whatnot` (`APP_STORE.md:53`). Production domain and privacy URL are `getwhatnot.com`, which uses a competitor's mark (Whatnot Inc.) | Drop third-party marks from Keywords (descriptive mentions in the Description are fine). Move the app's public URLs (privacy, support, marketing) to `liveopshub.com` before submission so ASC metadata doesn't depend on a "whatnot" domain. |
| 12 | 2.3.3 / 2.3.1 demo data | **Low** | Screens show a real operator's data ("Ofir Admin", "5 Second Beauty", "Peach/Hera/Sydney B LIVE") in `pro/admin/home.png`, `setup.png`, `pick.png` | Seed the demo company and screenshots with neutral fictional data. |
| 13 | 2.1 stale web | **Low** | Most pages log 1 JS error in the audit. Most are harness network errors (`ERR_TUNNEL_CONNECTION_FAILED`), but manager sees `"Access denied" is not valid JSON` on `/users`, `/users/badges`, `/admin/permissions`, `/admin/equipment` | Return JSON 403s to fetch callers and hide menu items a role can't open, so a reviewer on a manager account never hits a broken screen. |
| 14 | 2.1 / 5.1.1 2FA QR | **Low (fixed, verify)** | Audit shows the CSP blocking `qrcode.min.js` on `/me`. HEAD `194e7ca` allows that file (`app.py:4012`). Admin `me.png` also shows "0 recovery codes left" | Re-run the audit and confirm the QR renders inside the WKWebView. |
| 15 | HIG / polish | **Low** | `UpdateRequiredView` opens the generic App Store (`LiveOpsHubApp.swift:157`). Web pages are light-only while native screens follow dark mode. The bridge host check `hasSuffix("getwhatnot.com")` also matches `evilgetwhatnot.com` (`DashboardWebView.swift:88,207`) | Link to `itms-apps://apps.apple.com/app/id<APPID>`. Add a dark theme under `.lohub-ios` or force light in the app (`.preferredColorScheme(.light)`) for consistency. Match `h == host \|\| h.hasSuffix(".getwhatnot.com")`. |

Checked and passing:
- **Sign-in without a badge scanner.** The iOS UA is sent to `/login` (`app.py:4436-4437`), and the badge page scans with the iPhone camera through `LOHubNative.scan()` (`templates.py:2359-2363`).
- **2FA completes in-app.** TOTP step on `/login` (`templates.py:505-509`), enrollment on `/me`, and recovery codes.
- **Usage strings** are specific and true (`project.yml:35,48-49`). Microphone is optional (`PackingRecorder.swift:26`).
- **Other app-like behavior.** No ATT or tracking, `ITSAppUsesNonExemptEncryption=false`, JS dialogs are native, downloads go to the share sheet, there's an offline state, and haptics are present.

---

## 3. Gates

### Before TestFlight **external** testing (requires Beta App Review)
- [ ] PR #34 backend live (`/api/mobile/session`, MP4 upload, `/privacy`) on the URL the build points to.
- [ ] Demo company with an active plan, `appreview` admin with **2FA exemption** (finding 1), plus a worker account.
- [ ] Review/beta notes rewritten for the real two-tab flow, with sample tracking numbers and a label PDF (finding 2).
- [ ] Privacy policy URL live and reachable from inside the app, including signed out (finding 5).
- [ ] Deletion reachable in every state (finding 6).
- [ ] iPhone-only, or the iPad rotation fix (finding 10). Device-tested on at least one iPhone with no crash on scan → record → upload.
- [ ] iOS billing page has no prices or CTAs (finding 4). A beta reviewer can hit this too.

### Additionally before **App Store** submission
- [ ] 4.2 hardening (finding 3): native launch screen/tab, native Account sheet, web header hidden in-app, inputs ≥16 px, overflow fixed on the 5 worst pages, bridge used beyond badge login.
- [ ] Privacy manifest and nutrition label corrected (finding 8). Policy text corrected, including the AI disclosure (finding 7).
- [ ] Support URL with real contact info (finding 9). Keywords without third-party marks; public URLs on liveopshub.com (finding 11).
- [ ] Screenshots (6.9" iPhone; iPad only if iPad is kept) from neutral demo data showing the app in use, not login (2.3.3, finding 12).
- [ ] Re-run `scripts/mobile_audit.py` with the 0 overflow / ≥44 px / ≥16 px gates green for the worker and manager roles at least.

---

## 4. Public listing vs. unlisted distribution

**Recommendation: ship v1.0 as an Unlisted App.** Revisit a public listing once the native surface covers pick, lookup and today's numbers.

- **Fit.** Apple names "partner sales tools, employee resources" as good candidates and lists audiences such as "part-time employees, franchisees, partners, business affiliates" and "employee-owned devices that aren't eligible to be managed through Apple Business." That describes LiveOpsHub well: warehouse staff of seller companies, often on their own phones, with logins created by their admin and no public sign-up.
- **What it doesn't avoid.** Unlisted apps still go through App Review. Apple declines the request if the app "hasn't been submitted to App Review" or is "in a beta or prerelease state." So findings 1–2 and 4–11 still apply, and a demo account is still needed. Apple's pages don't say whether 4.2 is applied more leniently to unlisted apps, so don't count on it. The benefit is lower metadata and marketing exposure (no search or charts), which takes care of most of finding 11 and lowers 4.2 pressure from "is this useful to the public."
- **How.** Submit as a normal public app with a Review Notes line saying "intended for unlisted distribution," then file the unlisted request form. Customers get a direct link (put it in the onboarding email and on `/setup`). Apple's own advice ("implement a mechanism within your app to prevent unauthorized use") is already met by admin-created logins.
- **Not Private/Custom (Apple Business Manager).** Every seller would need its own ABM organization ID, which small TikTok/Whatnot sellers mostly don't have. ABM can also still reach unlisted apps.
- **Watch-out.** Distribution can't be changed after approval, except public → unlisted. Going from unlisted back to public isn't documented as a switch and may need a new app record. That's acceptable for a B2B tool. If public discovery (TikTok Shop App Store tie-in) becomes a goal, plan it as v2 with the full 4.2 work done.

---

## 5. Follow-ups for `ios/APP_STORE.md`
Not edited in this baseline (scope was this file only). When the reviewer flow is fixed, update §1 "Notes for the reviewer" (tabs, 2FA exemption, label PDF, unlisted note), the Support URL, Keywords, and the App Privacy table.
