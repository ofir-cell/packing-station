# Security review — SEC-5 fix: carrier routes fenced to the owner's orgs

- Date: 2026-11-11
- Reviewed: branch `fix/sec-5-carrier-account-exposure`, commit `9b2bfc5` on top of `main` (`6746598`)
- Finding under review: SEC-5 in `docs/security/2026-11-10-mobile-baseline.md`
- Reviewer: security-reviewer. Product code not touched. No test files added or changed (a qa review runs on the same working copy); tests I want are given as text at the end.

## Verdict

**FIX SOON — merge allowed.**

**SEC-5 is closed for what made it BLOCK-EXTERNAL**: no role of any other company can obtain the carrier account number or make the platform use the shared ShipStation/UPS account, and no role gained anything. It is **partly closed** overall: five residual items remain (SEC-5a … SEC-5e). All of them are either confined to the owner's own company (cs / manager / admin), or about logs, or already tracked under SEC-4. None is reachable by another company.

## How it was tested

Flask test client against a throwaway `DATA_DIR`, with fake credentials set in the environment (a fake account number, fake UPS client id/secret, fake ShipStation key and carrier id, fake USPS secret). `socket.connect` was disabled and `urllib.request.urlopen` replaced by a recorder that answers like UPS / ShipStation / USPS, so the real `_ups`, `_ups_token`, `_ss` and their error formatting ran, and every outbound attempt was counted by host. All response bodies and headers, the per-org databases, and everything the process wrote to stdout/stderr/logging were searched (case-insensitively) for each fake value. The same matrix was run against the parent commit (`git archive 6746598` into a temp dir) for the before/after comparison. Sessions were injected the way `tests/conftest.py` does.

## Results by question

### 1. Can the account number or another carrier identifier be obtained?

| Path | Result | How |
|---|---|---|
| Five gated routes (`/api/ship/carriers` incl. `?refresh=1`, `/api/ship/carriers/prefer`, `/api/label/rates`, `/api/label/rates-multi`, `/api/giveaway/<id>/rates`), other org, 6 roles, UPS and ShipStation providers | 403 everywhere, no value in any body, **0 outbound calls** | request |
| Same routes on the parent commit, other org cs/manager/admin | 200 with the number (confirms the original finding and that the fix is what closes it) | request |
| Buy routes (`/api/label/buy`, `/buy-multi`, `/api/giveaway/<id>/buy-label`), other org, 6 roles | 403 before any carrier call; the other org has 0 rows in `label_purchases` and `ship_quotes` | request |
| Buy routes, owner org, worker / picker / host | 403 | request |
| Owner org `GET /api/ship/carriers`, UPS direct | fixed id, no digits, clean | request |
| Sweep: every GET rule in the app (239), each of 6 roles in the other org, 6 roles in the owner org, the platform account, signed out | No fake value in any response for the other org, the platform account, signed out, or owner worker/picker/host/cs. Owner manager/admin: see SEC-5a and the note on ShipStation ids | request |
| `/api/mobile/session` | no carrier field | request |
| Saved preference read back, other org | nothing is saved (403), nothing to read | request |
| Audit log (`/api/audit-log`, `/admin/audit`), other org | clean; per-org table | request |
| Repo, templates, mobile, iOS bundle | the env names appear only in `app.py` and `UPS_DIRECT_SETUP.md` (placeholders) | grep |

Answer to the programmer's question on buy-route errors: **not reachable by a non-owner org** (the gate returns before the carrier is called, in every role) **and not by a low role of the owner org** (403 by role). It **is** reachable by cs / manager / admin of the owner org — SEC-5a.

### 2. Can a non-owner org make the platform call a carrier?

Every user of the shared ShipStation/UPS credentials was traced (`_ss`, `_ups`, `_ups_token`, `_ship_carriers_full`, `_ship_carrier_ids`, `_ship_rates`, `_ups_rates`, `_ship_buy`, `_ups_buy`): callers are exactly the five gated routes and the three buy routes. Measured: 0 outbound calls to UPS or ShipStation from the other org in any role, both providers. `/api/label/reconcile` reaches no carrier (`_carrier_label_lookup` is a stub). No address-validation or pickup call on the shared account exists in the code. WARP freight uses a per-org key and is out of scope here.

Not covered by this PR: **USPS tracking** on the platform's USPS credentials still runs for every org — SEC-5d.

### 3. Roles inside the owner org — no widening

Status matrix of the owner org on parent vs. fix is identical for all 12 probed routes × 6 roles × 2 providers (the only difference is that the number is gone from the carrier list). Carriers and rates: cs, manager, admin. Prefer: admin, manager. worker / picker / host: 403 on all. The decorators are untouched in the diff.

