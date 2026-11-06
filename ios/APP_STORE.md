# Store submission kit — LiveOpsHub

Everything to paste into App Store Connect and the TikTok Shop Partner Center listing.
Items marked **☐ Ofir** need you (accounts, money, real data).

---

## 1. App Store Connect

### App information
| Field | Value |
|---|---|
| Name | LiveOpsHub |
| Subtitle (30) | Pick, pack & prove live orders |
| Category | Primary: **Business** · Secondary: **Productivity** |
| Bundle ID | `com.liveopshub.app` |
| Age rating | 4+ (no objectionable content) |
| Price | Free (no in-app purchases) |
| Privacy Policy URL | https://www.getwhatnot.com/privacy |
| Support URL | https://www.getwhatnot.com/apply |
| Marketing URL | https://www.getwhatnot.com |
| Copyright | 2026 Btrade LLC |

### Promotional text (170)
Every live-sale order, picked right and packed on camera. Scan the label, record the box, and settle "missing item" claims with a video in seconds.

### Description
LiveOpsHub is the warehouse app for TikTok Shop and Whatnot live sellers. After every live, your team picks, packs and ships hundreds of orders. LiveOpsHub keeps that fast and keeps proof of every package.

PACK WITH PROOF
• Scan the shipping label with the iPhone camera
• See exactly what goes in the box, including combined packages and giveaways
• Recording starts automatically. Tap Stop, and the packing video is saved to the order
• When a buyer says an item was missing, pull up the video in seconds

PICK WITHOUT MISTAKES
• Pick queue per live show
• Tap items off as you pull them, or scan a label to jump to its order
• Built-in checks stop picking a cancelled order, or a show whose table hasn't been cleared

KNOW WHERE EVERY ORDER STANDS
• Look up any label: picked, packed, shipped, and by whom
• Today's numbers for you and your warehouse: orders to pick, orders to pack, open shows

BUILT FOR LIVE COMMERCE
• Orders sync from TikTok Shop automatically after each live
• Works alongside the LiveOpsHub web dashboard your managers already use
• Each company's data is fully isolated

LiveOpsHub is for businesses using the LiveOpsHub service. Your company admin creates your login. New companies can request access at getwhatnot.com.

### Keywords (100)
`warehouse,packing video,fulfillment,tiktok shop,whatnot,live selling,pick pack,barcode,shipping,orders`

### What's New (v1.0)
First release: pack with video proof, pick by show, label lookup, and daily stats.

### App Review information
| Field | Value |
|---|---|
| Sign-in required | Yes |
| Demo username | **☐ Ofir**: create `appreview` (role **admin**) in a demo company with sample orders |
| Demo password | **☐ Ofir** |
| Contact | Ofir Rashtty · ofir@5secbeauty.com · (859) 489-1528 |

**Notes for the reviewer** (paste as is):
> LiveOpsHub is a business tool for warehouse staff of TikTok Shop / Whatnot sellers. Accounts are created by each company's admin in the LiveOpsHub web dashboard, so the app has no public sign-up. Prospective companies request access at getwhatnot.com/apply. Nothing is sold in the app.
>
> To test: sign in with the demo account. **Pack** tab: point the camera at any of the sample labels below (or type a tracking number). The order contents appear and a packing video starts recording. Tap "Stop & save". **Pick** tab: open an order and tap items to pick them. **Account** tab → "Delete my account" permanently deletes the login.
>
> Sample tracking numbers in the demo account: **☐ Ofir: paste 3 from the demo company**
>
> Camera: scans labels and records packing videos. Microphone: audio in packing videos.

### App Privacy ("nutrition label")
Answer **Yes, we collect data**. None of it is used for tracking.

| Data type | Linked to user | Purpose |
|---|---|---|
| Contact Info → Name | Yes | App Functionality |
| Identifiers → User ID | Yes | App Functionality |
| User Content → Photos or Videos | Yes | App Functionality |
| User Content → Audio Data | Yes | App Functionality |
| User Content → Other User Content (order/shipping records of your customers' buyers) | Yes | App Functionality |

This matches `LiveOpsHub/Resources/PrivacyInfo.xcprivacy`.

### Screenshots **☐ Ofir** (I can produce them from the demo account once it exists)
Required sizes: **6.9"** (1320×2868) and **13" iPad** (2064×2752). Suggested set:
1. Pack: camera recording with the order contents card
2. Packed ✓ confirmation
3. Pick queue for a show
4. Order picking with items checked off
5. Lookup result (picked by / packed by)
6. Today: warehouse to-pick / to-pack

### Export compliance
`ITSAppUsesNonExemptEncryption = false` is already set (HTTPS only), so no question at upload.

---

## 2. TikTok Shop App & Service Store (Partner Center)

*Waiting for TikTok to unlock a Public app category on your account (open Lark ticket). Once it's unlocked:*

| Field | Value |
|---|---|
| Type | **Public** |
| Category | Order management / Fulfillment (whatever TikTok enables) |
| Name | LiveOpsHub |
| Logo | `ios/LiveOpsHub/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png` (1:1, PNG) |
| Redirect URL | https://www.getwhatnot.com/api/tiktok/callback |
| Webhook URL | https://www.getwhatnot.com/api/tiktok/webhook |
| Privacy policy | https://www.getwhatnot.com/privacy |
| Terms | https://www.getwhatnot.com/terms |
| Support | ofir@5secbeauty.com |

**Short description:** Pick, pack and ship your LIVE orders with video proof of every package.

**Long description:** After every LIVE, LiveOpsHub pulls your TikTok Shop orders, groups them by show, and runs your warehouse floor: pick lists, label scanning, combined packages, and a packing video saved to every order. Turn "item missing" claims around in seconds with the video, and see in real time how many orders are still to pick and pack. Available on the web and as an iPhone/iPad app.

**Scopes to request:** only what the app actually calls today: orders (read), fulfillment / shipping documents (labels), shop info, authorization. Keep the same list as the current Custom app ("Live Ops Hub", ID 7698696266553149197) so the review matches the code.

---

## 3. Open items before submitting

- [ ] **☐ Ofir**: merge PR #34 (backend) so `/api/mobile/session`, MP4 uploads and `/privacy` go live, before testing the app against production.
- [ ] **☐ Ofir**: demo company + `appreview` account with ~10 sample orders.
- [ ] **☐ Ofir**: check the privacy policy wording. It says "we do not write to your TikTok Shop", but the app creates TikTok Shipping labels (that is a write). I didn't change it; it's your legal text.
- [ ] Python CI on `main` fails on `check_js.py` (LIVE_HTML block 0, from before this work). It's worth fixing so the "Wait for CI" deploy gate means something.
