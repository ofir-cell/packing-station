# Security review — SEC-6i fix: backup copies of a deleted company erased after 30 days

- Date: 2026-11-11
- Change: branch `fix/sec-6i-deleted-org-backup-retention`, commit `93c8fc7` on top of the SEC-6 branch (`app.py`, `ps_backup.py`, `tests/test_sec6i_backup_retention.py`)
- Reviewer: security-reviewer
- Method: direct calls and Flask test client against a throwaway `DATA_DIR`; in-memory stand-ins for the main bucket and for the dedicated backup bucket; clock injected through the `now` argument. No production system, no real bucket. Items marked *(reading)* were not exercised.

## Verdict: FIX SOON (merge allowed)

The eraser does what it claims for the per-company copies and I could not turn it against a live company. It is not CLEAR, because:

- **SEC-6i is partly closed.** Closed for `backups/<weekday>/<org>/` in the main bucket and on the volume. In the dedicated backup bucket it is closed only when in-app deletes are switched on; with the switch off nothing is erased, ever (the owner is told).
- **New: SEC-6j.** The deleted company's TikTok tokens are still readable in the live `platform.db` file, and in every backup of it taken afterwards, until the database is compacted. Not caused by this PR; found while measuring what the backups hold.
- "Erased after 30 days" is not yet a true sentence for the privacy policy in any backup mode (section 3).

| Id | Status |
|---|---|
| SEC-6i | partly closed (see above) |
| SEC-6j | **new — FIX SOON**, owner programmer |
| SEC-6d, SEC-6f, SEC-7 | unchanged, deferred by decision |

## 1. The SEC-6i reproduction is dead (main bucket and volume)

Company X deleted, with copies on all seven weekdays in the bucket and on the volume, next to copies of two look-alike companies (`delxa`, `del`), a live one, an internal one and the founding one.

| Injected time after deletion | X copies in bucket | X weekday folders on volume | State |
|---|---|---|---|
| 1 day, 29 days, 29.99 days | 8 | 7 | not tried |
| 30.01 days | 0 | 0 | `erased` |

- Every other key and folder was unchanged, including the look-alikes, `platform.db` and `users.json`.
- Three more backup runs and cleanup runs, then a pass at day 60: nothing of X came back. Neither backup job lists a deleted company.
- A company deleted the same hour: nothing erased.

## 2. Can it be turned against a live company? No way found

- The tombstone is written only by a company's own deletion. `requested_at` is set once by the database; a body carrying `requested_at`, `org`, `org_id` is ignored, and retries of the deletion do not move it.
- Tombstone rows 400 days old written straight into the database for a live company, an internal company, the founding company, `__platform__`, `videos`, `mon`, `backups`, `../<live>`, `<live>/`, `%`, `*`, `""`, `"<live>\n"`: no object deleted, no folder removed. The one row that was "erased" was the live id in upper case — a different key, nothing under it. (Planting such rows needs write access to `platform.db`.)
- A volume entry for the dead company that is a symlink to a live company's backup folder: refused (`unexpected_entry`), live copy intact.
- Dedicated bucket shape `db-backups/<run>/<org>/`: the org must equal the third path segment exactly. `""`, `.`, `..`, `a/b`, `manifest.json` are refused; `platform.db`, `users.json`, `stations.json`, a run id, `db-backups` delete nothing. Only the dead company's keys were deleted; the look-alike `delva` kept all 15 objects; all runs still verify afterwards and no manifest mentions the dead company.
- A delete refused midway (backup key without delete permission): state `failed`, runs still verify, retried next pass.

## 3. What truly remains after 30 days

Measured with unique marker strings in the seeded company's token, 2FA secret and login:

