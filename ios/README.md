# LiveOpsHub for iOS

SwiftUI app for the LiveOpsHub (getwhatnot.com) backend. iPhone + iPad, iOS 17+.

| Tab | What it is | Served by |
|---|---|---|
| **Dashboard** | The real web dashboard, signed in — every screen the site has. Sign-in happens here. | `/` (web view) |
| **Pick** | The mobile Pick screen, built for the phone: choose a show, scan a label, tick items, done. Same server, same data and rules as the desktop `/pick`. | `/m/pick` (web view; code in `mobile/`) |
| **Pack** | Native. Scan a shipping label → see the box contents → record the packing video → upload. Auto-records after each scan (toggle in the toolbar). | `GET /api/shipment/<code>`, `POST /api/upload` |

## Scanning

Three ways, on every scan screen:

- **Bluetooth (or USB) handheld scanner.** Pair it in iOS Settings › Bluetooth in its keyboard (HID) mode. It then works at any moment, with nothing to tap: on **Pack** (`Components/HardwareScanner.swift`) and on **Pick** (`mobile/static/mobile.js`).
  On Pack the station is hands-free, like the web station: scan a label → recording starts → scan again → the video is saved; if that second scan was the next box's label, that box opens.
  While a scanner is connected iOS hides the on-screen keyboard; most scanners have a button (or a double-press) that brings it back.
- **Camera** (VisionKit) — the Pack tab's viewfinder, and `LOHubNative.scan()` from web pages.
- **Typing** the number.

## iPad

Supported in every orientation. The packing video and the camera preview follow how the device is held (`AVCaptureDevice.RotationCoordinator`), so an iPad on a stand in landscape records an upright landscape video.

## How it talks to the server

- Same signed session cookie as the web app (shared `HTTPCookieStorage`).
- `GET /api/mobile/session` on launch → sign-in state, roles, org, **CSRF token**. Every POST sends it in `X-CSRF-Token`; a stale token is refreshed and the request retried once.
- Every request sends `X-Client: lohub-ios/<version>`, so auth failures come back as JSON 401/403 instead of an HTML redirect.
- Packing videos: H.264 720p, recorded as QuickTime and **remuxed to MP4 without re-encoding** (fast start). The server detects MP4 and stores it as `video/mp4`.
- Forced upgrade: set `IOS_MIN_VERSION` on Railway; older builds show "Update required".

## Build & run (Mac)

```bash
brew install xcodegen
cd ios
xcodegen            # creates LiveOpsHub.xcodeproj from project.yml
open LiveOpsHub.xcodeproj
```

1. Target **LiveOpsHub → Signing & Capabilities** → Team: **Btrade LLC**. (Or put the Team ID in `project.yml` → `DEVELOPMENT_TEAM` and re-run `xcodegen`.)
2. Bundle ID is `com.liveopshub.ios`, registered to BTRADE LLC (team `4B4X663V8J`) on Nov 10 2026. It can't be changed after the first App Store upload. (`com.liveopshub.app` was already taken at Apple.)
3. Run on a real iPhone (the simulator has no camera; scanning falls back to typing).

`project.yml` is the source of truth; the `.xcodeproj` is generated and git-ignored.

## Ship to TestFlight / App Store

The App Store Connect record already exists: **Live Ops Hub**, iOS, bundle `com.liveopshub.ios`, SKU `liveopshub-ios`, company name BTRADE LLC.

**Automatic (no Mac needed).** `.github/workflows/testflight.yml` archives, signs and uploads a build whenever iOS code lands on `main`, or on demand from Actions → TestFlight → Run workflow. It needs three repository secrets (`ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8`) from an App Store Connect API key with the Admin role — the steps are at the top of that file. Build numbers come from the workflow run number.

**By hand, from Xcode.** Product → Archive (destination "Any iOS Device") → Distribute App → App Store Connect → Upload.

Either way the build appears under TestFlight after Apple processes it (10–20 min). Add internal testers there (your warehouse team) and test on the floor. For the store listing, fill it from `APP_STORE.md` → Submit for Review.

## CI

`.github/workflows/ios.yml` builds the app (unsigned, simulator) on a macOS runner on every change under `ios/`.
