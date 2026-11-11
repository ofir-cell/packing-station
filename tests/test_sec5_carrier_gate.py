"""SEC-5 — the shared carrier account (docs/security/2026-11-10-mobile-baseline.md).

Every route that reaches the platform owner's ShipStation/UPS account is behind the
same per-org gate as label purchase (`_can_buy_labels`), and the account number never
goes to a browser — not even for the owner's own org.

No network: the carrier transports (`_ups`, `_ups_token`, `_ss`) are replaced and
`urlopen` is booby-trapped. The account number below is a fake value.
"""
import json
import uuid

import pytest

FAKE_ACCT = "QQ77FAKE"
ROLES = ("worker", "picker", "host", "cs", "manager", "admin")
TO = {"name": "T", "street1": "1 A St", "city": "Davie", "state": "FL", "zip": "33328"}
FRM = {"name": "W", "street1": "2 B St", "city": "Davie", "state": "FL", "zip": "33328"}
RATES_BODY = {"to_address": TO, "from_address": FRM, "weight_oz": 8}
MULTI_BODY = {"to_address": TO, "from_address": FRM, "boxes": [{"weight_oz": 8}, {"weight_oz": 12}]}


def _client(A, org, role):
    name = "%s-%s" % (org, role)
    if name not in A.ldj(A.USERS_FILE):                   # owner-org test users (temp DATA_DIR only)
        with A.update_json(A.USERS_FILE) as users:
            users[name] = {"password": A._h("Passw0rd!x"), "role": role, "name": role, "org": org}
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="%s-%s" % (org, role), role=role, roles=[role], name=role, org=org)
    c.set_cookie("csrf_token", "tok")
    c.csrf = {"X-CSRF-Token": "tok"}
    return c


@pytest.fixture
def other_org(appmod):
    A = appmod
    org = "sec5b" + uuid.uuid4().hex[:6]
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (org, org.upper() + " Co", org[:10].upper(), "active"))
    c.commit(); c.close()
    A.provision_org(org)
    with A.update_json(A.USERS_FILE) as users:
        for r in ROLES:
            users["%s-%s" % (org, r)] = {"password": A._h("Passw0rd!x"), "role": r, "name": r, "org": org}
    return org


def _setting(A, org, key, value=None, write=False):
    c = A.sdb(org)
    try:
        if write:
            if value is None:
                c.execute("DELETE FROM settings WHERE key=?", (key,))
            else:
                c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (key, value))
            c.commit()
            return value
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else None
    finally:
        c.close()


def _giveaway(A, org):
    A.gdb_init(org)
    c = A.gdb(org)
    cur = c.execute("INSERT INTO giveaways(winner_username,prize_name,address_name,address_street1,address_city,"
                    "address_state,address_zip) VALUES('w','Prize','T','1 A St','Davie','FL','33328')")
    gid = cur.lastrowid
    c.commit(); c.close()
    return gid


@pytest.fixture
def carrier(appmod, monkeypatch):
    """UPS direct 'configured' with a fake account; every transport recorded, none real."""
    A = appmod
    calls = []

    def boom(*a, **k):
        raise AssertionError("a test reached the network")
    monkeypatch.setattr(A._urlreq, "urlopen", boom)
    monkeypatch.setattr(A, "IS_STAGING", False)
    monkeypatch.setattr(A, "STAGING_SAFE", False)
    monkeypatch.setattr(A, "UPS_ENABLED", True)
    monkeypatch.setattr(A, "SHIPSTATION_ENABLED", False)
    monkeypatch.setattr(A, "EASYPOST_ENABLED", True)
    monkeypatch.setattr(A, "UPS_ACCOUNT_NUMBER", FAKE_ACCT)
    monkeypatch.setattr(A, "_ups_token", lambda *a, **k: (calls.append(("token",)) or "t"))

    def fake_ups(method, path, payload=None):
        calls.append(("ups", method, path, payload))
        return {"RateResponse": {"RatedShipment": [
            {"Service": {"Code": "03"}, "TotalCharges": {"MonetaryValue": "9.10"}},
            {"Service": {"Code": "02"}, "TotalCharges": {"MonetaryValue": "21.40"}}]}}
    monkeypatch.setattr(A, "_ups", fake_ups)

    def fake_ss(method, path, payload=None, idem_key=None):
        calls.append(("ss", method, path, payload))
        return {"carriers": [{"carrier_id": "se-1", "carrier_code": "ups", "friendly_name": "UPS", "services": [1, 2]}]}
    monkeypatch.setattr(A, "_ss", fake_ss)
    monkeypatch.setitem(A._ss_carriers, "list", None)
    return calls


