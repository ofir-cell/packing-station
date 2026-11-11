# Pack (worker tab 3) — native in the app · web station `/` (`WORKER_HTML` / `STATION_HTML`) in browsers

**User:** a packer at a station. In the app it's a phone on a stand or in hand; in browsers it's an iPad or desktop station.
**Purpose:** scan a label, record the packing video, upload it, and move to the next order.

## In the app (owner: mobile-engineer / iOS)
The Pack tab is the existing SwiftUI `PackFlowView`. Designer requirements so it matches the web screens:
- Uses the same tokens: tint = `--brand` (#4f46e5 Classic, or the theme or tenant color passed through `/api/mobile/nav` as `brand.hex`), primary buttons as a gradient capsule 52pt high, DM Sans (bundled), SF Symbols.
- Root: large title "Pack", a hero showing "{n} packed today", the primary "Scan label" in the bottom action area, and "Type it instead" as a secondary.
- Recording: full-bleed camera, a top pill with the order (buyer · items), a big red stop button (≥72pt) centered above the home indicator, and the elapsed time.
- Upload: inline progress; never block the next scan (it queues). After a pack, haptic `success` and a toast "Packed · uploading".
- `LOHubNative.pack(code)` deep link opens straight into recording for that label.
- No "Switch to Picking" button: the tab bar does that.

## In mobile Safari / iPad station (web `/`)
Not in this round's scope beyond the global layer (G1–G6). Ticket for the next round: `screens/pack-station.md` (an iPad landscape layout). The current "📦 Switch to Packing / Picking" top-bar link is replaced by the web tab bar on phones (G8).
