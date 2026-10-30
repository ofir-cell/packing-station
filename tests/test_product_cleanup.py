"""After-Live Cleanup: products scanned during a live that still need a real name and
prices, listed per show, fixed in place.

The online barcode lookup is switched off so an unknown barcode always becomes the
"New product • <barcode>" stub that this screen exists to clean up.
"""
import uuid

import pytest


@pytest.fixture(autouse=True)
def offline_barcodes(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "_barcode_lookup_online", lambda code: None)


def _as(client, A, user, role):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _show(A, n_sold=3, price=11.0):
    """A show whose orders sold sticker #77 in PART 1 n_sold times."""
    tag = uuid.uuid4().hex[:6].upper()
    label = "Cleanup Live " + tag
    c = A.sdb(A.DEFAULT_ORG)
    for i in range(n_sold):
        sid = "CL%s-%d" % (tag, i)
        c.execute("INSERT INTO shipments(shipment_id,status,import_label,platform) VALUES(?,'pending',?,'tiktok')", (sid, label))
        c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue)
                     VALUES(?,?,'77',?,1,?)""", (sid, "O" + sid, label + " PART 1", price))
    c.commit(); c.close()
    return label


def _barcode():
    return "0" + str(uuid.uuid4().int)[:11]


def _match(client, hdr, label, sticker, part, code):
    return client.post("/api/live/match", headers=hdr,
                       json={"show": label, "sticker": sticker, "part": part, "code": code}).get_json()


def _detail(client, label):
    return client.get("/api/product-cleanup", query_string={"show": label}).get_json()


def test_scanned_unknown_product_shows_up_with_what_it_needs(appmod, client):
    A = appmod
    label, code = _show(A), _barcode()
    hdr = _as(client, A, "admin", "admin")
    assert _match(client, hdr, label, "77", 1, code)["ok"]
    d = _detail(client, label)
    assert d["ok"] and d["total"] == 1 and d["todo"] == 1
    it = d["items"][0]
    assert it["barcode"] == code and it["placeholder_name"] is True
    assert set(it["gaps"]) == {"name", "review", "target_price", "cost"}
    assert it["stickers"] == ["P1 #77"]
    assert it["units"] == 3 and it["avg_sold"] == 11.0          # helps set the target price
    shows = {s["label"]: s for s in client.get("/api/product-cleanup/shows").get_json()["shows"]}
    assert shows[label]["todo"] == 1 and shows[label]["products"] == 1


def test_saving_name_and_prices_marks_it_done_and_keeps_barcode(appmod, client):
    A = appmod
    label, code = _show(A), _barcode()
    hdr = _as(client, A, "admin", "admin")
    sku = _match(client, hdr, label, "77", 1, code)["product"]["sku"]
    # exactly what the screen sends on Save
    r = client.post("/api/products", headers=hdr, json={
        "sku": sku, "name": "Rare Beauty Blush - Joy", "barcode": code, "category": "",
        "target_price": "14", "retail_price": "23", "cost": "6.5"})
    assert r.get_json()["ok"]
    d = _detail(client, label)
    it = d["items"][0]
    assert it["done"] is True and it["gaps"] == [] and d["todo"] == 0
    assert it["barcode"] == code                                  # saving never drops the barcode
    assert it["name"] == "Rare Beauty Blush - Joy" and it["category"] == ""
    assert it["target_price"] == 14 and it["avg_cost"] == 6.5
    shows = {s["label"]: s for s in client.get("/api/product-cleanup/shows").get_json()["shows"]}
    assert shows[label]["todo"] == 0


def test_cs_sees_no_cost_and_is_not_asked_for_it(appmod, client):
    A = appmod
    label, code = _show(A), _barcode()
    hdr = _as(client, A, "admin", "admin")
    _match(client, hdr, label, "77", 1, code)
    _as(client, A, "cs1", "cs")
    d = _detail(client, label)
    it = d["items"][0]
    assert d["is_admin"] is False
    assert "avg_cost" not in it and "cost" not in it["gaps"]
    hdr = _as(client, A, "cs1", "cs")
    client.post("/api/products", headers=hdr, json={
        "sku": it["sku"], "name": "Serum", "barcode": code, "category": "Skincare",
        "target_price": "9", "retail_price": "0"})
    assert _detail(client, label)["items"][0]["done"] is True     # done for CS without cost


def test_live_scan_units_and_price_come_from_the_live(appmod, client):
    A = appmod
    label, code = _show(A, n_sold=0), _barcode()
    hdr = _as(client, A, "admin", "admin")
    for price in ("10", "14"):
        assert client.post("/api/live/scan", headers=hdr, json={
            "show": label, "sticker": "5", "part": 2, "code": code, "price": price}).get_json()["ok"]
    it = _detail(client, label)["items"][0]
    assert it["units"] == 2 and it["avg_sold"] == 12.0 and it["stickers"] == ["P2 #5"]


def test_known_complete_product_counts_as_done(appmod, client):
    A = appmod
    label, code = _show(A), _barcode()
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,category,target_price,avg_cost) VALUES(?,?,?,?,?,?)",
              (code, "Lip Oil", code, "Lips", 8, 3))
    c.commit(); c.close()
    hdr = _as(client, A, "admin", "admin")
    _match(client, hdr, label, "77", 1, code)
    d = _detail(client, label)
    assert d["items"][0]["done"] is True and d["todo"] == 0
    assert d["items"][0]["missing_photo"] is True                 # reported, but not blocking


def test_other_shows_products_are_not_listed(appmod, client):
    A = appmod
    a, b = _show(A), _show(A)
    hdr = _as(client, A, "admin", "admin")
    ca, cb = _barcode(), _barcode()
    _match(client, hdr, a, "77", 1, ca)
    _match(client, hdr, b, "77", 1, cb)
    assert [x["barcode"] for x in _detail(client, a)["items"]] == [ca]


def test_items_needing_work_come_first(appmod, client):
    A = appmod
    label = _show(A)
    hdr = _as(client, A, "admin", "admin")
    done_code, todo_code = _barcode(), _barcode()
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,target_price,avg_cost) VALUES(?,?,?,?,?)", (done_code, "Done", done_code, 5, 2))
    c.commit(); c.close()
    _match(client, hdr, label, "77", 1, done_code)
    _match(client, hdr, label, "78", 1, todo_code)
    items = _detail(client, label)["items"]
    assert [x["done"] for x in items] == [False, True]


def test_page_and_api_are_for_admin_and_cs_only(appmod, client):
    A = appmod
    _as(client, A, "cs1", "cs")
    r = client.get("/admin/product-cleanup")
    assert r.status_code == 200 and b"After-Live Cleanup" in r.data
    _as(client, A, "worker1", "worker")
    assert client.get("/admin/product-cleanup").status_code in (302, 401, 403)
    assert client.get("/api/product-cleanup/shows").status_code in (302, 401, 403)


def test_show_param_required(appmod, client):
    A = appmod
    _as(client, A, "admin", "admin")
    assert client.get("/api/product-cleanup").get_json()["ok"] is False
