# Security review — SEC-6 fix: company deletion cleanup

- Date: 2026-11-11
- Change: branch `fix/sec-6-org-delete-cleanup`, commit `1f59036` on `main` (`app.py`, `tests/test_sec6_org_delete_cleanup.py`, `tests/test_security_mobile_baseline.py`)
- Reviewer: security-reviewer
- Method: Flask test client against a throwaway `DATA_DIR`, in-memory fake storage, TikTok transports replaced by recorders. No production system, no real bucket, no network. Items marked *(reading)* were not exercised.

## Verdict: BLOCK (two small fixes), then FIX SOON for the rest

The cleanup itself does what it says and I could not make it touch another company's rows, keys or files. It is blocked for two reasons that both come from the same fact: **this PR turns an existing cookie-only action into an irreversible one** (stored objects and main-bucket backups are now deleted, and the id is tombstoned forever).

SEC-6 is **partly closed**. Open parts are listed as SEC-6a … SEC-6h.

| Id | Level | One line |
|---|---|---|
| SEC-6a | **BLOCK** | A leftover session of a deleted company deletes a *different* company once its username is taken again |
| SEC-6b | **BLOCK** | The founding (real warehouse) company can be wiped the same way; the tombstoned id comes back at next boot |
| SEC-6c | FIX SOON | TikTok callback / in-flight ingest re-create token and order rows for a tombstoned org; nothing ever purges them |
| SEC-6d | FIX SOON | Webhooks for the deleted company's shop are still stored (payload, no org, no retention) |
| SEC-6e | FIX SOON | Ids equal to shared storage folders (`videos`, `backups`, `support`, …) can still be created; their objects can never be auto-deleted |
| SEC-6f | FIX SOON | TikTok authorisation is not ended; live tokens, password hashes and 2FA secrets stay in backups for up to ~6 weeks |
| SEC-6g | FIX SOON | Privacy policy and App Store answers do not say what remains after deletion |
| SEC-6h | FIX SOON | `partial` deletions alert nobody; raw exception text is stored in the tombstone |

## Ruling on the edited demonstration test

**Edit accepted.** My original fake returned an empty listing for every call and still required a `delete*` call. S3-style storage has no "delete by prefix"; an honest implementation lists first and deletes what it finds, so it could not pass. That was my error.

The edited test is still a true test of the finding — checked by mutation, not by reading:

| Mutation of the fix | Edited test |
|---|---|
| storage targets removed (no storage work) | fails |
| platform rows not purged | fails |
| lists the whole bucket and deletes a key of **another** org | **passes** |

So it proves "storage is asked to delete something", not "the right thing". The exact-prefix guarantee is carried by `tests/test_sec6_org_delete_cleanup.py` (`test_storage_delete_hits_exactly_the_orgs_prefixes`, `test_similarly_named_orgs_are_untouched`), which is sound. Requested tightening (owner: programmer): have the fake record deleted keys and assert they equal `{org + "/videos/S1_TRK.webm"}`.

## What holds (verified by request / call)

