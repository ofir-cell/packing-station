"""SEC-5 — QA gate tests on top of tests/test_sec5_carrier_gate.py.

What these add:
  * every role of the owner's org AND of another org, on every carrier route (list, prefer,
    rates, multi rates, giveaway rates, the three buy routes, the two pages) and with both
    providers: the account number is in no response;
  * the owner's real flow end to end with the masked id sent back: carriers -> prefer
    ("ups-direct") -> rates -> buy, multi-box and giveaway included; the outbound UPS
    requests still carry the real account, a repeated buy is not a second purchase;
  * a preference saved before the change (old id) or after it (masked id) never empties the
    carrier list used for rating;
  * staging: refused before any transport is touched.

No network: transports are replaced, `urlopen` is booby-trapped (fixture `carrier`). The
account number is a fake value.
"""
import json

import pytest

from test_sec5_carrier_gate import (  # noqa: F401  (fixtures re-used on purpose)
    FAKE_ACCT, FRM, MULTI_BODY, RATES_BODY, ROLES, _client, _giveaway, _routes, _setting,
    carrier, other_org,
)

SHIP_OK = {"ShipmentResponse": {"ShipmentResults": {
    "ShipmentCharges": {"TotalCharges": {"MonetaryValue": "9.10"}},
    "PackageResults": [{"TrackingNumber": "1ZTESTQA0000000001"}]}}}
RATE_OK = {"RateResponse": {"RatedShipment": [
    {"Service": {"Code": "03"}, "TotalCharges": {"MonetaryValue": "9.10"}},
    {"Service": {"Code": "02"}, "TotalCharges": {"MonetaryValue": "21.40"}}]}}


@pytest.fixture
def ups_full(appmod, carrier, monkeypatch):
    """`carrier` + a UPS transport that answers both rating and shipping."""
    A = appmod

    def fake_ups(method, path, payload=None):
        carrier.append(("ups", method, path, payload))
        return SHIP_OK if "/shipments/" in path else RATE_OK
    monkeypatch.setattr(A, "_ups", fake_ups)
    return carrier


@pytest.fixture
def owner_ship_from(appmod):
    A = appmod
    old = _setting(A, A.DEFAULT_ORG, "ship_from")
    _setting(A, A.DEFAULT_ORG, "ship_from", json.dumps(FRM), write=True)
    yield
    _setting(A, A.DEFAULT_ORG, "ship_from", old, write=True)


@pytest.fixture
def owner_pref(appmod):
    """Restore the owner org's carrier preference after the test."""
    A = appmod
    old = _setting(A, A.DEFAULT_ORG, "ship_carrier_ids")
    yield
    _setting(A, A.DEFAULT_ORG, "ship_carrier_ids", old, write=True)
    A._ss_carriers["list"] = None


def _ships(calls):
    return [x for x in calls if x[0] == "ups" and "/shipments/" in x[2]]


def _all_carrier_responses(c, gid):
    out = _routes(c, gid)
    out += [
        ("POST /api/label/buy", c.post("/api/label/buy", headers=c.csrf, json={"shipment_id": "upsq_none", "rate_id": "upsq_none~03"})),
        ("POST /api/label/buy-multi", c.post("/api/label/buy-multi", headers=c.csrf,
                                             json={"legs": [{"shipment_id": "upsq_none", "rate_id": "upsq_none~02"}]})),
        ("POST /api/giveaway/<id>/buy-label", c.post("/api/giveaway/%d/buy-label" % gid, headers=c.csrf,
                                                     json={"shipment_id": "upsq_none", "rate_id": "upsq_none~03"})),
        ("GET /admin/inbound", c.get("/admin/inbound")),
        ("GET /giveaway/<id>", c.get("/giveaway/%d" % gid)),
    ]
    return out


# ───────────── 1. acceptance: the number is in no response, any org, any role ─────────────

@pytest.mark.parametrize("provider", ["ups", "shipstation"])
def test_qa_no_role_of_any_org_ever_receives_the_account_number(appmod, other_org, ups_full, owner_pref,
                                                                owner_ship_from, monkeypatch, provider):
    A = appmod
    if provider == "shipstation":
        monkeypatch.setattr(A, "UPS_ENABLED", False)
        monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    for org in (A.DEFAULT_ORG, other_org):
        gid = _giveaway(A, org)
        for role in ROLES:
            c = _client(A, org, role)
            for name, r in _all_carrier_responses(c, gid):
                assert FAKE_ACCT not in r.get_data(as_text=True), (provider, org, role, name)
                assert FAKE_ACCT not in json.dumps(dict(r.headers)), (provider, org, role, name)


