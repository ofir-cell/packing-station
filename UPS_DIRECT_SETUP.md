# UPS Direct API — Setup Guide

You're connecting **your own UPS account** directly, cutting out ShipStation and every other middleman. No monthly fee — you pay UPS for the labels you buy, at your account's negotiated rates.

You need **three values** from UPS, then paste them into Railway. That's it.

---

## What you'll end up with

| Env var | What it is | Example |
| --- | --- | --- |
| `UPS_CLIENT_ID` | Your app's Client ID | `aBcD1234...` |
| `UPS_CLIENT_SECRET` | Your app's Client Secret | `XyZ9876...` |
| `UPS_ACCOUNT_NUMBER` | Your 6-character UPS account (shipper) number | `A1B2C3` |

---

## Step 1 — Log in to the UPS Developer Portal

1. Go to **https://developer.ups.com**
2. Click **Log In** (top right) and sign in with your normal **UPS.com** account — the same one that has your account number and negotiated rates. (If you don't have a UPS.com login yet, create one at ups.com first and make sure your shipping account number is added to it.)

> Using your real UPS.com account is what gets you **your** rates on the labels, not list price.

## Step 2 — Find your UPS Account Number

1. On ups.com, go to your **Profile → Accounts and Payment** (or **Account Summary**).
2. Copy the **6-character account number** (looks like `A1B2C3`).
3. That's your `UPS_ACCOUNT_NUMBER`.

## Step 3 — Create an App on the Developer Portal

1. Back on **developer.ups.com**, open the **Apps** area (top menu → your name → **Apps**, or go to the "My Apps" / "Add Apps" page).
2. Click **Add App** / **Create App**.
3. When it asks **how you want to integrate**, choose:

   ### ✅ Client Credentials  (this is the one you want)
   - This is for using **your own** UPS account, server-to-server.
   - **Do NOT** pick *Authorization Code* — that flow (with a "redirect URI" and a consent screen) is only for connecting *other people's* UPS accounts, like a marketplace. It's more complex and you don't need it.

4. It will ask which **account number** to associate — pick the one from Step 2.
5. Give the app a name (e.g. `LiveOpsHub Labels`) and select the products/APIs. Make sure these are checked:
   - **Rating** (get rates)
   - **Shipping** (create labels)
   - *(optional)* **Tracking**
6. Submit.

## Step 4 — Copy your Client ID + Secret

After the app is created, the portal shows:
- **Client ID** → this is `UPS_CLIENT_ID`
- **Client Secret** → this is `UPS_CLIENT_SECRET` (you may need to click "show" / "generate")

Copy both somewhere safe. **The secret is a password — never share it or commit it to code.**

---

## Step 5 — Paste into Railway

1. Open your project on **Railway → Variables**.
2. Add these three variables:

   ```
   UPS_CLIENT_ID       = <your Client ID>
   UPS_CLIENT_SECRET   = <your Client Secret>
   UPS_ACCOUNT_NUMBER  = <your 6-char account number>
   ```

3. *(Optional)* To test against UPS's sandbox first instead of buying real labels, also add:

   ```
   UPS_ENV = test
   ```

   Leave `UPS_ENV` unset (or set it to `production`) when you're ready to buy real labels.

4. Save. Railway redeploys automatically.

---

## Step 6 — Confirm it works

1. Open the app and go to **Warehouse → Inbound Shipments**.
2. In the **"🚚 Carriers connected"** strip at the top you should now see **UPS ✓**.
   - Or open `https://getwhatnot.com/api/ship/carriers` directly — you should see `"provider":"ups"` and `"ok":true`.
   - If you see an error there, it means the Client ID/Secret/account number don't match — double-check them.
3. Fill in a supplier address + a box, hit **Get rates** — UPS services (Ground, 2nd Day Air, Next Day Air…) appear, sorted with UPS first. Pick one to buy the label.

---

## How it behaves

- **UPS takes priority.** The moment those three variables are set, every label (inbound supplier labels **and** giveaway labels) is bought directly from UPS.
- **Nothing breaks during the switch.** If UPS isn't configured yet, the app keeps using ShipStation. Once UPS is set, it takes over automatically. You can remove the ShipStation key whenever you like.
- **Rates are yours.** Because it's your account number on the request, you get your negotiated UPS pricing.
- **Labels** come back as 4×6 GIF images, printed from the same print screen as before.

---

## Notes & limits

- **USPS:** going UPS-direct means the app no longer offers USPS. UPS Ground is usually fine for supplier inbound and most giveaways; if you ever want the cheap USPS option back for tiny packages, keep a ShipStation key set and tell me — I can make it show both.
- **Token limit:** UPS allows ~250 auth-token requests per day. The app caches the token for its full lifetime, so this is never a problem in practice.
- **International:** this setup is built for US domestic. International (customs docs) can be added later if needed.
