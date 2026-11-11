# Live Ops Hub — mobile app (Capacitor)

A native iOS/Android shell for Live Ops Hub. It is **not** a thin web wrapper: it adds
real native capabilities (barcode scanning, push, offline awareness, in-app account
deletion) around the operations console, which satisfies Apple App Store Guideline 4.2.

- **App ID:** `com.btrade.liveopshub`  ·  **Name:** Live Ops Hub
- **Native shell:** `www/` (home with native Scan, Open console, Account/Delete)
- **Console:** the full web app opens in an in-app browser at `https://www.getwhatnot.com`

## Prerequisites (on your Mac)
- Node 18+ and npm
- Xcode 15+ with command-line tools, CocoaPods (`sudo gem install cocoapods`)
- An **Apple Developer Program** membership (organization, under Btrade LLC — needs the D-U-N-S number)

## First build
```bash
cd mobile
npm install
npx cap add ios          # and: npx cap add android
npx cap sync
npx cap open ios         # opens Xcode
```
In Xcode: select the project → Signing & Capabilities → set Team (your Apple Developer org),
confirm Bundle Identifier `com.btrade.liveopshub`, add the **Push Notifications** capability,
then run on a device or submit to TestFlight.

## Required iOS Info.plist keys
Add these (Xcode → Info):
- `NSCameraUsageDescription` → "Live Ops Hub uses the camera to scan product barcodes while packing."
- `NSPhotoLibraryAddUsageDescription` (only if you later save pack photos)
- Push: enable the Push Notifications + Background Modes (remote notifications) capabilities.

## Native plugins used
- `@capacitor-mlkit/barcode-scanning` — native barcode scanner (the core native value)
- `@capacitor/push-notifications` — order / ship-by alerts
- `@capacitor/network` — offline banner + queueing hook
- `@capacitor/browser` — in-app browser for the operations console
- `@capacitor/preferences`, `@capacitor/app` — storage / lifecycle

## Backend TODOs (so the app is fully Apple-compliant)
1. **Self-serve account deletion** — Apple requires account deletion to be completable in-app.
   The app opens `/me?delete=1`; add a confirmed "Delete my account" action there that deletes
   the user and triggers data deletion. (TikTok shop data deletion is already implemented via
   `/api/tiktok/forget` + the 30-day retention purge.)
2. **Push backend** — register device tokens and send order/ship-by notifications.
3. **Deep link** — `/scanit?code=` should accept a scanned code and jump straight to that product.

## App Store submission checklist
- [ ] App icon 1024×1024, **no alpha, square** (Apple rounds it) — flat-corner LoH mark
- [ ] Screenshots per device class (6.7"/6.5" iPhone, 12.9" iPad)
- [ ] Description, keywords, support URL (`https://liveopshub.com`)
- [ ] **Privacy policy URL** `https://liveopshub.com/privacy`
- [ ] **App Privacy** questionnaire — declare data types + subprocessors (see wms-tiktok-appstore-compliance.md)
- [ ] In-app **account deletion** (backend TODO #1)
- [ ] Guideline 4.2: native barcode scan + push + offline demonstrated
- [ ] TestFlight internal test passes, then submit for review

## Note
`ios/`, `android/`, and `node_modules/` are generated and git-ignored. Commit only the
`mobile/` source (config, `www/`, package.json). Build artifacts are created on your Mac.