def test_qa_roles_are_enforced_on_the_server_for_the_owner_org(appmod, ups_full, owner_pref, owner_ship_from):
    """worker / picker / host of the OWNER org reach no carrier route and no transport."""
    A = appmod
    gid = _giveaway(A, A.DEFAULT_ORG)
    for role in ("worker", "picker", "host"):
        c = _client(A, A.DEFAULT_ORG, role)
        for name, r in _routes(c, gid):
            assert r.status_code in (401, 403) or (300 <= r.status_code < 400), (role, name, r.status_code)
    assert ups_full == []
    # cs may rate but may not change the carrier preference
    cs = _client(A, A.DEFAULT_ORG, "cs")
    before = _setting(A, A.DEFAULT_ORG, "ship_carrier_ids")
    assert cs.post("/api/ship/carriers/prefer", headers=cs.csrf, json={"ids": ["x"]}).status_code == 403
    assert _setting(A, A.DEFAULT_ORG, "ship_carrier_ids") == before


# ───────────── 2. owner flow end to end with the masked id sent back ─────────────

def test_qa_owner_ups_flow_carriers_prefer_masked_id_rates_buy(appmod, ups_full, owner_pref, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_store_label", lambda data, ext: "/label/file/qa." + ext)
    c = _client(A, A.DEFAULT_ORG, "admin")

    row = c.get("/api/ship/carriers").get_json()["carriers"][0]
    assert row["carrier_id"] == "ups-direct"
    # the desktop strip sends [] when every box is ticked; send the masked id itself too
    for ids in ([], [row["carrier_id"]]):
        r = c.post("/api/ship/carriers/prefer", headers=c.csrf, json={"ids": ids})
        assert r.status_code == 200 and r.get_json()["ok"] is True, ids
        assert c.get("/api/ship/carriers").get_json()["ok"] is True

        del ups_full[:]
        d = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY).get_json()
        assert d["ok"] is True and len(d["rates"]) == 2, (ids, d)
        rate = d["rates"][0]
        b1 = c.post("/api/label/buy", headers=c.csrf, json={"shipment_id": d["shipment_id"], "rate_id": rate["id"]})
        j1 = b1.get_json()
        assert b1.status_code == 200 and j1["ok"] is True and j1["tracking"] == "1ZTESTQA0000000001", (ids, j1)
        ships = _ships(ups_full)
        assert len(ships) == 1
        shp = ships[0][3]["ShipmentRequest"]["Shipment"]
        # the purchase is still made on, and billed to, the real account — not the masked id
        assert shp["Shipper"]["ShipperNumber"] == FAKE_ACCT
        assert shp["PaymentInformation"]["ShipmentCharge"][0]["BillShipper"]["AccountNumber"] == FAKE_ACCT
        assert shp["Service"]["Code"] == "03"
        # money: the same click again buys nothing more
        j2 = c.post("/api/label/buy", headers=c.csrf, json={"shipment_id": d["shipment_id"], "rate_id": rate["id"]}).get_json()
        assert j2["ok"] is True and j2.get("idempotent") is True
        assert len(_ships(ups_full)) == 1
        assert FAKE_ACCT not in json.dumps(j1) + json.dumps(j2)


