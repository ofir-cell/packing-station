# Security review — SEC-1 fix: 2FA on effective roles

- Date: 2026-11-11
- PR: branch `fix/sec-1-2fa-effective-roles`, commit `37b69cd` on `main` (`6746598`)
- Scope of the change: `app.py` (`_twofa_required`, `_session_revocation`, `me_page`), two test files
- Method: Flask test client against a throwaway `DATA_DIR` (never production). 408 routes swept. "Request" = measured with a real request; "reading" = code only.

## Verdict

**FIX SOON — merge allowed.** The change does what it says, nothing got worse, and I found no way through the hold. **SEC-1 is partly closed**: the path in the original finding (password login of a user with `admin` in `extra_roles`) is closed; four items remain (SEC-1a … SEC-1d). SEC-1a is as serious as the original finding and predates this PR.

| Id | Rating | One line | Owner |
|---|---|---|---|
| SEC-1a | **BLOCK-EXTERNAL** (not caused by this PR) | The platform owner (`superadmin`) signs in with a password only, cannot enrol in 2FA at all, and can enter any company as admin. | programmer |
| SEC-1b | **FIX SOON** — recommended before or with the deploy | The hold is decided only at login and on a role change. Sessions that are already admin and not enrolled are never re-checked. | programmer (+ Ofir for the deploy step) |
| SEC-1c | Decision for Ofir | Warehouse Manager (near-admin) still needs no 2FA. Policy unchanged by this PR, as stated. | Ofir, then programmer |
| SEC-1d | FIX SOON (low) | Enrolment is "first session wins": whoever holds the password when admin is granted enrols their own authenticator. | programmer |

## What was verified, per question

### 1. Ways to hold admin power, and whether password login requires 2FA

| Way | Result | How |
|---|---|---|
| Primary `admin`, not enrolled | Held: `/api/users`, `/api/audit-log`, `/api/shows` → 403 `need_2fa_setup`; pages → 302 `/me?setup2fa=1` | request |
| `worker` / `host` / `cs` + `extra_roles: ["admin"]`, not enrolled | Held, same as above | request |
| Same, enrolled | Password gives `twofa: true` and no session; code completes it | request |
| Created through `POST /api/users/add` with `extra_roles: ["admin"]` | Held at first login | request |
| Mass-assignment of `twofa_exempt` / `twofa_enabled` through `/api/users/add` and `/api/users/roles` | Ignored, not stored | request |
| Malformed stored values (`extra_roles: "admin"` as a string, `"Admin"`, `" admin"`, role `"Admin"`) | No 2FA asked, but no admin power either (`/api/users` 403) — consistent | request |
| `manager`, or `manager` as extra role | No 2FA, by policy. Not a true admin (`/api/users`, `/api/audit-log`, `/admin/settings` 403) but passes every other `req_role("admin")` route | request → SEC-1c |
| **`superadmin` (platform owner)** | **Password only. `_twofa_required` is false. `/api/2fa/setup` and `/api/2fa/status` → 403, so it cannot enrol. `POST /api/impersonate {"org_id": B}` → `/api/users` and `/api/audit-log` of org B → 200** | request → **SEC-1a** |
| Impersonation ("support mode") | Only reachable from a `superadmin` session; a held user gets 403 | request |
| `twofa_exempt: true` on an extra-role admin in an ordinary org | Full admin with a password | request — this is SEC-3, unchanged, as the PR says |
| Session role lists | `session["roles"]` is set only in `_finalize_login`, `api_badge_login`, `_session_revocation`, impersonate enter/exit | reading |
| Per-org role overrides, API tokens, bearer auth, an `agent` role | None exist in the code | reading (grep) |

### 2. Is `_twofa_required` the single decision point?

Yes for the 2FA requirement. Callers: `_finalize_login`, `_session_revocation`, `api_2fa_status`, `api_2fa_disable`. The code step in `api_login` keys on `twofa_enabled`, not on a role, which is correct. The `/me` template gate (`ROLE!=="admin"`, `templates.py:2667`) is fed by the fixed `me_page`. No other 2FA check reads the primary role. (reading + request)

Primary-role-only checks that remain elsewhere, not 2FA but worth knowing:
- `api_account_delete` counts admins by primary role (`app.py:4841-4842`). A company whose only admin holds it through `extra_roles` can delete that account with no `need_org_confirm`; the company is left with no admin (request: 200, org row still present).
- Many screens use `session.get("role")=="admin"` for cost/price visibility. An extra-role admin sees less, never more. (reading)

### 3. Sessions created without the gate