### 4. The gate

`_can_buy_labels()` = not staging, and `session["org"]` is in `SHIPPING_LABEL_ORGS` (environment; default: the founding org id). Nothing a tenant controls feeds it:
- settings rows planted in the tenant's own database (`ship_carrier_ids` and invented names) → still 403, 0 outbound (request);
- a tenant admin creating a user with `"org": "<owner id>"` in the body → the user is created in the tenant's own org (request);
- org ids are assigned by the platform owner only, are unique, lower-case, regex-checked; a company named like the owner gets a suffixed id (reading + `_slug_org_id`);
- session org variants (upper case, padded, suffixed) do not match (request; they are stopped earlier as unknown orgs);
- a worker with `admin` in extra roles in another org → 403 (request);
- staging → 403 for the owner too (request), as the commit message says.

Two hardening points — SEC-5e.

### 5. Logs

The fix adds no logging. `_ss` / `_ups` do not print requests, headers or bodies. Across the whole run the fake account number and carrier id reached the process log in one case only: an unhandled carrier error on `/api/ship/carriers/prefer` — SEC-5c. Start-up lines print only "enabled / not configured" and the base URL.

## Remaining issues

### SEC-5a — FIX SOON — Buy-route carrier errors are returned and stored unredacted (owner org only)
- Repro: owner org, cs / manager / admin; get rates, then make the carrier fail the purchase with an error text that contains the account number (mock `urlopen` → HTTP 400 or 500 on `/api/shipments/.../ship`). `POST /api/label/buy`, `/api/label/buy-multi`, `/api/giveaway/<id>/buy-label` return the text as-is; it is saved in `label_purchases.error` and returned again by `GET /api/label/uncertain` (admin, manager).
- Evidence: `app.py:15210`, `15506-15516`, `15592`.
- Not reachable by another org or by worker / picker / host.
- Fix: pass these through the same redaction, and redact before storing. Owner: **programmer**.

### SEC-5b — FIX SOON — `_carrier_err` only removes an exact copy of `UPS_ACCOUNT_NUMBER`
- Repro (owner org, cs / manager / admin, rate routes): a carrier error that carries the number in lower case or spaced out comes through; with the ShipStation provider and `UPS_ACCOUNT_NUMBER` unset (the account lives inside ShipStation) nothing is redacted at all, and ShipStation carrier ids are echoed.
- Evidence: `app.py:2299-2302`.
- Fix: do not forward raw carrier text to the browser — return a short category message plus a reference, keep the detail server-side (redacted). Owner: **programmer**.

### SEC-5c — FIX SOON — Unhandled carrier error on `/api/ship/carriers/prefer` writes the full carrier message to the server log
- Repro: owner org admin or manager, ShipStation provider, carrier list call fails → HTTP 500, traceback with the complete carrier error text in the log; the preference was already saved before the failure.
- Evidence: `app.py:15424-15425` (`_ship_carriers_full(force=True)` outside any `try`). Present before this PR.
- Fix: catch, return a redacted error, log a category only. Owner: **programmer**.

### SEC-5d — tracked under SEC-4 — USPS tracking runs on the platform's USPS credentials for every org
- Repro: other org cs / manager / admin with one shipment whose tracking code looks like USPS → `POST /api/tracking/refresh` → outbound calls to the USPS API (token + tracking). The 6-hourly `_tracking_loop` does the same for all orgs (reading).
- No credential or account identifier is returned (request). This is quota / attribution on the owner's USPS developer account, already listed in the SEC-4 outbound table; it needs a decision by Ofir whether tracking is a platform service or owner-only. Owner: **programmer** (with SEC-4).

### SEC-5e — FIX SOON (hardening) — the gate fails open on a missing org, and trusts ids that may not exist
- A session without an `org` key is treated as the founding org (`current_org() or DEFAULT_ORG`, and login uses `user.get("org", DEFAULT_ORG)`): measured, such a session gets 200 on the carrier list. No way was found for a tenant to obtain such a session (every user-creation path writes the org), so this is defence in depth: return False when there is no org.
- If `SHIPPING_LABEL_ORGS` ever names an id that does not exist (typo, or a company deleted later — see SEC-6, deleted ids can be reused), the next company provisioned with that id inherits the shared account. Check at start-up that every listed id exists, and refuse reuse of deleted ids.
- Owner: **programmer**.