1. **Nothing of the deleted org remains** after `POST /api/account/delete {"wipe_org": true}` by the last admin: every `platform.db` table with `org_id` is empty for the org (TikTok shop tokens, orders, events incl. unmapped ones of its shop, live sessions, control, products, billing requests), tickets + messages + attachment object + local `support/<id>/`, all logins, the org folder, local `backups/<dow>/<org>/`, local flat hire uploads, storage `<org>/` in main and HR buckets and `backups/<dow>/<org>/`. A neighbouring org seeded identically was untouched (rows, 11 objects, local hire file).
2. **Old sessions are dead immediately, on another process too.** A real pre-deletion cookie replayed in a second Python process sharing the volume: 402 on gated routes, 401 `session_revoked` on billing-open routes. The check reads `users.json` and `platform.db` on every request, so there is no per-worker state. A platform-owner impersonation session opened before deletion: 402 everywhere tried, cannot mint a TikTok connect link, does not re-create the folder. Login as a deleted user: refused. (Exception: SEC-6a.)
3. **Id reuse refused**: same id, upper case, leading/trailing spaces, tab, newline → "belonged to a deleted company". Cyrillic look-alike, full-width letter, zero-width space, trailing `/` or `.` → rejected by the id pattern. Tombstone lookup is an exact byte comparison on the id *after* `strip().lower()` and the ASCII-only pattern `^[a-z0-9][a-z0-9\-]{1,30}$`, so there is no normalisation gap. Intake with the same company name gets `<id>2`; a super-admin override in upper case also lands on a fresh id. A `pending` id cannot be created either.
4. **Who can trigger it**: worker, picker, host, cs, manager sending `wipe_org: true` delete only their own login; the company stays. Without the CSRF header: 403. The org is taken from the user record, never from the request body (body `org` / `org_id` ignored). No route lets a tenant tombstone or mark "pending" an id it does not own. Confirmation is still only the `wipe_org` flag, no password, no 2FA (SEC-7, open, unchanged).
5. **Crafted ids**: `""`, `__platform__`, `a/b`, `../x`, `ab/`, `a b` are refused by `_delete_org_data`; `../x`, `/`, blank company names cannot become an org at intake. Deleting orgs named `videos`, `backups`, `support`, `photos` (created through intake) made **no** list or delete call on the shared prefixes and removed no shared object. Prefix `ab/` never matches `abc/` or `ab-2/` (programmer's tests, re-run: 9 passed). 2,500 objects under one prefix: all deleted, neighbour key kept.
6. **Failure path**: storage raising on every call → response `state: pending`, id still blocked, hourly resume finishes it and leaves the look-alike prefix alone.
7. **Logging**: nothing printed by the purge except `alog error: unable to open database file` (the route writes the tenant audit line after the tenant DB is gone — harmless, but the `account.delete` line is lost). No token string in stdout, `platform_audit`, the tombstone `detail`, or the HTTP response.

## Findings

### SEC-6a — BLOCK — A leftover session of a deleted company can delete another company
- Reproduce (done by request): org C exists with admin `gonec-admin`. Keep a copy of any C session cookie. Last admin wipes C. Create a new org D whose admin username is `gonec-admin` (usernames are free again after deletion; intake proposes `<company slug>admin`, so the same company name signing up again gets the same username). Replay the old cookie: `POST /api/account/delete {"wipe_org": true}` → 200, `org_deleted: true`; D's organizations row is gone, D is tombstoned, D's storage prefixes were purged.
- Why: `_session_revocation` only asks "does this username exist" and re-syncs the role from the new record; `api_account_delete` takes the org from `users[u]`, not from the session. Cookies live 7 days and survive logout (SEC-10). `/api/account/delete` is open through the billing gate, which is what stops the stale session elsewhere.
- Not introduced by this PR, but before it the damage stopped at the local folder; now it is permanent. The PR's own docstring relies on "sessions are revoked on their next request".
- Fix (few lines): in `_session_revocation`, revoke when the record's org differs from `session["org"]`; in `api_account_delete`, refuse when they differ. The same gap lets a deleted worker's cookie pick up a new namesake's role inside the *old* org — belongs with SEC-10. Owner: **programmer**.

### SEC-6b — BLOCK — The founding company can be wiped; its tombstoned id returns at boot
- Reproduce (done by request): as the only admin of the default org (the seed has exactly one), `POST /api/account/delete {"wipe_org": true}` → 200, state `partial`; `5sec/…` media, HR documents and `backups/<dow>/5sec/` deleted from storage, folder gone. Then `pdb_init()` (every boot) inserts the organizations row again while the tombstone stays: a live org whose id is "deleted", which the resume loop skips by name.
- Session cookie only (SEC-7). This is the real warehouse's packing-video evidence.
- Fix: refuse `wipe_org` for `DEFAULT_ORG` in the route (the resume loop already treats it as untouchable). Strongly preferred: merge the SEC-7 re-authentication before or together with this PR. Owner: **programmer**.

### SEC-6c — FIX SOON — Rows are re-created for a tombstoned org and never purged
- Reproduce (done by request): mint a connect state for org A (valid 1 h, usable by a signed-out browser — SEC-12), delete A, open `/api/tiktok/callback?code=…&state=…` → 200 and a `tiktok_shops` row with live tokens for the tombstoned id. A following signed webhook is queued for that org; `_tt_ingest_order` then writes a `tiktok_orders` row for it; the sweep keeps calling TikTok with the token every cycle (fails only when it opens the missing shipments DB — the folder is **not** re-created). `_org_delete_resume_pending` returns 0: it looks only at `pending` tombstones.
- Same result *(reading)* for an ingest thread that read its token just before the purge.
- Fix: `_tt_store_shop`, the callback and the ingest/sweep paths refuse an org without an organizations row; the hourly loop purges platform rows for every tombstoned id, whatever its state. Owner: **programmer**.

### SEC-6d — FIX SOON — Late webhooks are stored without owner or retention
- Reproduce (done by request): after deletion, a signed order webhook for the old shop → 200, a `tiktok_events` row with the payload and `org_id=''`. No job deletes such rows. Because the authorisation is not ended (SEC-6f), TikTok keeps sending them.
- Side effect measured: each unknown-shop webhook makes the self-heal call TikTok (token refresh + shop list) with every other connected company's token.
- Fix: do not store payloads for shops no org owns (or purge `org_id=''` events on the retention schedule); skip self-heal for shop ids that belonged to a tombstoned org. Owner: **programmer**.

### SEC-6e — FIX SOON — Reserved folder names can still become org ids
- Reproduce (done by request): intake with company name `Videos`, `Backups`, `Support`, `Photos` → orgs `videos`, `backups`, `support`, `photos`. Deleting them ends `partial` with the storage prefix skipped (correct and safe), so their media can never be removed automatically, and they share a top-level prefix with the founding company's legacy media / everybody's backups / everybody's ticket files.
- Fix: reject `_R2_RESERVED_TOP` (plus `orgs`, the weekday names, `platform`) in `_create_tenant` and in the intake slug loop. Owner: **programmer**.

### SEC-6f — FIX SOON — TikTok access is not ended; secrets outlive the company in backups
- *(reading)* Tokens are deleted locally only. Copies remain in `backups/<dow>/platform.db` and `users.json` in the main bucket (7-day rotation), the same files under `DATA_DIR/backups/`, the dedicated backup bucket (`keep_6h=8, keep_daily=7, keep_weekly=6` → about six weeks), and any legacy root copies from the migration. Those copies contain working refresh tokens, password hashes and 2FA secrets of the deleted company.
- Ruling: SEC-6 is not closed while a restored backup can still act on the seller's shop. Either end the authorisation at TikTok at deletion time (I did not verify that TikTok offers a partner-side call — owner to check the Partner API), or tell the deleting admin on the confirmation screen to remove the app in Seller Center and state the backup window in the policy. A restore procedure must re-apply tombstones (delete tombstoned orgs again after any restore).
- Owner: **programmer**; restore note: **Ofir**.

### SEC-6g — FIX SOON — Privacy answers
`site/privacy.html` says deletion within 30 days after deauthorisation, "Backups age out on a fixed schedule", and "encrypted credentials". It must state, for company deletion:
- deleted at once: logins, orders and buyer details, packing videos and photos, labels, documents, new-hire documents, support tickets and attachments, TikTok connection data; storage cleanup is retried hourly until done;
- backups: the real maximum (7 days operational, about 6 weeks for the dedicated backup set), and that backups are not edited;
- kept: payment and billing records, the platform security log (company id, admin username, time), the sales/sign-up contact (name, email, phone) — with a stated period or an anonymisation rule;
- the company id is reserved permanently;
- the seller must disconnect the app in TikTok Seller Center unless we end it for them;
- single-user deletion: the name stays on order history, the packing log and inside videos (from the baseline).
`ios/APP_STORE.md` reviewer notes and the App Privacy answers must match. Owner: **Ofir** (text), **programmer** (page).

### SEC-6h — FIX SOON — Housekeeping
- A `partial` tombstone ("needs a human") is only a database row: no notice to the platform owner, no screen. Add it to the Organizations console.
- Storage exception text is saved verbatim (first 200 characters) in `org_tombstones.detail`; measured with a fake error carrying a credential-looking string: stored in the row, not printed, not returned to the client. Store the exception type only.
- Owner: **programmer**.

## The four deliberate leftovers

| Left by the programmer | Ruling |
|---|---|
| `payments`, `platform_audit` kept | Acceptable (financial and security records). Must be in the policy. |
| `leads`, `client_intakes` kept | Personal contact data with no end date. Acceptable only with a stated period; otherwise anonymise on deletion. |
| TikTok tokens not revoked | Not acceptable as final state — SEC-6f. |
| Dedicated backup bucket and `platform.db` backup copies | Acceptable if the window is published and restores re-apply tombstones — SEC-6f, SEC-6g. |
| Founding org's un-prefixed legacy keys | Correct to leave. But the founding org must not be deletable through this route at all — SEC-6b. |

## Tests requested (text only; owner: programmer / qa)

```python
def test_sec6a_stale_session_cannot_delete_a_namesake_company(appmod):
    A = appmod; org = _mk_org(A, "stale")            # baseline helpers
    with A.update_json(A.USERS_FILE) as u:
        for k in [k for k, v in u.items() if v.get("org") == org and k != org + "-admin"]: del u[k]
    c = _as(A, org + "-admin"); c.post("/api/account/delete", headers=c.csrf, json={"wipe_org": True})
    ok, res = getattr(A._create_tenant, "__wrapped__", A._create_tenant)("fresh" + org[-6:], "Fresh Co", org + "-admin")
    assert ok
    stale = A.app.test_client()
    with stale.session_transaction() as s:
        s.update(user=org + "-admin", role="admin", roles=["admin"], name="x", org=org)
    stale.set_cookie("csrf_token", "tok")
    r = stale.post("/api/account/delete", headers={"X-CSRF-Token": "tok"}, json={"wipe_org": True})
    p = A.pdb(); alive = p.execute("SELECT 1 FROM organizations WHERE org_id=?", (res["org_id"],)).fetchone(); p.close()
    assert r.status_code in (401, 403) and alive

def test_sec6b_founding_org_cannot_be_wiped(appmod, admin):
    r = admin.post("/api/account/delete", headers=admin.csrf, json={"wipe_org": True})
    assert r.status_code in (400, 403, 409)
    assert not appmod.org_id_tombstoned(appmod.DEFAULT_ORG)

def test_sec6c_callback_cannot_attach_a_shop_to_a_deleted_org(appmod, monkeypatch):
    # state minted before deletion; after the wipe the callback must answer 4xx and
    # SELECT COUNT(*) FROM tiktok_shops WHERE org_id=<deleted> must stay 0;
    # _org_delete_resume_pending() must remove rows planted for a tombstone in state 'deleted'.

def test_sec6d_webhook_for_a_deleted_orgs_shop_stores_no_payload(appmod):
    # signed type-1 webhook for the old shop id after deletion ->
    # no tiktok_events row for that shop_id, and no outbound TikTok call.

def test_sec6e_reserved_ids_cannot_be_created(appmod):
    # for each of videos, photos, documents, labels, products, invoices, backups, support:
    # _create_tenant refuses; intake with that company name yields a different id.
```
Plus the tightening of the demonstration test described above.

## Not exercised

- A real bucket: `delete_objects` error shapes, listing consistency, lifecycle rules, real client exception text.
- Four real gunicorn workers deleting the same company at once (the file lock was read, not raced); the 60 s storage budget inside a live request (worker timeout is 300 s — reading).
- Contents and pruning of the dedicated backup bucket; a restore.
- Whether TikTok offers partner-side revocation; behaviour of TikTok after local deletion.
- Storage links issued before deletion (short-lived presigned URLs — reading).
- The demo / App Review company: it does not exist yet. Note for SEC-7: a wiped demo org is now tombstoned, so it cannot be re-seeded under the same id; the simulated-deletion rule for the sandbox must land before that account is given to Apple.
- The native app and web views (not touched by this change).

---

## Re-review — 2026-11-11, commit `e973284`

Same method as above (Flask test client, throwaway `DATA_DIR`, fake storage, TikTok transports replaced by recorders; a second Python process for the cross-worker check). Nothing was run against production or a real bucket.

### Verdict: FIX SOON (merge allowed)

Both blocking findings are closed and I found no new way to reach another company. Not CLEAR: SEC-6d, SEC-6f and SEC-7 are open by decision, one new finding (SEC-6i) was opened by this commit, and the items under "Not exercised" still stand.

| Id | Status | Evidence (by request unless marked) |
|---|---|---|
| SEC-6a | **closed** | Original reproduction → 401 `session_revoked`, org D alive. Variants below. |
| SEC-6b | **closed** | Founding and `internal=1` org: last admin → 403 `org_protected`, login kept, no tombstone, storage and folder untouched. |
| SEC-6c | **closed** | Callback with a state minted before deletion → 400, no token exchange, no row. Rows planted after a finished deletion are removed by the loop. |
| SEC-6d | deferred by decision | Unchanged: late webhooks stored with no owner and no retention. |
| SEC-6e | **closed** | All shared names, weekdays, `orgs`, `platform` refused, in any case and with spaces/newline; intake moves to `<name>2`. |
| SEC-6f | deferred by decision | Unchanged: TikTok access not ended; secrets in backup copies. |
| SEC-6g | open (Ofir) | Policy text — see the backup sentence below. |
| SEC-6h | **closed** | Reason codes only; `stuck` after the attempt limit; visible to the platform owner. |
| SEC-6i | **new — FIX SOON** | Kept backup copies of a deleted company never expire by any code path. |

### 1. SEC-6a and variants

- Cookie of deleted org C, username re-used as admin of new org D, `POST /api/account/delete {"wipe_org":true}`: 401, D alive. Same result with the cookie's org missing, empty, `None`, C in upper case, D in upper case. (A cookie carrying D's exact id cannot be made without the signing key.)
- Cookie of a deleted user in a **live** org: 401. Same username re-created as an admin in another org, old cookie replayed: 401 — the role is no longer picked up across companies.
- Impersonation session of a deleted org: 402 / 401.
- Real pre-deletion cookie in a second process: 402 on gated routes, 401 on billing-open ones.
- "402 before the check": with a dead-org cookie I tried `/me`, `/api/me`, `/api/me/stats`, `/billing`, `/api/billing/status`, `/privacy`, `/demo`, `/home`, `/api/users`, `/api/tickets`, `/api/2fa/status`, `/api/tiktok/status`, `/api/stations` and POSTs to `/api/2fa/setup`, `/api/2fa/enable`, `/api/billing/request`, `/api/me/password`, `/api/users/add`. Every answer was 401, 402 or a redirect to `/` or `/billing`; no response contained D's id or name; no billing request row was written; D's admin record and C's folder were unchanged. The only paths that skip the session check are `/login`, `/logout`, `/healthz`, the favicon and static files. I did not walk every route in the app; the argument for the rest is by reading: any path the billing gate lets through reaches the session check next.
- Founding org after the boot-time tombstone clear: a founding session works again (200), which is correct — the org is alive. A still-valid cookie of a founding user is ordinary SEC-10 territory, not SEC-6.
- Legitimate users of live orgs were unaffected (200).

