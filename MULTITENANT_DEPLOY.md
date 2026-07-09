# Multi-tenant data isolation — deploy notes

## What changed (in code, done + tested)

Each tenant now has a **physically separate set of data files** under
`/data/orgs/<org>/` (shipments.db, giveaways.db, videos/, photos/, packing_log.csv,
documents, onboarding, announcements). A query literally cannot reach another
tenant's file — isolation is by filesystem path, resolved from the logged-in
user's session org through one choke point (`sdb()` / `gdb()` / `video_dir()` …).

- **Control plane** stays shared at the `/data` root: `users.json` (maps user→org,
  read at login before the org is known), `stations.json`, and a new
  **`platform.db`** holding the `organizations` table.
- **`provision_org()`** creates a tenant's folders + DBs. Runs at boot for every
  org; it's also what a future SaaS signup calls to create a new tenant.
- **One-time auto-migration**: on first boot after this deploy, existing flat
  `/data` files are moved into `/data/orgs/5sec/` automatically. The databases +
  JSON stores are **COPIED** (the originals stay at the `/data` root as an
  automatic backup); only the local media folders are moved. Idempotent, marker-
  guarded, and safe with multiple gunicorn workers. Your customized branding is
  copied from the old DB into `platform.db`.
- **Schedulers** (cleanup + USPS tracking) now loop over all tenants.
- **Public new-hire onboarding links** resolve their tenant from the invite token
  and stay scoped to it; an authenticated user only ever sees their own org.

Verified locally: fresh boot, legacy migration (real data survived), two-tenant
isolation (no cross-tenant leakage), public-token org resolution, and authenticated
routes returning 200.

## Your steps to deploy

1. **(Optional) Snapshot the `/data` volume** in Railway if your plan offers it.
   Not strictly required: the migration COPIES your DBs and leaves the originals
   at the `/data` root as an automatic backup. (I cannot reach your volume.)
2. **Deploy**: on your Mac, clear the git locks
   (`find .git -name "*.lock" -delete`), then
   `git add -A && git commit -m "Multi-tenant data isolation" && git push`.
   Railway auto-deploys on push.
3. **Watch the first boot logs** for
   `[migrate] done — legacy DBs copied into …/orgs/5sec`. That confirms the
   one-time migration ran.
4. **Verify** the app works normally — your existing shipments, videos, shows and
   giveaways are all there (they just live under `orgs/5sec/` now).
5. **Later, once verified**, you can delete the leftover backup files at the
   `/data` root (`shipments.db`, `giveaways.db`, the old JSON files). Optional.

## Not included in this change (next step)

- **R2 object keys are not yet namespaced per org.** Media is still access-gated
  (each tenant's DB references only its own media filenames, URLs are short-lived
  presigned, filenames are random timestamps), so there's no cross-tenant media
  leak today. Full R2 key prefixing needs an object migration and should be its
  own focused step before onboarding an external customer.
- Hire-uploads folder and the SaaS signup/onboarding flow to create new orgs.
