# Pack (tab 3) — native (`ios/LiveOpsHub/Features/Pack/`)

**Blueprint:** S6, flow 4.4, rules 5.1, 5.3, 5.4, 5.9, piece N8. **Release: 1.0. Exists; gaps in "Requirements the build does not meet yet". Owner: ios-engineer.**
**Mockup:** the Pack tab's place in the bar is in [`../mockups/tabbar.html`](../mockups/tabbar.html); the screen itself is not drawn in this round.
**User:** a packer at a table — phone in hand or on a stand, iPad on a stand in landscape, Bluetooth/USB scanner, hands full. Roles: worker, cs, manager, admin. A host has no Pack tab.
**Purpose:** scan a label, see what goes in the box, record the packing video, save it, next box.

The browser packing stations (`/`, `WORKER_HTML`) are not part of the app and are not specified here; the floor keeps them unchanged.

## Look
- **LiveOpsHub indigo, fixed** (board D8): the tint is the app's accent colour (DESIGN_SYSTEM §1.6) for every company. No colour is passed from the server and none is read from the company.
- Primary button: indigo → violet gradient capsule, 52pt high, white label. SF Symbols. Light and dark follow the system.
- English and Spanish for every string (blueprint rule 5.2; today Pack is English only — N8c).

## Layout
1. **Scan stage** (tab root). Large title "Pack". Hero line "{n} packed today". Bottom action area: primary **"Scan label"** (camera) and secondary "Type it instead". A Bluetooth/USB scanner works with nothing tapped. The "start recording automatically" switch stays (on by default).
2. **Box stage.** Top card: buyer · "{n} item(s)"; the list of contents, combined packages and giveaways included. Camera preview below. With auto-record on, recording starts as the box opens.
3. **Recording.** Full-bleed camera; a top pill with the order (buyer · items) and the elapsed time; a red stop button ≥ 72pt centred above the home indicator. A second scan stops and saves; if that scan was the next box's label, that box opens after the save.
4. **Saving → Packed.** Upload progress inline, then "Packed" with a success haptic, then back to the scan stage for the next label.
5. `LOHubNative.pack(code)` (from Track) opens the box stage for that label.

There is no "Switch to Picking" control; the tab bar does that.

## When the upload fails — 1.0 requirement (blueprint flow 4.4, N8a)
The earlier draft of this spec said the upload "never blocks the next scan (it queues)". **That is not what the app does**: by reading `PackFlowView.swift` `stopAndUpload`, the recording file is removed when the upload fails, so the box must be filmed again. The requirement for 1.0 is:

1. **Keep the recording.** A recording is deleted from the device only after the server has accepted it. A failed upload, a lost connection, an expired session, the app going to the background or being closed — none of them delete it.
2. **Retry.** The app retries the upload by itself (when the connection returns, when the app comes back to the front, after sign-in), and the packer can retry by hand at any time.
3. **Tell the packer.** The screen says, in words, that the video is not saved yet: "Video not saved yet — we'll keep trying." with **"Try again"**. It never shows "Packed" for that box until the server accepted the video.
4. **The server is the record.** The order shows as packed only after the server said so (rule 5.4); the app marks nothing packed on its own, so stock is still deducted exactly once.
5. **The packer is not stuck.** While a video is waiting, the next label can be scanned and the next box recorded. A persistent line on the scan stage says how many are waiting: "1 video waiting to upload" (tap → the list, each with its buyer, time and "Try again").
6. **Nothing is lost quietly.** If a waiting video can no longer be sent (the order was cancelled meanwhile, the server refuses it), the app says which box and why, and keeps the file until the packer dismisses it.

How many videos may wait, how long they are kept, and how much storage they may use are not set by the blueprint (see "Open points").

## States
| State | Treatment |
|---|---|
| Unknown label | "Shipment not found" with the code that was scanned; stays on the scan stage |
| Cancelled order | full-width red: "This order is cancelled — don't ship it." Error haptic |
| **A scan while a box is open but not recording, or while saving** | today it is ignored silently. Required: say so — "Finish this box first" (not recording: "Start recording or go back"), with the scanned code. A scan is never dropped silently (blueprint §4, "Wrong scan", and flow 4.4) |
| No network at the scan | "Can't reach LiveOpsHub. Check the connection and scan again." Nothing is looked up from memory |
| No network at the save | "When the upload fails" above |
| Session ended | the shell shows Sign-in (not "Open the Dashboard tab and sign in" — N8b). After sign-in the person is back on Pack and a waiting video uploads |
| **Camera refused** | the label can still be scanned with a hardware scanner or typed; without the camera there is no video. A full-stage message: "Pack needs the camera to record the packing video." + "Open Settings". No recording, so no "Packed" |
| Microphone refused | recording works without sound; no blocking message |
| Wrong role | no Pack tab; a stale entry gets "Your account can't open this. Ask your manager." |
| Demo company | a "Demo company" line on the scan stage; nothing else differs in the app |

## Copy (EN / ES)
Pack / Empacar · Scan label / Escanear etiqueta · Type it instead / Escribirlo · {n} packed today / {n} empacados hoy · Packed / Empacado · Shipment not found / Envío no encontrado · This order is cancelled — don't ship it. / Este pedido está cancelado — no lo envíes. · Video not saved yet — we'll keep trying. / El video aún no se guardó — seguiremos intentando. · Try again / Reintentar · {n} video(s) waiting to upload / {n} video(s) esperando para subir · Finish this box first / Termina esta caja primero · Pack needs the camera to record the packing video. / Empacar necesita la cámara para grabar el video de empaque. · Open Settings / Abrir Ajustes. Spanish is a first draft.

## Requirements the build does not meet yet (ios-engineer)
| # | Gap | Source |
|---|---|---|
| 1 | A failed upload deletes the recording | N8a — section above |
| 2 | A lost session tells the packer to open the Dashboard tab | N8b, K7a |
| 3 | English only | N8c, P3 |
| 4 | A scan while a box is open and not recording is ignored without a word | flow 4.4 |
| 5 | Camera-refused state | flow 4.4 |
| 6 | Tint follows nothing but the app's indigo | D8, N16 |

## Open points — for app-planner
- Limits for waiting videos: how many, for how long, what happens when the device is out of space, and whether a waiting video survives sign-out by a *different* person on a shared device (it belongs to the company, but the uploader's session is gone).
- Whether "Packed" may be shown as "Packed — video uploading" for the box in front while the upload runs in the background. This spec says no: "Packed" only after the server accepted the video.

## Acceptance
*Compiles* and *proven on a device* are separate statements (CLAUDE.md). On a device: with Wi-Fi off at the save, the packer can scan and record the next box; with Wi-Fi back, both videos arrive, each order is packed once, and neither had to be filmed again.
