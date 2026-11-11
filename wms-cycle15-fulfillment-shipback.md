# Cycle-15 — TikTok fulfillment write-back (push our tracking numbers to TikTok)

**What it does:** after your warehouse bundles/packs a TikTok order and it has a tracking
number (status `packed` or `shipped`), the system pushes that tracking number back to TikTok
so the order is marked **shipped** on TikTok — the seller self-ship flow you asked for.

**How it works:** resolves your carrier (USPS by default) to TikTok's `shipping_provider_id`
via Get Shipping Providers, then marks the package shipped with the tracking number + the
order's line-item ids. State is tracked in a new `tiktok_fulfillment` table so an order is
**never shipped twice**, and every attempt is audit-logged.

**It runs** automatically after each order sweep, and on demand via admin `POST /api/tiktok/fulfill`
(optionally `{"order_id": "..."}` for one order).

## It is OFF until you turn it on — on purpose
It stays completely inert until **both**:
1. The **fulfillment scope is granted** in App Review, and
2. You set the env flag **`TT_FULFILLMENT_WRITE=1`**.

Staging Safe Mode also blocks the actual calls, so nothing fires there regardless. This means
you can deploy it now safely — it changes nothing in production until you flip the flag.

## Activation steps (after App Review grants the fulfillment scope)
1. **Confirm the endpoint path** in Partner Center → API Reference → Fulfillment
   ("Mark Package As Shipped" / self-ship). If the native path differs from the default
   `/fulfillment/202309/orders/{order_id}/packages`, set `TT_SHIP_PACKAGE_PATH` to the exact
   path — no code change needed. (Same for `TT_SHIP_PROVIDERS_PATH` if the providers path differs.)
2. Set the Railway env vars on the production service:
   - `TT_FULFILLMENT_WRITE=1`
   - `TT_SHIP_PROVIDER_NAME=USPS` (or your carrier, matched against TikTok's provider list)
   - `TT_SHIP_PACKAGE_PATH` / `TT_SHIP_PROVIDERS_PATH` only if Partner Center shows different paths
3. Ship one real order and confirm on TikTok it shows **Shipped** with the tracking number.
   Check the audit log for `tiktok.ship.ok`. If you see `tiktok.ship.fail`, the message tells
   you what TikTok rejected (usually a provider mismatch or tracking-format issue).

## Deploy
FF-safe over origin/main; bundle delivered. Push:
```bash
cd ~/Desktop/packing-app
git fetch origin
git push origin cycle15/tiktok-fulfillment-shipback:main
```
Safe/additive; inert until `TT_FULFILLMENT_WRITE=1`.

## Scope impact on your TikTok submission
Because the system now writes fulfillment back to TikTok, **request the fulfillment (write)
scope** in the app submission, and show the ship-back step in the demo video (Scene 5). I'll
update the submission packet to reflect "fulfillment write" instead of read-only.

## Env knobs (summary)
| Var | Default | Purpose |
|---|---|---|
| `TT_FULFILLMENT_WRITE` | `0` (off) | Master switch for the whole feature |
| `TT_SHIP_PROVIDER_NAME` | `USPS` | Carrier name matched to TikTok's provider list |
| `TT_SHIP_PACKAGE_PATH` | `/fulfillment/202309/orders/{order_id}/packages` | Ship endpoint (confirm in Partner Center) |
| `TT_SHIP_PROVIDERS_PATH` | `/logistics/202309/shipping_providers` | Provider-list endpoint |