### Notes (no action in this PR)
- With the ShipStation provider the owner org's cs / manager / admin still receive ShipStation carrier ids and nicknames in the carrier list, and the chosen ids are written to the owner's audit log (admin only). That is the owner's own data shown to the owner's staff; make sure no nickname in ShipStation contains an account number.
- A UPS tracking number contains the shipper number by design, so anyone who handles or receives a UPS label of the owner can derive it. This does not change the finding, but it bounds how secret the number can ever be; the control that matters is that other companies cannot ship on the account, which holds.
- Seen in passing, outside this PR: `@app.route("/api/orgs/create")` + `@req_super` sit directly on the helper `_create_tenant(org_id, company, ...)` (`app.py:13370-13372`). For qa / programmer to look at.

## Tests to add (text only — not added by me)

```python
# tests/test_sec5_carrier_gate.py — uses the existing fixtures/helpers of that file

def test_buy_route_errors_do_not_echo_the_account(appmod, carrier, monkeypatch):      # SEC-5a
    A = appmod
    _setting(A, A.DEFAULT_ORG, "ship_from", json.dumps(FRM), write=True)
    c = _client(A, A.DEFAULT_ORG, "cs")
    q = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY).get_json()
    def rejecting(method, path, payload=None):
        raise A.CarrierUncertain("UPS: shipper %s not valid" % FAKE_ACCT)
    monkeypatch.setattr(A, "_ups", rejecting)
    r = c.post("/api/label/buy", headers=c.csrf,
               json={"shipment_id": q["shipment_id"], "rate_id": q["rates"][0]["id"]})
    assert FAKE_ACCT not in r.get_data(as_text=True)
    adm = _client(A, A.DEFAULT_ORG, "admin")
    assert FAKE_ACCT not in adm.get("/api/label/uncertain").get_data(as_text=True)
    db = A.sdb(A.DEFAULT_ORG)
    try:
        assert not any(FAKE_ACCT in (row["error"] or "") for row in db.execute("SELECT error FROM label_purchases"))
    finally:
        db.close()


def test_carrier_error_text_is_not_forwarded_verbatim(appmod, carrier, monkeypatch):   # SEC-5b
    A = appmod
    c = _client(A, A.DEFAULT_ORG, "cs")
    def rejecting(method, path, payload=None):
        raise A.CarrierRejected("UPS: shipper %s / %s not valid" % (FAKE_ACCT.lower(), " ".join(FAKE_ACCT)))
    monkeypatch.setattr(A, "_ups", rejecting)
    body = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY).get_data(as_text=True).lower()
    assert FAKE_ACCT.lower() not in body and " ".join(FAKE_ACCT).lower() not in body


def test_prefer_survives_a_carrier_failure_without_a_traceback(appmod, carrier, monkeypatch):  # SEC-5c
    A = appmod
    monkeypatch.setattr(A, "UPS_ENABLED", False); monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    def failing(*a, **k):
        raise A.CarrierRejected("ShipStation: carrier se-1 shipper %s suspended" % FAKE_ACCT)
    monkeypatch.setattr(A, "_ss", failing)
    c = _client(A, A.DEFAULT_ORG, "admin")
    r = c.post("/api/ship/carriers/prefer", headers=c.csrf, json={"ids": ["se-1"]})
    assert r.status_code != 500 and FAKE_ACCT not in r.get_data(as_text=True)


def test_gate_is_closed_without_an_org_in_the_session(appmod, carrier):               # SEC-5e
    A = appmod
    c = _client(A, A.DEFAULT_ORG, "admin")
    with c.session_transaction() as s:
        s.pop("org", None)
    assert c.get("/api/ship/carriers").status_code == 403
    assert carrier == []


def test_usps_tracking_is_not_run_for_other_orgs(appmod, other_org, monkeypatch):     # SEC-5d (if Ofir decides owner-only)
    A = appmod
    seen = []
    monkeypatch.setattr(A, "USPS_ENABLED", True)
    monkeypatch.setattr(A, "_usps_track_batch", lambda tns: (seen.append(tns) or {}))
    db = A.sdb(other_org)
    db.execute("INSERT INTO shipments(shipment_id,tracking_code) VALUES('S1','9400111899223344556677')")
    db.commit(); db.close()
    c = _client(A, other_org, "admin")
    c.post("/api/tracking/refresh", headers=c.csrf, json={})
    assert seen == []
```

## What could not be exercised

- Real carrier responses: whether UPS or ShipStation actually put the account number in an error text is unknown; SEC-5a/b/c were shown with simulated error bodies.
- Production configuration: the real value of `SHIPPING_LABEL_ORGS` / `DEFAULT_ORG`, which provider is live, the nicknames inside the ShipStation account, and the existing Railway logs (whether a carrier error was already logged there in the past).
- The real sign-in path (sessions were injected, as the repo's fixtures do), several gunicorn workers, and the screens in a browser (only the JSON and HTML returned to the test client were searched).
- The background `_tracking_loop` (read, not run).
