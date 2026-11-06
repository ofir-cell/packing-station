"""Cycle-27: WARP freight (inbound pallet / LTL) integration. The outbound HTTP to WARP
is monkeypatched (no network in tests); we verify key storage/masking, the quote/book/track
proxies, that a booking is persisted, and that freight cost is admin-only."""
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


def _fake_warp(monkeypatch, A, handler):
    monkeypatch.setattr(A, "_warp_api", handler)


def test_settings_save_and_mask(appmod, client):
    A = appmod; hdr = _admin(client, A)
    r = client.post("/api/warp/settings", json={"test_key": "wak_test_abcdef1234567890", "mode": "test"}, headers=hdr).get_json()
    assert r["ok"]
    g = client.get("/api/warp/settings", headers=hdr).get_json()
    assert g["test_set"] and g["mode"] == "test" and g["configured"]
    assert "…" in g["test_mask"] and "wak_test_abcdef1234567890" not in json.dumps(g)   # key never returned in full


def test_quote_proxies_and_needs_fields(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "wak_test_x", "mode": "test"}, headers=hdr)
    # missing fields rejected before any call
    bad = client.post("/api/warp/quote", json={"origin_zip": "90001"}, headers=hdr).get_json()
    assert bad["ok"] is False
    _fake_warp(monkeypatch, A, lambda m, p, body=None, use_key=True: (True, 200, {"quote_id": "wq_1", "price_usd": 694.59, "transit_days": 5}))
    ok = client.post("/api/warp/quote", json={"origin_zip": "90001", "destination_zip": "10001",
                                              "pickup_date": "2026-11-27", "pallets": 2, "weight_lbs_per_pallet": 500,
                                              "length_in": 48, "width_in": 40, "height_in": 48}, headers=hdr).get_json()
    assert ok["ok"] and ok["quote"]["quote_id"] == "wq_1" and ok["quote"]["price_usd"] == 694.59


def test_book_persists_shipment(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "wak_test_x", "mode": "test"}, headers=hdr)
    _fake_warp(monkeypatch, A, lambda m, p, body=None, use_key=True: (True, 200, {
        "booked": True, "shipment_id": "01ABC", "shipment_number": "S-199806-2617", "tracking_number": "S-199806-2617"}))
    r = client.post("/api/warp/book", json={"quote_id": "wq_1", "reference": "PO-5", "price_usd": 694.59,
                                            "pallets": 2, "pickup_date": "2026-11-27", "delivery_date": "2026-12-02",
                                            "pickup": {"zipCode": "90001"}, "delivery": {"zipCode": "10001"}},
                    headers=hdr).get_json()
    assert r["ok"] and r["booking"]["shipment_number"] == "S-199806-2617"
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT * FROM warp_shipments WHERE quote_id='wq_1'").fetchone(); c.close()
    assert row and row["shipment_number"] == "S-199806-2617" and row["price_usd"] == 694.59 and row["status"] == "booked"


def test_track_proxies(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "wak_test_x", "mode": "test"}, headers=hdr)
    _fake_warp(monkeypatch, A, lambda m, p, body=None, use_key=True: (True, 200, {"status": "booked", "price_usd": 694.59}))
    r = client.get("/api/warp/track?booking_id=S-199806-2617", headers=hdr).get_json()
    assert r["ok"] and r["tracking"]["status"] == "booked"


def test_freight_cost_admin_only(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    client.post("/api/warp/settings", json={"test_key": "wak_test_x", "mode": "test"}, headers=hdr)
    _fake_warp(monkeypatch, A, lambda m, p, body=None, use_key=True: (True, 200, {"shipment_id": "z", "shipment_number": "S-1", "tracking_number": "S-1"}))
    client.post("/api/warp/book", json={"quote_id": "wq_9", "price_usd": 400, "pickup": {"zipCode": "1"}, "delivery": {"zipCode": "2"}}, headers=hdr)
    # cs sees shipments but NOT the price
    hcs = _admin(client, A, role="cs")
    lst = client.get("/api/warp/shipments", headers=hcs).get_json()
    assert lst["ok"] and all("price_usd" not in s for s in lst["shipments"])
    # admin sees it
    lst2 = client.get("/api/warp/shipments", headers=_admin(client, A)).get_json()
    assert any(s.get("price_usd") == 400 for s in lst2["shipments"])


def test_book_is_admin_only(appmod, client):
    A = appmod
    hcs = _admin(client, A, role="cs")
    assert client.post("/api/warp/book", json={"quote_id": "x"}, headers=hcs).status_code == 403
