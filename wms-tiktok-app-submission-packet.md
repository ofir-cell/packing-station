# TikTok Shop App Store — submission packet (Live Ops Hub)

Everything needed to take the app from **Custom/Development** to a **public** listing, with
ready-to-paste text for each field. You submit inside **TikTok Shop Partner Center**
(partner.tiktokshop.com) on your app's page. Reviews for US partners can take **3+ weeks**,
so submit once the fields below are in.

> Verify every label against your actual Partner Center screen — TikTok moves things around.
> Where this packet and the portal disagree, follow the portal and tell me what changed.

---

## 0. Where the submission lives
On your app page in Partner Center there's a **Launch checklist** (sometimes "Go live" /
"App review"). It tracks each gate:
1. App information (listing) complete
2. Scopes + webhook configured
3. Tested in a Development Shop (Sandbox)
4. **Submit for App Review**
5. **Data Security & Privacy Review (DSPR)** — triggered when the review team asks
6. **US Data Security Questionnaire** — triggered for US-market apps when asked

Work top to bottom. 5 and 6 usually open *after* you submit for App Review.

---

## 1. App information (listing) — ready to paste

**App name:** Live Ops Hub

**Short description (1 line):**
> Warehouse pick, pack, and ship for TikTok Shop LIVE sellers — orders flow straight into a packing workflow.

**Full description:**
> Live Ops Hub is a warehouse operations tool for TikTok Shop LIVE sellers. It pulls your
> authorized LIVE orders into a pick-pack-and-ship workflow so your fulfillment team can pick
> the right items, pack them on camera, and ship on time against each order's ship-by
> deadline. It syncs your product catalog so a barcode scan confirms the correct item, tracks
> packer and picker performance, and records every pack on video for dispute protection.
> Sellers connect their shop with one click and can disconnect and delete their data at any
> time.

**Category:** Order management / Fulfillment (pick whichever TikTok lists closest).

**Primary market:** United States.

**App icon:** 1024×1024 PNG, no transparency — use the LoH mark
(`live-ops-hub-logo-1080.png` is in your outputs).

**Support / contact email:** ofir@5secbeauty.com

**Website:** https://liveopshub.com
**Privacy Policy URL:** https://liveopshub.com/privacy
**Terms of Service URL:** https://liveopshub.com/terms

**Redirect/Callback URL (OAuth):** your production callback —
`https://www.getwhatnot.com/api/tiktok/callback` (confirm against what's registered in code;
it must match exactly).

**Webhook URL:** `https://www.getwhatnot.com/api/tiktok/webhook`

---

## 2. Scopes — request ONLY what the app exercises
This is the part reviewers check hardest: every scope must be demonstrated in the demo video.
**Decision made: the system writes tracking numbers back to TikTok** (seller self-ship, built
in cycle-15), so the fulfillment **write** scope is required:

| Scope | Request it? | Why / where used |
|---|---|---|
| Order read / order details | **Yes** | Pull LIVE orders + ship-by deadline (`_tt_apply_order`, sweep, webhook topic 1) |
| Product read | **Yes** | Catalog/SKU sync for barcode match (cycle-8 product sync) |
| **Fulfillment (write)** | **Yes** | Push our tracking number back to mark the order shipped (`_tt_mark_shipped`, cycle-15) + Get Shipping Providers |
| Webhook / event subscription | **Yes** | Order events + deauthorization (topic 6) |

> Demo video: show Scene 5 (the ship-back) — pack an order, then show it marked **Shipped**
> on TikTok with the tracking number. The write path is live in code but OFF until
> `TT_FULFILLMENT_WRITE=1` (see `wms-cycle15-fulfillment-shipback.md`); enable it in a Sandbox
> shop to record the demo.

---

## 3. Demo video
Record per `wms-tiktok-app-review-video-script.md` (3–6 min, shows OAuth + each scope +
deauthorization/deletion). Upload where the Launch checklist asks for "demo video" /
"review video". Use a **Development Shop (Sandbox)** — no real seller/consumer PII on screen.

---

## 4. Test account for reviewers
Give reviewers a way in without your real data:
- **Console URL:** https://www.getwhatnot.com
- A **demo-org** admin login (create a throwaway admin in a demo org; don't hand over a real tenant).
- Note: "Sign in, open the orders list, scan to pack, and see Account → Delete my account on /me."

---

## 5. Data Security & Privacy Review (DSPR) + US Data Security Questionnaire
These open when the review team asks. Ready answers are in
`wms-tiktok-data-security-questionnaire.md` (companion doc). You'll also likely need to
re-upload the business documents you already have: **Articles of Organization**, **2025
Annual Report**, and the **D-U-N-S** (10-114-2825).

---

## 6. Pre-submit checklist
- [ ] App name, descriptions, category, icon, support email, website set
- [ ] Privacy + Terms URLs live (they are: /privacy, /terms) and reachable
- [ ] Redirect + webhook URLs match production exactly
- [ ] Scopes trimmed to what's exercised (decide fulfillment read vs write)
- [ ] Demo video recorded in Sandbox, no real PII
- [ ] Reviewer test login (demo org) created
- [ ] Business docs ready to upload (Articles, Annual Report, D-U-N-S)
- [ ] Deauthorization deletion + self-serve deletion deployed to prod
      (`git push origin cycle14/me-account-delete-ui:main` — bundle delivered)

> ⚠️ Deploy the privacy/deletion branch **before** you submit — reviewers will test
> disconnect + deletion, and those code paths must be live in production.

---

## 7. What I still need from you to finish the packet
1. **Fulfillment scope:** read-only, or do you push tracking back to TikTok? (sets the scope list)
2. Confirm the **OAuth callback URL** registered in the app matches section 1.
3. Want me to open Partner Center with you in the browser and fill this in field by field?