Remaining and out of scope here: a username deleted and re-created **inside the same org** keeps the old cookie alive with the new role (SEC-10).

### 2. SEC-6b

- Founding org: worker, picker, host, cs, manager with `wipe_org:true` → own login only; last admin → 403, nothing removed. Internal org: 403, nothing removed.
- Platform owner impersonating the founding org → 401 `session_revoked`, org alive, owner login kept.
- No platform-console route deletes a company: POST routes touching orgs are branding, payment, subscription, create, toggle, TikTok forget. `_delete_org_data` has two callers only (the route, the loop).
- Loop fed tombstone rows written straight into the database for the founding org, an internal org, a live org, `__platform__`, `../x`, `"ab\n"` and `""`: ran 0 deletions, all orgs, folders and objects intact.
- Aside (SEC-7 scope, unchanged): the platform owner's own login is deleted by the same cookie-only request.

### 3. Lock-out through the new session check

- No tenant-reachable route writes a tombstone for an id other than the caller's own org, and none changes the `org` of a user record (user routes tried with an `org` field: ignored or 404; the victim's record unchanged). Sign-in creates sessions with the record's own org, so a mismatch can only come from deletion.
- A tombstone planted directly in the database for a live org does kill that org's sessions (401). That needs write access to `platform.db`; nothing in the app does it. A planted founding tombstone is cleared at next boot, not before.
- The check is best-effort: if `platform.db` cannot be read it is skipped and the request continues (by reading; existing design).

