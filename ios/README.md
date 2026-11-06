# LiveOpsHub for iOS

Native SwiftUI client for the LiveOpsHub (getwhatnot.com) backend. iPhone + iPad, iOS 17+.

| Tab | What it does | Server endpoints |
|---|---|---|
| **Pack** | Scan a shipping label → see the box contents → record the packing video → upload. Auto-records after each scan (toggle in the toolbar). | `GET /api/shipment/<code>`, `POST /api/upload` |
| **Pick** | Pick queue by show, tap items off, scan a label to jump to its order, mark order picked. Respects the cleanout / cancelled-items / already-picked gates. | `GET /api/pick/queue`, `GET /api/pick/<sid>`, `POST /api/pick/item/<id>/toggle`, `POST /api/pick/complete/<sid>` |
| **Lookup** | Scan or type any label: status, who picked/packed it, items. | `GET /api/shipment/<code>` |
| **Today** | Your packs today / this month / rank; for admin & CS, to-pick / to-pack per show. | `GET /api/me/stats`, `GET /api/home/fulfillment` |
| **Account** | TikTok Shop connections (admin, in-app web view), privacy, terms, support, sign out, **delete account** (Apple 5.1.1(v)). | `/admin/tiktok`, `POST /api/account/delete` |

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
2. Bundle ID is `com.liveopshub.app`. Change it in `project.yml` first if you want another — it can't be changed after the first App Store upload.
3. Run on a real iPhone (the simulator has no camera; scanning falls back to typing).

`project.yml` is the source of truth; the `.xcodeproj` is generated and git-ignored.

## Ship to TestFlight / App Store

1. App Store Connect → **My Apps → +** → New App: iOS, name "LiveOpsHub", bundle `com.liveopshub.app`, SKU `liveopshub-ios`.
2. Xcode → **Product → Archive** (destination "Any iOS Device") → **Distribute App → App Store Connect → Upload**.
3. Build appears in TestFlight in ~15 min → add internal testers (your warehouse team) → test on the floor.
4. Fill the listing from `APP_STORE.md` → **Submit for Review**.

## CI

`.github/workflows/ios.yml` builds the app (unsigned, simulator) on a macOS runner on every change under `ios/`.
