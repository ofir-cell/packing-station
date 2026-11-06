"""Cycle-27 (v2): WARP freight integration against the WARP API v2 (apikey header,
stg/gw.wearewarp.com, /freights/quote|booking|tracking). The outbound HTTP is monkeypatched
(no network in tests). We verify key storage/masking + mode→base, the quote/book/track
proxies build the v2 request shapes, a booking persists, and freight cost is admin-only."""
import json


def _admin(client, A, role="admin"):
    uname = role + "_u"
    with A.update_json(A.USERS_FILE) as users:
        u = dict(users.get(uname) or {})
        u.update({"password": u.get("password", "x"), "role": role, "name": role.title(), "org": A.DEFAULT_ORG})
        users[uname] = u
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=A.DEFAULT_ORG, name=role.title())
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _capture(A, monkeypatch, result):
    """Patch _warp_api to record the last call and return a canned (ok, status, data)."""
    calls = {}
    def fake(method, path, body=None):
        calls["method"] = method; calls["path"] = path; calls["body"] = body
        return result
    monkeypatch.setattr(A, "_warp_api", fake)
    return calls


def test_settings_mode_picks_base_and_masks(appmod, client):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "stgKEY1234567890", "live_key": "prodKEY1234567890", "mode": "test"}, headers=hdr)
    g = client.get("/api/warp/settings", headers=hdr).get_json()
    assert g["mode"] == "test" and g["base"] == "https://stg.wearewarp.com/api/v1" and g["configured"]
    assert "…" in g["test_mask"] and "stgKEY1234567890" not in json.dumps(g)
    client.post("/api/warp/settings", json={"mode": "live"}, headers=hdr)
    assert client.get("/api/warp/settings", headers=hdr).get_json()["base"] == "https://gw.wearewarp.com/api/v1"


def test_quote_builds_v2_shape(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "k", "mode": "test"}, headers=hdr)
    calls = _capture(A, monkeypatch, (True, 200, {"quote_id": "q_1", "price": {"amount": 694.59}, "transit_time": 5}))
    r = client.post("/api/warp/quote", json={"origin_zip": "90001", "destination_zip": "10001", "pickup_date": "2026-12-01",
                                             "pallets": 2, "weight_lbs_per_pallet": 500, "length_in": 48, "width_in": 40, "height_in": 48,
                                             "commodity": "cosmetics"}, headers=hdr).get_json()
    assert r["ok"] and r["quote"]["quote_id"] == "q_1" and r["quote"]["price_usd"] == 694.59 and r["quote"]["transit_days"] == 5
    # request used the v2 endpoint + camelCase body
    assert calls["path"] == "/freights/quote"
    b = calls["body"]
    assert b["pickupDate"] == "2026-12-01" and b["pickupInfo"]["zipcode"] == "90001" and b["deliveryInfo"]["zipcode"] == "10001"
    it = b["listItems"][0]
    assert it["quantity"] == 2 and it["totalWeight"] == 1000 and it["sizeUnit"] == "IN" and it["weightUnit"] == "lbs"


def test_book_builds_v2_shape_and_persists(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "k", "mode": "test"}, headers=hdr)
    calls = _capture(A, monkeypatch, (True, 200, {"shipmentId": "01X", "shipmentNumber": "S-00524-2635", "trackingNumber": "S-00524-2635", "orderNumber": "P-1"}))
    quote_inputs = {"origin_zip": "90001", "destination_zip": "10001", "pickup_date": "2026-12-01",
                    "pallets": 2, "weight_lbs_per_pallet": 500, "length_in": 48, "width_in": 40, "height_in": 48, "commodity": "cosmetics"}
    r = client.post("/api/warp/book", json={"quote_id": "q_1", "price_usd": 694.59, "reference": "PO-9", "quote": quote_inputs,
                                            "pickup": {"company": "ACME", "contact": "Dana", "phone": "2135550100", "street": "1 Main", "city": "LA", "state": "CA", "zipcode": "90001"},
                                            "delivery": {"company": "WH", "phone": "2125550200", "street": "2 Broadway", "city": "NY", "state": "NY", "zipcode": "10001"}},
                    headers=hdr).get_json()
    assert r["ok"] and r["booking"]["shipmentNumber"] == "S-00524-2635"
    b = calls["body"]
    assert calls["path"] == "/freights/booking" and b["quoteId"] == "q_1"
    assert b["pickupInfo"]["contactPhone"] == "2135550100" and b["pickupInfo"]["address"]["city"] == "LA"
    assert b["pickupInfo"]["windowTime"]["from"].startswith("2026-12-01")      # auto pickup window
    assert b["deliveryInfo"]["address"]["zipcode"] == "10001"
    assert b["listItems"][0]["totalWeight"] == 1000                            # matches the quote items
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT * FROM warp_shipments WHERE quote_id='q_1'").fetchone(); c.close()
    assert row["shipment_number"] == "S-00524-2635" and row["price_usd"] == 694.59


def test_book_requires_pickup_phone(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "k", "mode": "test"}, headers=hdr)
    _capture(A, monkeypatch, (True, 200, {}))
    r = client.post("/api/warp/book", json={"quote_id": "q_1", "quote": {"origin_zip": "1", "destination_zip": "2"},
                                            "pickup": {"zipcode": "1"}, "delivery": {"zipcode": "2"}}, headers=hdr).get_json()
    assert r["ok"] is False and "phone" in r["error"].lower()


def test_track_uses_tracking_numbers_array(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "k", "mode": "test"}, headers=hdr)
    calls = _capture(A, monkeypatch, (True, 200, [{"shipmentNumber": "S-1", "statusInfo": {"status": "booked"}}]))
    r = client.get("/api/warp/track?booking_id=S-1", headers=hdr).get_json()
    assert r["ok"] and r["tracking"]["status"] == "booked"
    assert calls["path"] == "/freights/tracking" and calls["body"] == {"trackingNumbers": ["S-1"]}


def test_verify_hits_shipments(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "k", "mode": "test"}, headers=hdr)
    calls = _capture(A, monkeypatch, (True, 200, []))
    r = client.post("/api/warp/verify", headers=hdr).get_json()
    assert r["ok"] and calls["method"] == "GET" and calls["path"] == "/freights/shipments"


def test_freight_cost_admin_only(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "k", "mode": "test"}, headers=hdr)
    _capture(A, monkeypatch, (True, 200, {"shipmentId": "z", "shipmentNumber": "S-9", "trackingNumber": "S-9"}))
    client.post("/api/warp/book", json={"quote_id": "q9", "price_usd": 400, "quote": {"origin_zip": "1", "destination_zip": "2", "pallets": 1},
                                        "pickup": {"phone": "1", "zipcode": "1"}, "delivery": {"zipcode": "2"}}, headers=hdr)
    lst_cs = client.get("/api/warp/shipments", headers=_admin(client, A, role="cs")).get_json()
    assert all("price_usd" not in s for s in lst_cs["shipments"])
    lst_ad = client.get("/api/warp/shipments", headers=_admin(client, A)).get_json()
    assert any(s.get("price_usd") == 400 for s in lst_ad["shipments"])


def test_book_is_admin_only(appmod, client):
    A = appmod
    assert client.post("/api/warp/book", json={"quote_id": "x"}, headers=_admin(client, A, role="cs")).status_code == 403