def test_qa_owner_multi_box_flow_rates_then_buy(appmod, ups_full, owner_pref, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_store_label", lambda data, ext: "/label/file/qa." + ext)
    c = _client(A, A.DEFAULT_ORG, "admin")
    assert c.post("/api/ship/carriers/prefer", headers=c.csrf, json={"ids": ["ups-direct"]}).get_json()["ok"]
    d = c.post("/api/label/rates-multi", headers=c.csrf, json=MULTI_BODY).get_json()
    assert d["ok"] is True and d["boxes"] == 2
    legs = d["rates"][0]["legs"]
    body = {"legs": legs, "supplier": "QA Supplier"}
    r = c.post("/api/label/buy-multi", headers=c.csrf, json=body)
    j = r.get_json()
    assert r.status_code == 200 and j["ok"] is True and j["count"] == 2, j
    assert len(_ships(ups_full)) == 2
    j2 = c.post("/api/label/buy-multi", headers=c.csrf, json=body).get_json()
    assert j2["ok"] is True and all(x["idempotent"] for x in j2["labels"])
    assert len(_ships(ups_full)) == 2                      # double submit: no third/fourth label
    assert FAKE_ACCT not in json.dumps(j) + json.dumps(j2)


def test_qa_owner_giveaway_flow_rates_then_buy_once(appmod, ups_full, owner_pref, owner_ship_from, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_store_label", lambda data, ext: "/label/file/qa." + ext)
    c = _client(A, A.DEFAULT_ORG, "cs")
    gid = _giveaway(A, A.DEFAULT_ORG)
    d = c.post("/api/giveaway/%d/rates" % gid, headers=c.csrf, json={"weight_oz": 8}).get_json()
    assert d["ok"] is True and d["rates"], d
    body = {"shipment_id": d["shipment_id"], "rate_id": d["rates"][0]["id"]}
    j = c.post("/api/giveaway/%d/buy-label" % gid, headers=c.csrf, json=body).get_json()
    assert j["ok"] is True and j["tracking"] == "1ZTESTQA0000000001", j
    j2 = c.post("/api/giveaway/%d/buy-label" % gid, headers=c.csrf, json=body).get_json()
    assert j2["ok"] is False                                 # already purchased
    assert len(_ships(ups_full)) == 1
    assert FAKE_ACCT not in json.dumps(j) + json.dumps(j2)


# ───────────── 3. preferences saved with the old id / the masked id ─────────────

@pytest.mark.parametrize("stored", [[FAKE_ACCT], ["ups-direct"]])
def test_qa_stored_preference_never_breaks_ups_rating(appmod, ups_full, owner_pref, stored):
    A = appmod
    _setting(A, A.DEFAULT_ORG, "ship_carrier_ids", json.dumps(stored), write=True)
    c = _client(A, A.DEFAULT_ORG, "admin")
    r = c.get("/api/ship/carriers")
    assert r.get_json()["ok"] is True and FAKE_ACCT not in r.get_data(as_text=True)
    d = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY).get_json()
    assert d["ok"] is True and len(d["rates"]) == 2


@pytest.mark.parametrize("stored", [[FAKE_ACCT], ["ups-direct"]])
def test_qa_stored_preference_falls_back_to_all_carriers_on_shipstation(appmod, carrier, owner_pref, monkeypatch, stored):
    """If the provider is ShipStation, an id that is not a connected ShipStation carrier
    must not empty the list that is rated against (it falls back to every carrier)."""
    A = appmod
    monkeypatch.setattr(A, "UPS_ENABLED", False)
    monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    _setting(A, A.DEFAULT_ORG, "ship_carrier_ids", json.dumps(stored), write=True)
    with A.app.test_request_context():
        from flask import session
        session.update(user="x", role="admin", org=A.DEFAULT_ORG)
        assert A._ship_carrier_ids(force=True) == ["se-1"]


@pytest.mark.xfail(strict=True, reason="SEC-5 residual: a carrier preference that was stored with the old id "
                   "(the account number) is echoed back in `preferred` when the provider is ShipStation")
def test_qa_old_id_stored_as_preference_is_not_echoed(appmod, carrier, owner_pref, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "UPS_ENABLED", False)
    monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    _setting(A, A.DEFAULT_ORG, "ship_carrier_ids", json.dumps([FAKE_ACCT]), write=True)
    r = _client(A, A.DEFAULT_ORG, "cs").get("/api/ship/carriers")
    assert FAKE_ACCT not in r.get_data(as_text=True)


@pytest.mark.xfail(strict=True, reason="SEC-5 residual: the buy routes return carrier error text unredacted "
                   "(_carrier_err is applied to list/rates only)")
def test_qa_buy_routes_do_not_echo_the_account_number_in_carrier_errors(appmod, ups_full, owner_pref, monkeypatch):
    A = appmod
    c = _client(A, A.DEFAULT_ORG, "cs")
    d = c.post("/api/label/rates", headers=c.csrf, json=RATES_BODY).get_json()

    def rejected(*a, **k):
        raise A.CarrierRejected("UPS: 120100: Missing or invalid shipper number %s" % FAKE_ACCT)
    monkeypatch.setattr(A, "_ups", rejected)
    r = c.post("/api/label/buy", headers=c.csrf, json={"shipment_id": d["shipment_id"], "rate_id": d["rates"][0]["id"]})
    assert r.get_json()["ok"] is False
    assert FAKE_ACCT not in r.get_data(as_text=True)


# ───────────── 5. staging (the gate is false for the owner org as well) ─────────────

def test_qa_staging_refuses_before_any_transport_and_saves_nothing(appmod, ups_full, owner_pref, owner_ship_from, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "IS_STAGING", True)
    gid = _giveaway(A, A.DEFAULT_ORG)
    before = _setting(A, A.DEFAULT_ORG, "ship_carrier_ids")
    c = _client(A, A.DEFAULT_ORG, "admin")
    for name, r in _routes(c, gid):
        assert r.status_code == 403 and r.get_json()["error"] == A._NO_LABEL_MSG, (name, r.status_code)
    assert ups_full == []
    assert _setting(A, A.DEFAULT_ORG, "ship_carrier_ids") == before
