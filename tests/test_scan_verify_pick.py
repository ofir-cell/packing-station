"""Scan-to-verify picking: while an order is open the picker scans each PRODUCT; it is
checked against the product linked to that sticker during the live (Live Match / Live
Scan). Tapping an item and Mark as picked stay available as the bypass, and every item
records how it was checked off (scan / tap / bypass) so the pilot can be measured.
"""
import uuid

import pytest


def _as(client, A, user="worker1", role="worker"):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


@pytest.fixture
def order(appmod):
    """One TikTok-style order in a fresh show: sticker #940 from PART 1 and #212 from
    PART 1. #940 is linked to product A; PART 2 #940 (another buyer's item) is linked to
    product B; #212 is not linked yet. The show is marked cleaned out so picking is open."""
    A = appmod
    t = uuid.uuid4().hex[:6].upper()
    label, sid, trk = "Verify Live " + t, "VS" + t, "9400555" + t + "01"
    a, b = "A" + t, "B" + t
    c = A.sdb(A.DEFAULT_ORG)
    A._cleanout_ensure(c)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_label,platform) VALUES(?,?,'pending',?,'tiktok')", (sid, trk, label))
    for st in ("940", "212"):
        c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,1)",
                  (sid, "O" + sid, st, label + " PART 1"))
    c.execute("INSERT INTO products(sku,name,barcode,image_url) VALUES(?,?,?,?)", (a, "Rare Blush Joy", "BC" + a, "/product-image/" + a))
    c.execute("INSERT INTO products(sku,name,barcode) VALUES(?,?,?)", (b, "Glow Serum", "BC" + b))
    c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,1,?)", (label, "940", a))
    c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,2,?)", (label, "940", b))
    c.commit(); c.close()
    A._show_mark_cleanout(A.sdb(A.DEFAULT_ORG), label, "test")
    return {"label": label, "sid": sid, "trk": trk, "a": a, "b": b, "bc_a": "BC" + a, "bc_b": "BC" + b}


def _items(A, sid):
    c = A.sdb(A.DEFAULT_ORG)
    r = {x["sku"]: dict(x) for x in c.execute("SELECT * FROM shipment_items WHERE shipment_id=?", (sid,))}
    c.close(); return r


def _scan(client, hdr, sid, code):
    return client.post("/api/pick/%s/scan" % sid, headers=hdr, json={"code": code}).get_json()


def test_pick_screen_shows_the_linked_product(appmod, client, order):
    A = appmod; _as(client, A)
    items = {i["sku"]: i for i in client.get("/api/pick/" + order["sid"]).get_json()["items"]}
    assert items["940"]["product"]["name"] == "Rare Blush Joy"
    assert items["940"]["product"]["image_url"]
    assert items["212"]["product"] is None                       # not linked: tap it


def test_right_product_checks_the_item_off(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    d = _scan(client, hdr, order["sid"], order["bc_a"])
    assert d["ok"] is True and d["sticker"] == "940"
    it = _items(A, order["sid"])["940"]
    assert it["picked"] == 1 and it["pick_method"] == "scan"
    assert _scan(client, hdr, order["sid"], order["bc_a"]).get("already") is True


def test_part2_product_is_wrong_for_a_part1_sticker(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    d = _scan(client, hdr, order["sid"], order["bc_b"])             # same #940, other PART
    assert d["ok"] is False and d["wrong"] is True
    assert d["scanned"]["name"] == "Glow Serum"
    assert [(x["sticker"], x["name"]) for x in d["expected"]] == [("940", "Rare Blush Joy")]
    assert _items(A, order["sid"])["940"]["picked"] == 0           # nothing checked off


def test_unknown_barcode_is_wrong_not_silently_accepted(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    d = _scan(client, hdr, order["sid"], "000NOTAPRODUCT")
    assert d["wrong"] is True and "Unknown barcode" in d["scanned"]["name"]


def test_scanning_a_label_says_scan_the_product(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    d = _scan(client, hdr, order["sid"], order["trk"])
    assert d["label"] is True and d["same_order"] is True
    assert all(i["picked"] == 0 for i in _items(A, order["sid"]).values())


def test_order_with_no_linked_products_falls_back_to_tap(appmod, client):
    A = appmod; hdr = _as(client, A)
    t = uuid.uuid4().hex[:6].upper()
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,import_label,platform) VALUES(?,'pending',?,'whatnot')", ("NB" + t, "NoLinks " + t))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,'7','Lip',1)", ("NB" + t, "O" + t))
    c.execute("INSERT INTO products(sku,name,barcode) VALUES(?,?,?)", ("P" + t, "Some Product", "BCP" + t))
    c.commit(); c.close()
    d = _scan(client, hdr, "NB" + t, "BCP" + t)
    assert d["ok"] is False and d["no_binding"] is True


def test_tap_and_mark_as_picked_still_work_and_are_recorded(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    _scan(client, hdr, order["sid"], order["bc_a"])                 # #940 by scan
    d = client.post("/api/pick/complete/" + order["sid"], headers=hdr).get_json()
    assert d["ok"] is True                                          # bypass never blocked
    items = _items(A, order["sid"])
    assert items["940"]["pick_method"] == "scan"
    assert items["212"]["pick_method"] == "bypass" and items["212"]["picked"] == 1


def test_tap_records_tap_and_untap_clears_it(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    iid = _items(A, order["sid"])["212"]["id"]
    assert client.post("/api/pick/item/%d/toggle" % iid, headers=hdr).get_json()["picked"] == 1
    assert _items(A, order["sid"])["212"]["pick_method"] == "tap"
    client.post("/api/pick/item/%d/toggle" % iid, headers=hdr)
    assert _items(A, order["sid"])["212"]["pick_method"] is None


def test_no_scanning_into_cancelled_or_picked_orders(appmod, client, order):
    A = appmod; hdr = _as(client, A)
    client.post("/api/pick/complete/" + order["sid"], headers=hdr)
    assert _scan(client, hdr, order["sid"], order["bc_a"])["ok"] is False
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", (order["sid"],)); c.commit(); c.close()
    assert "cancelled" in _scan(client, hdr, order["sid"], order["bc_a"])["error"]


def test_scan_requires_login(appmod, client, order):
    client.set_cookie("csrf_token", "tok")                         # valid CSRF, but no session
    r = client.post("/api/pick/%s/scan" % order["sid"], headers={"X-CSRF-Token": "tok"}, json={"code": "x"})
    assert r.status_code in (302, 401)