### 4. SEC-6c, SEC-6e

- Callback for a never-existing org: 400. `_tt_store_shop` for a dead org: `False`. Callback for a live org still stores its shop (200).
- Rows planted for a tombstone in state `deleted` (shop with tokens, order, unmapped event): all removed by the next loop; a live org's shop row kept; the audit line holds table names and counts only.
- Reserved ids refused: `videos`, `VIDEOS`, `" Videos "`, `backups`, `"support\n"`, `mon`, `SUN`, `orgs`, `platform`, `photos`, `documents`, `labels`, `products`, `invoices`; `hire_uploads` and `__platform__` fail the id pattern. Intake with those company names or as a super-admin override gets `<name>2` / `<name>3`. `hire-uploads` and `video` are allowed, correctly: neither equals a shared key name.
- Explicit purge list: with the live schema every table carrying `org_id` is in the purge or the keep list (none undecided); a clean deletion still ends `deleted`.

### 5. `unfinished_deletions`

Returned only by `GET /api/orgs`: 403 for worker, manager and admin of a tenant, 403 for the platform owner while impersonating, redirect when signed out. Fields: org id, state, attempts, two timestamps — no detail text. Tenants cannot read it.

### 6. Logging

With storage raising an error that carried a credential-looking string: not in the tombstone, not in stdout, not in the audit log, not in the response. The attention line prints org id, state, attempt count and reason codes (`storage <org>/:RuntimeError`). Two audit rows per deletion (first attempt, final state) instead of one per hour.

