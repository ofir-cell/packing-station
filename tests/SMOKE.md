# Staging smoke test (QA runs after every deploy to staging)

1. Log in as admin → /home loads, no console errors.
2. Worker badge login → pick screen → Back and 🏠 buttons work.
3. Scan a test tracking on a packing station → order found, video records, order shows `packed`.
4. Admin → TikTok: status shows connected; "Sync" returns ok; no new "webhook rejected" lines in logs from real TikTok traffic.
5. Mark one order picked → wait 6 minutes (one wide sweep) → still `picked`.
6. Admin → TikTok → "Fix show grouping" → packed/picked counts per show unchanged before vs after.
7. Inventory page loads; on_hand of a test SKU unchanged by steps 5–6.