| Path | Result | How |
|---|---|---|
| Badge login, worker + extra admin, not enrolled | `/api/users` 200, no `must_setup_2fa` | request — **SEC-2, exactly as before** |
| Badge login, worker + extra admin, enrolled | `/api/users` 200, no code asked | request — SEC-2 |
| Badge login, primary admin with a badge | `/api/users` 200 | request — SEC-2 |
| Badge session opened as a plain worker, admin granted afterwards | Held on the next request | request — slightly better than `main` |
| Badge scan from inside a held session | 403 (gate); a fresh browser badge scan still works (SEC-2) | request |
| `pending_2fa` (password accepted, code not given) | Nothing reachable: `/api/users`, `/api/shows`, `/api/me/stats`, `/me` → not signed in; wrong code changes nothing | request |
| Remember-me | Does not exist; `session.permanent` is never set | reading |
| Token, magic-link, org-switch sign-in | None exist. Org changes only through impersonation | reading |
| `/api/mobile/session` | Creates no session. While held it answers 403 `need_2fa_setup` — see note N1 | request |

### 4. The hold

Reachable while held (full sweep of 408 routes, GET and every other declared method; everything else is 403 `need_2fa_setup` or 302 `/me?setup2fa=1`):

- `GET /me`, `GET /api/me/stats`, `GET /privacy`, `GET /terms`, `GET /login` (redirect), `/logout`
- `GET /static/...`, `GET /guide-asset/...`
- `GET /api/2fa/status`, `POST /api/2fa/setup`, `POST /api/2fa/enable`, `POST /api/2fa/disable`, `POST /api/2fa/recovery`
- `POST /api/account/delete`

Findings (all by request):
- The `/api/2fa/*` routes act on `session["user"]` only. A `username` in the body is ignored; another admin's record was byte-identical afterwards.
- `/api/me/stats` returns the caller's own counters; `user` / `name` query parameters are ignored. `/me` contains no other user.
- A held user cannot set `twofa_exempt`, change roles, reset a password, add a user or impersonate: all 403 `need_2fa_setup`. No route writes `twofa_exempt` at all (reading: 24 writers of `users.json`).
- There is no "reset someone's 2FA" route (reading).
- Path tricks (`//api/users`, `/api/users/`, `/API/users`, `/static/../api/users`, `/api/2fa/../users`, `%2e%2e`, `%2f`, query-string decoys) → 403, 404 or redirect; none reached a handler.
- `POST /api/account/delete` works while held, with no password. That is SEC-7, unchanged.

### 5. Sessions issued before the deploy — SEC-1b, FIX SOON

Reproduction (request): a session cookie with `roles: ["worker","admin"]` and no `must_setup_2fa`, user not enrolled → `GET /api/users` 200 and `POST /api/users/add {"role":"admin"}` creates an admin. `/api/2fa/status` says `required: true, must_setup: false`.

Cause: `_session_revocation` re-decides the hold only inside `if sorted(live)!=sorted(session roles)`. The same gap, also measured:
- an admin turns 2FA off in one browser; their other signed-in browser stays a full admin with no 2FA on the account;
- `twofa_exempt` removed from a signed-in account: that session stays unheld.

Lifetime: the cookie is signed with a timestamp and accepted for 7 days (`PERMANENT_SESSION_LIFETIME`), and it is re-signed whenever the session is written (for example station selection), so an active session can outlive 7 days (reading).

Why FIX SOON and not BLOCK: the PR is strictly better than `main`, the affected group is only extra-role admins who are signed in at deploy time and not enrolled, and there is a deploy-time step that removes the exposure without code.

Smallest safe fix, in `_session_revocation`, replacing the four lines added by this PR and moved one level out of the `if`:

```python
        _need=_twofa_required(rec) and not rec.get("twofa_enabled")
        if _need and not session.get("must_setup_2fa"):
            session["must_setup_2fa"]=True
            return _twofa_setup_gate()
        if not _need: session.pop("must_setup_2fa",None)
```

Tried on a throwaway copy (never in this working copy): the pre-deploy session, the second browser after a 2FA disable, and the removed exemption are all held on the next request. Two consequences the programmer must know:
1. It also holds badge sessions of admins who are not enrolled (part of SEC-2). Enrolled admins still get in with a badge alone.
2. About 40 existing tests forge an admin session for a user who is not enrolled (starting with the `admin` fixture in `tests/conftest.py`) and fail with this change. They need an enrolled admin in the fixtures. That is test work, not a product problem, but it makes this more than a five-line PR.

If the code change is not made before the deploy, either of these closes the window (Ofir's action, not an agent's):
- before deploying, look for accounts with `admin` in `extra_roles` and no `twofa_enabled`; if there are none, nobody is exposed;
- or change `SECRET_KEY` in Railway with the deploy, outside packing hours. Every session ends and everyone signs in again. The key also signs the TikTok connect state, so a shop connection in progress at that moment must be restarted.

### 6. Role changed mid-session