### Demonstration test

Now records deleted keys and asserts they equal the org's one object, with a second org's look-alike key in the store. My mutation that deletes another org's key now fails the test. SEC-6 suites re-run: 124 passed.

### SEC-6i — FIX SOON — Kept backup copies of a deleted company have no expiry

- Reproduce (done by call): run the daily backup, delete the company, run the backup and the hourly cleanup three more times → `backups/<weekday>/<org>/shipments.db` and `giveaways.db` are still stored. Those files are only ever overwritten for companies that still exist, and no code deletes anything under `backups/`. On the volume (when no bucket is configured) the same folders stay for good.
- These are the full order databases: buyer names and addresses.
- So "they expire by backup retention" holds only for `platform.db` / `users.json` (overwritten weekly) and for the dedicated backup set (about six weeks, by reading). For the per-company weekday copies it depends entirely on a lifecycle rule on the bucket, which I cannot see.
- Keeping them while SEC-7 is open is accepted by the lead and I do not block on it. What is needed: a fixed period after which the loop deletes `backups/<weekday>/<org>/` for a tombstoned id (for example 30 days after `requested_at`), in the bucket and on the volume. Owner: **programmer**; the period: **Ofir**.

### Privacy policy — the sentence about backups

> "When a company account is deleted, its data is removed from the live service at once. Copies in our backups are not edited; they are kept for up to [N] days after deletion and then erased, and are used during that time only to restore a company deleted by mistake."

`[N]` must be a number the system enforces. Today it does not enforce one for the per-company copies (SEC-6i), so the sentence cannot be published as written until that is fixed or the bucket rule is confirmed.

### Not exercised in the re-review

- Every route in the app with a dead-org cookie (a sample of 18 was tried; the rest is by reading of the gate order).
- A real bucket and any lifecycle rule on it; the dedicated backup bucket's pruning; a restore from backup of a wrongly deleted company (the id is tombstoned, so restore is a manual procedure nobody has run).
- Real gunicorn workers racing; an ingest thread caught mid-flight by a deletion (simulated by planting rows).
- The Organizations screen showing `unfinished_deletions` (API only; no template changed in this commit).
- The demo company (does not exist yet).
