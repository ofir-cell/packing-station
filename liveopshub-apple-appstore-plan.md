# Live Ops Hub — Apple App Store readiness plan

Goal: ship Live Ops Hub as an iOS/iPadApp on the App Store. The app is already a web app on iPad, so the fastest compliant path is a **hybrid wrapper with real native features** (Apple rejects thin web wrappers under Guideline 4.2).

## 1. Account & legal (start now — has lead time)
- **Apple Developer Program** — $99/yr. For an **organization** account under *Btrade LLC* you need a **D-U-N-S number** (free from Dun & Bradstreet; 1–14 days). Start this first — it's the long pole.
- Legal entity, address, support email: Btrade LLC · 4322 SW 84th Ter, Davie, FL 33328 · ofir@5secbeauty.com.
- **Privacy Policy URL**: https://liveopshub.com/privacy (already drafted).

## 2. Technical approach — Capacitor hybrid (recommended)
Wrap the existing Live Ops Hub web UI in a native shell and add native capabilities that justify a standalone app:
- **Native barcode scanning** (camera) — core to packing; a real native value-add (passes 4.2).
- **Push notifications** — new LIVE orders, "ship-by" deadlines.
- **Offline-tolerant mode** — queue scans when connectivity drops on the floor.
- **Camera/photo capture** — pack verification photos.

Why Capacitor: reuses the entire existing web app, adds native plugins (Camera, Push, Haptics, Filesystem), one codebase, fastest to store. Alternatives: React Native (more rewrite) or full Swift (most work). 

## 3. Apple review requirements (Guideline-mapped)
| Area | Requirement | Plan |
|---|---|---|
| **4.2 Minimum functionality** | Not just a website | Native barcode scan + push + offline (above) |
| **5.1.1 Privacy** | Privacy policy + App Privacy "nutrition label" | Use liveopshub.com/privacy + declare data types (orders, addresses, email) and subprocessors |
| **Account deletion** | In-app account deletion if accounts exist | Add "Delete account" in app settings |
| **Sign in** | If you offer third-party login, offer Sign in with Apple | Current login is badge/employee — confirm whether Apple-login is triggered |
| **5.1.1(v) Data collection** | Clear consent + minimal data | Read-only TikTok scopes, least-privilege |
| **2.1 Completeness** | No crashes, works on review | TestFlight pass before submit |
| **Permissions** | Purpose strings | Add `NSCameraUsageDescription` ("scan order barcodes"), push consent |

## 4. Listing assets (App Store Connect)
- **App icon 1024×1024**, no alpha, no rounded corners (Apple rounds it). *(I'll export a flat-corner version of the LoH icon.)*
- **Screenshots** per device class (6.7"/6.5" iPhone, 12.9" iPad) — from the real app.
- Name, subtitle, description, keywords, support URL (liveopshub.com), privacy URL.
- **App Privacy** questionnaire (data types + usage).

## 5. Build & submit flow
1. D-U-N-S → enroll in Apple Developer Program (org).
2. Scaffold Capacitor around the web app; add Camera/Push/Offline plugins + purpose strings.
3. Implement in-app **Delete account**.
4. Internal test → **TestFlight** → fix review blockers.
5. Create the App Store Connect listing (assets §4) → submit for review.
6. Review typically a few days to ~2 weeks.

## 6. Shared wins with TikTok (do once, use twice)
Privacy Policy, least-privilege scopes, and data-deletion-on-deauthorization satisfy **both** TikTok App Review and Apple. Build them once.

## 7. What I can build vs what needs you
- **I can build:** the Capacitor scaffold + native-plugin wiring, the in-app Delete-account flow, purpose strings, the flat-corner 1024 icon, listing copy, App Privacy answers.
- **You must do:** D-U-N-S registration, Apple Developer enrollment + payment, signing certificates on your Apple ID, real device screenshots, final submit (Apple account actions are yours).
