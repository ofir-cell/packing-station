# TikTok Shop — App Review demo video script (Live Ops Hub)

Purpose: the screen-recording TikTok's partner reviewers require when you convert the
Custom app to a **public** app. It must show, end to end, that every API scope you
requested is actually used in the product, and that you handle authorization and data
deletion correctly. Keep it **3–6 minutes**, screen recording with a voiceover (English).

Record at 1280×720 or higher. Narrate calmly; don't rush the auth and deletion parts —
those are what reviewers scrutinize. Use a **test/sandbox shop**, not a real seller's data.

---

## Before you record
- Sign in to Live Ops Hub as an **admin** of a demo org.
- Have the TikTok **test shop** ready to authorize.
- Close unrelated tabs; hide any real customer names (use the demo org).

---

## Scene 1 — What the app is (0:00–0:30)
**Show:** the Live Ops Hub console home.
**Say:** "This is Live Ops Hub, a warehouse pick-pack-and-ship tool for TikTok Shop LIVE
sellers. It pulls a seller's LIVE orders into a packing workflow so a warehouse team can
pick, pack on camera, and ship them. I'll show how it connects to TikTok Shop, what each
permission is used for, and how a seller disconnects and deletes their data."

## Scene 2 — Authorization / OAuth (0:30–1:15)  ← reviewers watch this closely
**Show:** click **Connect TikTok Shop** → TikTok's authorization screen → approve → redirect back.
**Say:** "The seller connects their shop through TikTok's standard authorization flow. We
request only the scopes we use: order read, fulfillment, product read, and the webhook.
After they approve, TikTok returns us an access token, which we store encrypted."
**Point out on screen:** the granted shop now appears as **connected** in Live Ops Hub.

## Scene 3 — Order read scope in use (1:15–2:15)
**Show:** a LIVE order arriving (via the Sync button or webhook) and appearing in the orders list.
**Say:** "When an order is placed during a LIVE, TikTok sends us a webhook; we also poll for
new and updated orders. Each order shows the buyer, items, and the TikTok-provided
**ship-by deadline**, which we use to prioritize packing. This is the order-read scope."

## Scene 4 — Product read scope in use (2:15–2:50)
**Show:** the product/SKU list synced from TikTok; a scanned barcode resolving to a product name.
**Say:** "We read the shop's product catalog so that when a packer scans a barcode, we match
it to the right TikTok product and confirm the correct item is in the box. This is the
product-read scope."

## Scene 5 — Fulfillment in use (2:50–3:40)
**Show:** packing an order → generating/attaching a shipping label → marking it shipped →
the tracking number flowing back.
**Say:** "Once an order is packed, we create the shipment and record the tracking number.
This is the fulfillment scope — we update fulfillment state for orders the seller
authorized us to handle."
> Only include this scene if you actually push fulfillment/tracking back to TikTok. If the
> app currently only **reads** and ships via the carrier (no write-back to TikTok), say so
> plainly instead: "Fulfillment is recorded in Live Ops Hub and the carrier; we do not write
> back to TikTok." Do not claim a scope you don't exercise — reviewers reject mismatches.

## Scene 6 — Deauthorization + data deletion (3:40–4:40)  ← the compliance moment
**Show:** two things —
1. In Live Ops Hub (admin): the **Delete account** control on the profile page, and the
   TikTok **disconnect / "forget shop"** action.
2. Narrate what happens server-side.
**Say:** "If a seller revokes access from TikTok, we receive the deauthorization webhook and
immediately stop all access: we delete the stored tokens and shop credentials, and we purge
or anonymize that shop's order data. A seller can also trigger deletion themselves — here's
the in-app 'Delete my account' action, which deletes the account and requests data deletion.
Within 30 days all personal data is deleted or anonymized, per our published privacy policy
at liveopshub.com/privacy."

## Scene 7 — Close (4:40–5:00)
**Say:** "That's Live Ops Hub: it reads a seller's authorized TikTok Shop orders and products,
helps a warehouse team pack and ship them on time, and fully removes the seller's data on
disconnection or request. Thank you for reviewing."

---

## Checklist reviewers map against your requested scopes
- [ ] OAuth consent + redirect shown in full
- [ ] Each requested scope demonstrated doing real work (don't request unused scopes)
- [ ] Webhook **and/or** polling for orders shown
- [ ] Deauthorization → token deletion + data purge explained/shown
- [ ] Self-serve deletion path shown (now live on `/me`)
- [ ] Privacy policy URL visible: https://liveopshub.com/privacy
- [ ] No real seller/consumer PII on screen (use the test shop + demo org)

## Narration-to-code cross-reference (for your own confidence, not for the video)
- OAuth / token storage: `_tt_valid_token`, `_tt_ensure_cipher`
- Webhook (order topic 1, deauth topic 6): `/api/tiktok/webhook`
- Order polling/apply: `_tt_sweep_once`, `_tt_apply_order`
- Deauth handling: `_tt_mark_deauthorized` (clears tokens/cipher), topic-6 handler
- Data purge / retention: `_tt_purge_shop_data`, `_tt_retention_purge` (30-day), `/api/tiktok/forget`
- Self-serve account deletion: `POST /api/account/delete` + Delete control on `/me`
