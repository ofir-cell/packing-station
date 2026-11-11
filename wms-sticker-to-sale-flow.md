# The sticker → product → sale chain (end to end)

How a scanned barcode during matching connects all the way down to the actual sale, and
where bundles stand today. Written to reason precisely about the workflow before we change it.

## The one join key: the sticker number
Every sold unit in a live carries a **sticker number** — TikTok's per-sale counter the host
calls out and the picker writes on the item. In our data that sticker lives on each order
line: `shipment_items.sku` **is** the sticker (e.g. `143`), with `shipment_items.revenue` =
the sale price and the parent `shipments` row holding the buyer + address + tracking.

So the sale already knows its sticker. What it does **not** know by itself is *which product*
that sticker was. That is the only thing matching adds — and it's the link that makes the
whole chain work.

## The chain, stage by stage

**1. Sale happens (live / order import).**
A buyer buys sticker #143 for $29. It lands as `shipment_items(sku='143', revenue=29, product_name='<TikTok listing>')` under a `shipments` row (buyer, address). At this point the
system knows *a sale of sticker 143 happened* but not what product 143 is.

**2. Matching (the link).** `/admin/match-live` → `/api/live/match`.
A worker sees sticker 143 ("sold at $29", to confirm it's the right one) and scans the
product barcode. The endpoint:
- resolves the product by barcode (`products.barcode`); if unknown, `_resolve_or_create_product_by_barcode` pulls name + image from online barcode DBs and **creates the product**.
- writes the link: `show_product_map(import_label, sticker_sku=143, part, product_sku)`.
- runs `_deplete_show_packed` — back-deducts stock for boxes already packed before the match.

**3. Resolution (sticker → product) everywhere downstream.** `_resolve_item_product(...)`
reads `show_product_map`, so the instant 143 is linked, **every** order line with sticker 143
resolves to that product — retroactively, across all buyers. This is the hub the rest hangs off.

**4. Picking & packing.** `_pack_box` / the pick screen resolve each sticker to its product,
so the picker/packer see the real product name + image, and packing can **verify by barcode**
(cycle-17: an unknown barcode scanned at packing is learned onto the expected item).

**5. Inventory.** Each match/scan deducts `products.on_hand` and writes `stock_moves`;
`_resync_inventory` can rebuild stock from the current links. So stock reflects real sales.

**6. The sale level — the full trace.** Because the sticker joins the order line (buyer,
price) to the catalog product (cost `avg_cost`, barcode, image), every sold unit now traces:
> buyer → sticker 143 → product X → unit cost / price → **profit, COGS, revenue** (live
> totals via `live_sales`; trued-up by the CSV import at the end).

That is "down to the sale level": the link isn't just cosmetic — it's what lets a $29 sale of
sticker 143 become "sold Product X, cost $8, profit $21, −1 from on-hand."

## Where bundles stand today — the honest picture

**What exists: `part`.** `show_product_map` is keyed by **(label, sticker, part)** — one
product per (sticker, part). `part` is parsed from the listing name (`_part_num`: "Part 2" → 2).
Its real purpose is **live segments/lanes**: a live runs "PART 1" then "PART 2", sticker
numbers reset each part, so sticker 65 in PART 1 ≠ 65 in PART 2. Packing already shows each
(sticker, part) as its own scan line.

**What does NOT exist: a real bundle definition.** There is no bundle/kit/components table,
and no way to say "this one sold sticker is physically products A + B." One sold sticker =
one `(sticker, part)` row = **one** product. A genuine bundle (one TikTok listing that is
several physical items) only works today if the seller already listed each component as its
own "Part N" line so the order carries multiple lines. For a single-listing bundle, the
packer is **not** told "scan 2 products" — the system thinks it's one.

This is the gap to close for the workflow you described (define a bundle during linking → the
packer is told "bundle of N, scan all").

## Options to truly solve bundles (for discussion)

1. **Bundle at match time (recommended).** On the match screen, after linking sticker 143 to
   product A, allow "➕ add another product to this sticker" → scan product B. Store both as
   `(143, part 0=A, part 1=B)` — reuse the existing `part` slots, but driven by the *worker's*
   action, not the listing name. Packing already renders multiple parts as separate scan
   lines, so it would automatically say "2 to scan." Smallest change; uses what's there.

2. **A bundle/kit catalog.** Mark a product as a bundle of component SKUs; expand it into
   components at pick/pack and for inventory (deduct each component). More correct for
   inventory/costing, but a bigger build (new table + expansion everywhere + analytics).

3. **Hybrid.** Bundle-at-match for the floor workflow now (option 1), add the kit catalog
   later only if inventory/costing per component becomes important.

## Quick reference — the moving parts
| Thing | Where |
|---|---|
| Sticker on the sale | `shipment_items.sku` (+ `.revenue`, parent `shipments` buyer/addr) |
| The link | `show_product_map(import_label, sticker_sku, part, product_sku)` |
| Make the link | `/api/live/match`, `/api/live/scan` (+ auto-create from barcode) |
| Resolve sticker→product | `_resolve_item_product` / `_ship_bindings` |
| Pick/pack view + verify | `_pack_box`, `/api/pack/scan` (+ cycle-17 learn) |
| Inventory | `products.on_hand`, `stock_moves`, `_deplete_show_packed`, `_resync_inventory` |
| Live profit | `live_sales`, `_live_totals` |
| Part (segment) key | `_part_num` / `_sticker_part` ("Part N" in the listing name) |
| Bundle definition | **does not exist yet** |