| Where | What of the deleted company | How long |
|---|---|---|
| `backups/<weekday>/<org>/` (main bucket, volume) | order databases (buyer names, addresses) | 30 days, then erased — verified |
| `db-backups/<run>/<org>/` (dedicated bucket) | order databases, packing log, documents index | switch on: 30 days — verified. Switch off: **never erased**, tombstone marked `external` — verified at day 31 and day 400 |
| `platform.db` in backups taken **before** the deletion | TikTok access and refresh tokens, tickets, billing rows | legacy job: until that weekday is overwritten, up to 7 days *(reading)*. Dedicated bucket, switch on: until the run is pruned, about six weeks *(reading; 31 days in one simulated schedule)*. Switch off: never |
| `users.json` in backups taken before the deletion | usernames, password hashes, 2FA secrets | same as the line above |
| live `platform.db` and every backup of it taken **after** the deletion | the token text is still in the file — **SEC-6j** | until the database is compacted; measured: still present in the first and second run after deletion, gone after a `VACUUM` |
| `users.json` after the deletion | nothing — verified | — |
| old `backups/<weekday>/platform.db` and `users.json` in the main bucket | whatever they held when the legacy job last ran | when the dedicated-bucket job is running, the legacy job is not started, so these seven copies are never overwritten again *(reading)* |
| kept on purpose | payments, platform audit log, sign-up contact | not time-limited |

### SEC-6j — FIX SOON — Deleted TikTok tokens stay readable in the database file
- Reproduce (done by call): seed a company with marker strings as access and refresh token, delete it, read the bytes of `platform.db`: both markers are there. Take a backup: both markers are in the backup's `platform.db`. Run `VACUUM`, take another backup: gone.
- Why: deleting a row marks its page free; the bytes stay until reused.
- With SEC-6f open (the authorisation is not ended at TikTok) these are working credentials, and each new backup renews their life.
- Fix: `PRAGMA secure_delete=ON` on the connection that purges a deleted company's rows (or compact after the purge). Owner: **programmer**.

### The truthful sentence per backup mode

**(a) Legacy backups only** — true once SEC-6j is fixed:
> "Backup copies of a deleted company's order data are erased 30 days after deletion. Sign-in and connection records leave our backups within 7 days."

**(b) Dedicated backup bucket, in-app deletes off** — "erased after 30 days" is false. The only true sentence today:
> "Backups are kept in a separate archive from which we do not delete automatically. Copies of a deleted company's data stay there until we remove them by hand, which we do on request."

A fixed number can be promised in this mode only if the bucket itself has an expiry rule; then the number is that rule's.

**(c) Dedicated backup bucket, in-app deletes on** — true once SEC-6j is fixed:
> "Backup copies of a deleted company's order data are erased 30 days after deletion. Sign-in and connection records remain in backups for up to six weeks."

In all three: payments, the security log and the sign-up contact are kept and must be listed separately (SEC-6g).

### Production facts Ofir must confirm

1. Which backup job runs in production: is `BACKUP_V2` set, and did the boot log say the scheduler started?
2. Is `BACKUP_PRUNE_IN_APP` set? It is off by default.
3. Is the backup bucket's key allowed to delete, and to overwrite a manifest?
4. Is there a bucket lock or an expiry rule on the backup bucket, and for how many days? A lock longer than 30 days makes case (c) fail and show as `stuck`.
5. Is there an expiry rule or object versioning on the main bucket?
6. If the dedicated-bucket job is running: do old `backups/<weekday>/platform.db` and `users.json` still sit in the main bucket? They need a one-time manual removal.
7. Are there volume snapshots at the hosting provider, and how long are they kept?

## 4. The trade-off, in one line

Thirty days is also the limit for undoing a wrongful wipe of the order databases, deletion still needs no password (SEC-7), and packing videos, photos and new-hire documents are not in any backup — they are gone the moment the company is deleted.

## 5. Logging and access

- A backup-bucket error carrying a credential-looking string: not in the tombstone, not printed, not in the audit log. Stored and printed: company id, state, counts, reason codes (`backup bucket:PermissionError`, `backup bucket:in_app_deletes_off`).
- One audit row per change of state.
- `GET /api/orgs` (the only place `unfinished_deletions` appears): 403 for a tenant admin, 403 for the platform owner while impersonating, redirect when signed out. New fields: `backups_state`, `backups_erased_at`, `backups_overdue` — no detail text.
- The programmer's suite: 14 passed.

## Not exercised

- A real bucket of either kind: delete permission, bucket lock, expiry rules, versioning, overwrite of a manifest under a lock.
- The real retention pruning over six weeks (one simulated schedule only); the legacy job's weekly overwrite over a real week.
- Which backup mode production runs.
- Two workers erasing the same company at once (the lock was read, not raced).
- A restore of a wrongly deleted company from these backups.
- The Organizations screen (API only).