def _routes(c, gid):
    """Every carrier route that reaches the shared account, as (name, response)."""
    return [
        ("GET /api/ship/carriers", c.get("/api/ship/carriers")),
        ("GET /api/ship/carriers?refresh=1", c.get("/api/ship/carriers?refresh=1")),
        ("POST /api/ship/carriers/prefer", c.post("/api/ship/carriers/prefer", headers=c.csrf, json={"ids": ["se-1"]})),
        ("POST /api/label/rates", c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY)),
        ("POST /api/label/rates-multi", c.post("/api/label/rates-multi", headers=c.csrf, json=MULTI_BODY)),
        ("POST /api/giveaway/<id>/rates", c.post("/api/giveaway/%d/rates" % gid, headers=c.csrf, json={"weight_oz": 8})),
    ]


def test_non_owner_org_is_refused_on_every_carrier_route(appmod, other_org, carrier):
    A = appmod
    gid = _giveaway(A, other_org)
    before = _setting(A, other_org, "ship_carrier_ids")
    for role in ("admin", "cs", "manager"):
        c = _client(A, other_org, role)
        for name, r in _routes(c, gid):
            assert r.status_code == 403, (role, name, r.status_code)
            assert FAKE_ACCT not in r.get_data(as_text=True), (role, name)
            if r.is_json:                                 # (cs on /prefer is refused by role: plain 403)
                assert r.get_json().get("ok") is False, (role, name)
    assert carrier == [], "a non-owner org reached the shared carrier account: %r" % (carrier,)
    assert _setting(A, other_org, "ship_carrier_ids") == before      # prefer wrote nothing


def test_non_owner_org_refused_with_shipstation_provider_too(appmod, other_org, carrier, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "UPS_ENABLED", False)
    monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    gid = _giveaway(A, other_org)
    c = _client(A, other_org, "admin")
    for name, r in _routes(c, gid):
        assert r.status_code == 403, (name, r.status_code)
    assert carrier == []


def test_owner_org_still_gets_carriers_without_the_account_number(appmod, carrier):
    A = appmod
    c = _client(A, A.DEFAULT_ORG, "admin")
    r = c.get("/api/ship/carriers")
    d = r.get_json()
    assert r.status_code == 200 and d["ok"] is True and d["provider"] == "ups" and d["count"] == 1
    row = d["carriers"][0]
    assert row["carrier_code"] == "ups" and row["account_connected"] is True
    assert row["services"] == len(A.UPS_SERVICE_NAMES)
    assert FAKE_ACCT not in r.get_data(as_text=True)
    assert ("token",) in carrier                     # credentials are still verified as before


def test_owner_org_carrier_errors_never_echo_the_account_number(appmod, carrier, monkeypatch):
    A = appmod

    def bad(*a, **k):
        raise RuntimeError("UPS: shipper %s is not valid" % FAKE_ACCT)
    monkeypatch.setattr(A, "_ups_token", bad)
    monkeypatch.setattr(A, "_ups", bad)
    c = _client(A, A.DEFAULT_ORG, "admin")
    r1 = c.get("/api/ship/carriers")
    r2 = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY)
    r3 = c.post("/api/label/rates-multi", headers=c.csrf, json=MULTI_BODY)
    r4 = c.post("/api/giveaway/%d/rates" % _giveaway(A, A.DEFAULT_ORG), headers=c.csrf,
                json={"weight_oz": 8, "from_address": FRM})
    for r in (r1, r2, r3):
        assert r.get_json()["ok"] is False and "UPS:" in r.get_json()["error"]
    for r in (r1, r2, r3, r4):
        assert FAKE_ACCT not in r.get_data(as_text=True)