- Admin granted through the real `POST /api/users/roles`; the worker's very next request was `POST /api/users/add` → 403 `need_2fa_setup`, user not created. (request)
- Replaying the cookie from before the grant three times → 403 each time; the target record unchanged. (request)
- Legacy cookie with no `roles` key → held. (request)
- User deleted mid-session → 401 `session_revoked`. (request)
- Admin removed while held → released, but only after a request to an open path (`/me`, `/api/me/stats`, `/api/2fa/status`), because the hold gate answers before the role re-sync runs. A browser lands on `/me` by the redirect and is fine. See N2.

### Tenant isolation (unchanged, re-checked)

An enrolled extra-role admin of org A: org B's users are not in `/api/users`; `POST /api/users/pw` on an org B user → `ok: false`; `POST /api/users/roles` → 404; record unchanged. (request)

## Remaining issues

### SEC-1a — BLOCK-EXTERNAL — Platform owner has no second factor
- Repro: set `SUPERADMIN_USER`; `POST /api/login` with its password → `ok: true`, no `twofa`, no `must_setup_2fa`. `POST /api/2fa/setup` → 403. `POST /api/impersonate {"org_id": "<any org>"}` → `ok`; `GET /api/users`, `GET /api/audit-log` of that org → 200.
- Evidence: `_twofa_required` looks for `admin`; the role is `superadmin`. `/api/2fa/*` is `req_role("admin")`. `_session_revocation` skips `superadmin` and impersonating sessions (`app.py:3950`), so such a session is never re-checked, even if the account is removed.
- Impact: one password opens every company. This is the single account for which 2FA matters most.
- Fix: require 2FA for `superadmin` in `_twofa_required`; let `superadmin` use `/api/2fa/*`; keep the hold gate in front of `/api/impersonate` and `/admin/organizations` (it already is by default). Decide separately whether impersonating sessions should be re-validated. Owner: programmer.

### SEC-1b — FIX SOON — see section 5.

### SEC-1c — Decision — Warehouse Manager without 2FA
A manager passes every `req_role("admin")` route outside `_MANAGER_BLOCK_PREFIXES`, including label rate requests and most admin screens, with a password only. The baseline asked for a decision; this PR keeps the policy on purpose. If Ofir decides managers need 2FA, it is a one-line change in `_twofa_required` plus tests. Owner: Ofir, then programmer.

### SEC-1d — FIX SOON (low) — First session enrols
The hold lets any password-only session of the account enrol. If a worker's password is already known to someone else when that worker is given admin, that person enrols their own authenticator and is a full admin. Same behaviour exists on `main` for a new primary admin. Fix options: the granting admin issues a one-time enrolment code, or enrolment requires the password again. Owner: programmer.

## Notes for the owners (not security findings)

- **N1 (mobile-engineer):** `/api/mobile/session` is not in the hold's open list, so a held admin in the native app gets 403 from the bootstrap call and no CSRF token. Same on `main` for a primary admin; this PR adds extra-role admins to the group. Not proven on a device.
- **N2 (programmer):** a held user who loses admin stays held for API-only clients until an open path is requested (section 6).
- **N3 (programmer):** last-admin check in `api_account_delete` ignores `extra_roles` (section 2).

## Tests I want added (text only; I did not add or change tests)

1. `superadmin` password login must not reach `/api/impersonate` without a second factor (strict xfail, reason `SEC-1a`).
2. Forged session `roles=["worker","admin"]`, user not enrolled, no `must_setup_2fa` → `/api/users` must be 403 `need_2fa_setup` (strict xfail, reason `SEC-1b`).
3. Two sessions of one enrolled admin; 2FA turned off in one → the other is held on its next request (strict xfail, `SEC-1b`).
4. Mid-session grant through `POST /api/users/roles` (not by editing `users.json`), first request is `POST /api/users/add` → 403 and no user created. Passes today; locks in section 6.
5. Replay of the pre-grant cookie → 403. Passes today.
6. Held user: `POST /api/2fa/enable {"username": <other admin>}` leaves the other record unchanged; `POST /api/users/roles` with `twofa_exempt: true` never stores the flag. Passes today.
7. Sweep: for a held session, every route outside the open list answers 403 `need_2fa_setup` or 302 `/me?setup2fa=1`. Passes today; catches a future route added to the open list by mistake.

## Not exercised

- Production data: whether any real account has `admin` in `extra_roles` without 2FA, and whether such sessions exist now.
- The native iOS app and real browsers (cookie persistence across app restarts, N1). Nothing here is proven on a device.
- Several gunicorn workers at once (the test client is one process). The hold lives in the signed cookie and in `users.json`, so I expect no difference, but it was not run.
- The 7-day expiry and the re-signing behaviour of the cookie: read, not timed.
- The suggested SEC-1b change was run only on a throwaway copy, with the existing suite red until fixtures are updated.
- SEC-3, SEC-7, SEC-10 and the demo company: out of scope for this PR; touched only where they meet the hold.