def test_owner_org_still_gets_rates(appmod, carrier):
    A = appmod
    for role in ("admin", "cs"):
        del carrier[:]
        c = _client(A, A.DEFAULT_ORG, role)
        r = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY)
        d = r.get_json()
        assert r.status_code == 200 and d["ok"] is True, (role, d)
        assert d["shipment_id"].startswith("upsq_")
        assert [(x["service"], x["rate"]) for x in d["rates"]] == [("UPS Ground", "9.10"), ("UPS 2nd Day Air", "21.40")]
        assert all(x["id"].startswith(d["shipment_id"] + "~") for x in d["rates"])
        assert FAKE_ACCT not in r.get_data(as_text=True)
        ups = [x for x in carrier if x[0] == "ups"]
        assert len(ups) == 1 and ups[0][2].startswith("/api/rating/")
        # the outbound request itself is unchanged: it still rates on the owner's account
        assert ups[0][3]["RateRequest"]["Shipment"]["Shipper"]["ShipperNumber"] == FAKE_ACCT


def test_owner_org_still_gets_multi_box_and_giveaway_rates(appmod, carrier):
    A = appmod
    c = _client(A, A.DEFAULT_ORG, "admin")
    r = c.post("/api/label/rates-multi", headers=c.csrf, json=MULTI_BODY)
    d = r.get_json()
    assert r.status_code == 200 and d["ok"] is True and d["boxes"] == 2, d
    assert d["rates"][0]["total"] == 18.2 and len(d["rates"][0]["legs"]) == 2
    assert d["best_mix"]["total"] == 18.2
    assert FAKE_ACCT not in r.get_data(as_text=True)

    old = _setting(A, A.DEFAULT_ORG, "ship_from")
    _setting(A, A.DEFAULT_ORG, "ship_from", json.dumps(FRM), write=True)
    try:
        gid = _giveaway(A, A.DEFAULT_ORG)
        r = c.post("/api/giveaway/%d/rates" % gid, headers=c.csrf, json={"weight_oz": 8})
        d = r.get_json()
        assert r.status_code == 200 and d["ok"] is True and len(d["rates"]) == 2, d
        assert FAKE_ACCT not in r.get_data(as_text=True)
    finally:
        _setting(A, A.DEFAULT_ORG, "ship_from", old, write=True)


def test_owner_org_shipstation_carrier_list_and_prefer_unchanged(appmod, carrier, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "UPS_ENABLED", False)
    monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    c = _client(A, A.DEFAULT_ORG, "admin")
    old = _setting(A, A.DEFAULT_ORG, "ship_carrier_ids")
    try:
        d = c.get("/api/ship/carriers").get_json()
        assert d["ok"] is True and d["count"] == 1
        assert d["carriers"][0]["carrier_id"] == "se-1" and d["carriers"][0]["services"] == 2
        r = c.post("/api/ship/carriers/prefer", headers=c.csrf, json={"ids": ["se-1"]})
        assert r.status_code == 200 and r.get_json() == {"ok": True, "preferred": ["se-1"], "restricted": True}
        d = c.get("/api/ship/carriers").get_json()
        assert d["restricted"] is True and d["carriers"][0]["selected"] is True
    finally:
        _setting(A, A.DEFAULT_ORG, "ship_carrier_ids", old, write=True)


def test_label_purchase_gate_is_untouched(appmod, other_org, carrier):
    """Buying was already fenced; this change must not move it."""
    A = appmod
    c = _client(A, other_org, "admin")
    for path in ("/api/label/buy", "/api/label/buy-multi"):
        assert c.post(path, headers=c.csrf, json={"shipment_id": "x", "rate_id": "y"}).status_code == 403, path
    assert carrier == []
