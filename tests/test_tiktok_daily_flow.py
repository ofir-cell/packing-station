"""TikTok daily flow: from an order on TikTok to a packed, recorded box.

  A. An order is fetched from the TikTok API and becomes a package in the right show
  B. During the live the assistant scans the product for each sold sticker (Live Match)
  C. Picking ("pull"): the table-cleanout gate, the pick queue, claiming a box,
     cancellations that must be pulled off the table, issues
  D. Packing takes stock off exactly once, and the whole day end to end

The TikTok API is replaced by FakeTikTok and the online barcode lookup is switched off,
so nothing leaves the machine. Added after the Oct 29 2026 review found no tests for
order ingest, Live Match or the TikTok picking path.
"""
import io, time, uuid

import pytest

EBML = b"\x1a\x45\xdf\xa3"
SHOP = "SHOP-DAILY"


# ── fake TikTok ───────────────────────────────────────────────────────────────
class FakeTikTok:
    """Answers the order-detail call (/order/<ver>/orders?ids=...) from a dict."""
    def __init__(self):
        self.orders, self.calls = {}, []

    def add(self, order):
        self.orders[order["id"]] = order
        return order

    def request(self, method, url, params=None, **kw):
        self.calls.append(url)
        if "/orders" in url and params and params.get("ids") in self.orders:
            return {"code": 0, "data": {"orders": [self.orders[params["ids"]]]}}
        return {"code": 0, "data": {}}


@pytest.fixture
def tiktok(appmod, monkeypatch):
    A = appmod
    fake = FakeTikTok()
    monkeypatch.setattr(A, "_tt_request", fake.request)
    monkeypatch.setattr(A, "_tt_valid_token", lambda org, shop: {"access_token": "t", "shop_cipher": "c"})
    monkeypatch.setattr(A, "_tt_ensure_cipher", lambda org, shop, tok: tok)
    monkeypatch.setattr(A, "_barcode_lookup_online", lambda code: None)   # never call the internet
    return fake


@pytest.fixture
def r2(appmod, monkeypatch):
    class R2:
        def __init__(self): self.objects = {}
        def put_object(self, Bucket, Key, Body, **kw): self.objects[Key] = bytes(Body)
        def upload_fileobj(self, f, b, key, ExtraArgs=None): self.objects[key] = f.read()
        def generate_presigned_url(self, op, Params=None, ExpiresIn=None): return "https://r2.example/" + Params["Key"]
    fake = R2()
    monkeypatch.setattr(appmod, "r2", fake)
    monkeypatch.setattr(appmod, "R2_BUCKET", "test-bucket")
    return fake


def _order(oid, pkg, room, items, status="AWAITING_SHIPMENT", buyer="buyer", tracking=None, created=None):
    """A TikTok order as the API returns it. items: [(sticker, product_name, price)]."""
    return {
        "id": oid, "status": status, "buyer_nickname": buyer,
        "create_time": int(created or time.time()),
        "tracking_number": tracking or ("9400" + pkg[-10:]),
        "packages": [{"id": pkg}],
        "recipient_address": {"full_address": "1 Main St, Davie, FL 33314", "postal_code": "33314", "name": buyer.title()},
        "line_items": [{"id": "L%d" % i, "seller_sku": st, "sku_id": st, "product_name": nm,
                        "sale_price": str(price), "package_id": pkg, "live_room_id": room}
                       for i, (st, nm, price) in enumerate(items)],
    }


def _ingest(A, oid):
    A._tt_ingest_order(A.DEFAULT_ORG, SHOP, oid)


def _ship(A, sid):
    c = A.sdb(A.DEFAULT_ORG)
    s = c.execute("SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    items = [dict(r) for r in c.execute("SELECT * FROM shipment_items WHERE shipment_id=? ORDER BY id", (sid,))]
    c.close()
    return (dict(s) if s else None), items


def _login(client, A, user, role):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _live(A, tiktok):
    """One TikTok LIVE: PART 1 and PART 2 both sell a sticker #940 (different items),
    and buyer C wins two auctions that TikTok ships in ONE package."""
    # The table-cleanout gate's one-time launch migration marks every EXISTING show as
    # cleaned (prod ran it long ago). Run it before creating this live, as in production.
    c = A.sdb(A.DEFAULT_ORG); A._cleanout_ensure(c); c.close()
    t = uuid.uuid4().hex[:6].upper()
    room = "ROOM-" + t
    lst = "Peach Live " + t          # shows are named by listing + start time; keep each test's live distinct
    o = {
        "a":  tiktok.add(_order("OA" + t, "PKA" + t, room, [("940", lst + " PART 1", 9)], buyer="amy")),
        "b":  tiktok.add(_order("OB" + t, "PKB" + t, room, [("940", lst + " PART 2", 12)], buyer="bob")),
        "c1": tiktok.add(_order("OC1" + t, "PKC" + t, room, [("101", lst + " PART 1", 5)], buyer="cat")),
        "c2": tiktok.add(_order("OC2" + t, "PKC" + t, room, [("102", lst + " PART 1", 7)], buyer="cat")),
    }
    for k in ("a", "b", "c1", "c2"):
        _ingest(A, o[k]["id"])
    label = _ship(A, "PKA" + t)[0]["import_label"]
    return t, room, label, o


# ── A. order pull from TikTok → package in the show ───────────────────────────
def test_order_is_fetched_and_becomes_a_package(appmod, tiktok):
    A = appmod
    t = uuid.uuid4().hex[:6].upper()
    tiktok.add(_order("O" + t, "PK" + t, "ROOM-" + t, [("55", "Peach Live PART 1", 8.5)], buyer="dana"))
    _ingest(A, "O" + t)
    assert any("/orders" in u for u in tiktok.calls)
    ship, items = _ship(A, "PK" + t)
    assert ship and ship["platform"] == "tiktok" and ship["status"] == "pending"
    assert ship["import_batch"] == "tiktok-api" and ship["import_label"]
    assert [(i["sku"], i["quantity"]) for i in items] == [("55", 1)]
    assert round(items[0]["revenue"], 2) == 8.5
    c = A.pdb()
    assert c.execute("SELECT 1 FROM tiktok_orders WHERE order_id=?", ("O" + t,)).fetchone()   # raw order kept
    c.close()


def test_whole_live_lands_in_one_show(appmod, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    labels = {_ship(A, sid)[0]["import_label"] for sid in ("PKA" + t, "PKB" + t, "PKC" + t)}
    assert labels == {label}                         # PART 1 and PART 2 of one live = one show


def test_different_live_is_a_different_show(appmod, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    t2 = uuid.uuid4().hex[:6].upper()
    tiktok.add(_order("OX" + t2, "PKX" + t2, "ROOM-OTHER-" + t2, [("1", "Hera Live PART 1", 4)]))
    _ingest(A, "OX" + t2)
    assert _ship(A, "PKX" + t2)[0]["import_label"] != label


def test_two_orders_in_one_package_keep_both_products(appmod, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    ship, items = _ship(A, "PKC" + t)
    assert sorted(i["sku"] for i in items) == ["101", "102"]      # regression: Oct 22 fix
    _ingest(A, o["c1"]["id"])                                      # a later update to one order
    assert sorted(i["sku"] for i in _ship(A, "PKC" + t)[1]) == ["101", "102"]


def test_unpaid_order_waits_until_paid(appmod, tiktok):
    A = appmod
    t = uuid.uuid4().hex[:6].upper()
    o = tiktok.add(_order("OU" + t, "PKU" + t, "ROOM-" + t, [("7", "Peach Live PART 1", 3)], status="UNPAID"))
    _ingest(A, o["id"])
    assert _ship(A, "PKU" + t)[0] is None                         # not in the pick queue yet
    o["status"] = "AWAITING_SHIPMENT"
    _ingest(A, o["id"])
    assert _ship(A, "PKU" + t)[0]["status"] == "pending"


def test_paused_sync_parks_orders_without_building_packages(appmod, tiktok, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_tt_is_paused", lambda org: True)
    t = uuid.uuid4().hex[:6].upper()
    tiktok.add(_order("OP" + t, "PKP" + t, "ROOM-" + t, [("8", "Peach Live PART 1", 3)]))
    _ingest(A, "OP" + t)
    assert _ship(A, "PKP" + t)[0] is None
    c = A.pdb()
    assert c.execute("SELECT 1 FROM tiktok_orders WHERE order_id=?", ("OP" + t,)).fetchone()
    c.close()


# ── B. Live Match: assistant scans the product for each sold sticker ──────────
def test_match_queue_keeps_part1_and_part2_stickers_apart(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    _login(client, A, "worker3", "worker")
    d = client.get("/api/live/match-queue", query_string={"show": label}).get_json()
    keys = {(w["sticker"], w["part"]) for w in d["waiting"]}
    assert ("940", 1) in keys and ("940", 2) in keys               # same number, two items


def test_scanning_unknown_barcode_creates_product_and_links_sticker(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker3", "worker")
    code = "0" + str(uuid.uuid4().int)[:11]
    r = client.post("/api/live/match", headers=hdr, json={"show": label, "sticker": "940", "part": 1, "code": code})
    d = r.get_json()
    assert d["ok"] is True and d["auto_created"] is True
    c = A.sdb(A.DEFAULT_ORG)
    p = c.execute("SELECT * FROM products WHERE barcode=?", (code,)).fetchone()
    m = c.execute("SELECT product_sku FROM show_product_map WHERE import_label=? AND sticker_sku='940' AND part=1", (label,)).fetchone()
    c.close()
    assert p["category"] == "Needs review"                        # flagged for the after-live cleanup
    assert m["product_sku"] == p["sku"]
    q = client.get("/api/live/match-queue", query_string={"show": label}).get_json()
    keys = {(w["sticker"], w["part"]) for w in q["waiting"]}
    assert ("940", 1) not in keys and ("940", 2) in keys          # only PART 1 #940 is done


# ── C. picking ("pull") ───────────────────────────────────────────────────────
def test_new_tiktok_show_needs_table_cleanout_before_picking(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    assert client.get("/api/pick/PKA" + t).get_json()["cleanout_required"] is True
    assert client.post("/api/show/cleanout", headers=hdr, json={"label": label}).get_json()["ok"]
    assert client.get("/api/pick/PKA" + t).get_json()["cleanout_required"] is False


def test_pick_queue_lists_the_show_and_a_box_is_claimed_once(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    client.post("/api/show/cleanout", headers=hdr, json={"label": label})
    q = client.get("/api/pick/queue", query_string={"show": label}).get_json()
    assert {r["shipment_id"] for r in q} == {"PKA" + t, "PKB" + t, "PKC" + t}
    assert client.post("/api/pick/complete/PKC" + t, headers=hdr).get_json()["ok"]
    ship, items = _ship(A, "PKC" + t)
    assert ship["status"] == "picked" and ship["picked_by"] == "worker1"
    assert all(i["picked"] == 1 for i in items)                   # both products pulled
    hdr2 = _login(client, A, "worker2", "worker")
    d = client.post("/api/pick/complete/PKC" + t, headers=hdr2).get_json()
    assert d["ok"] is False and d["already_picked"] and d["picked_by"] == "worker1"
    q = client.get("/api/pick/queue", query_string={"show": label}).get_json()
    assert "PKC" + t not in {r["shipment_id"] for r in q}


def test_tiktok_resync_after_pick_keeps_floor_progress(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    client.post("/api/show/cleanout", headers=hdr, json={"label": label})
    client.post("/api/pick/complete/PKA" + t, headers=hdr)
    _ingest(A, o["a"]["id"])                                       # the 5s live sweep re-reads it
    ship, items = _ship(A, "PKA" + t)
    assert ship["status"] == "picked" and items[0]["picked"] == 1


def test_cancel_after_pick_blocks_show_until_item_pulled_off_table(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    client.post("/api/show/cleanout", headers=hdr, json={"label": label})
    client.post("/api/pick/complete/PKA" + t, headers=hdr)        # #940 PART 1 is on the table
    o["a"]["status"] = "CANCELLED"
    _ingest(A, o["a"]["id"])                                       # buyer cancels after the pull
    assert _ship(A, "PKA" + t)[0]["status"] == "cancelled"
    assert client.get("/api/pick/PKB" + t).get_json()["cleanup_blocked"] is True
    g = client.get("/api/cleanup/" + label).get_json()
    assert [(x["sku"], x["total_qty"]) for x in g["groups"]] == [("940", 1)]
    part = g["groups"][0]["part"]
    assert client.post("/api/cleanup/" + label + "/mark", headers=hdr,
                       json={"sku": "940", "part": part, "removed": True}).get_json()["is_clean"]
    assert client.get("/api/pick/PKB" + t).get_json()["cleanup_blocked"] is False


def test_cancel_before_pick_does_not_block_the_floor(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    client.post("/api/show/cleanout", headers=hdr, json={"label": label})
    o["b"]["status"] = "CANCELLED"
    _ingest(A, o["b"]["id"])                                       # never pulled → nothing on the table
    assert client.get("/api/pick/PKA" + t).get_json()["cleanup_blocked"] is False
    d = client.post("/api/pick/complete/PKB" + t, headers=hdr).get_json()
    assert d["ok"] is False                                        # and it can't be picked


def test_issue_leaves_queue_and_retry_brings_it_back(appmod, client, tiktok):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    client.post("/api/show/cleanout", headers=hdr, json={"label": label})
    assert client.post("/api/pick/issue/PKB" + t, headers=hdr, json={"reason": "item missing from shelf"}).get_json()["ok"]
    q = {r["shipment_id"] for r in client.get("/api/pick/queue", query_string={"show": label}).get_json()}
    assert "PKB" + t not in q
    hdr = _login(client, A, "cs1", "cs")
    assert client.post("/api/pick/resolve/PKB" + t, headers=hdr, json={"action": "retry"}).get_json()["ok"]
    _login(client, A, "worker1", "worker")
    q = {r["shipment_id"] for r in client.get("/api/pick/queue", query_string={"show": label}).get_json()}
    assert "PKB" + t in q


# ── D. pack + stock, and the whole day ────────────────────────────────────────
def _on_hand(A, sku):
    c = A.sdb(A.DEFAULT_ORG); v = c.execute("SELECT on_hand FROM products WHERE sku=?", (sku,)).fetchone()[0]; c.close()
    return v


def _set_on_hand(A, sku, n):
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE products SET on_hand=? WHERE sku=?", (n, sku)); c.commit(); c.close()


def test_full_tiktok_day_order_to_video(appmod, client, tiktok, r2):
    A = appmod
    # during the live: orders arrive from TikTok
    t, room, label, o = _live(A, tiktok)
    # the assistant scans the real product for sticker #940 PART 1
    hdr = _login(client, A, "worker3", "worker")
    code = "0" + str(uuid.uuid4().int)[:11]
    assert client.post("/api/live/match", headers=hdr,
                       json={"show": label, "sticker": "940", "part": 1, "code": code}).get_json()["ok"]
    _set_on_hand(A, code, 10)                                       # counted stock for that product
    # next morning: clean the table, pull the box
    hdr = _login(client, A, "worker1", "worker")
    assert client.post("/api/show/cleanout", headers=hdr, json={"label": label}).get_json()["ok"]
    assert client.post("/api/pick/complete/PKA" + t, headers=hdr).get_json()["ok"]
    # pack it on camera
    hdr = _login(client, A, "worker1", "worker")
    trk = _ship(A, "PKA" + t)[0]["tracking_code"]
    r = client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                    data={"tracking": trk, "station": "S1", "duration": "38",
                          "video": (io.BytesIO(EBML + b"box"), "v.webm")})
    assert r.get_json()["ok"] is True
    ship, items = _ship(A, "PKA" + t)
    assert ship["status"] == "packed"
    assert _on_hand(A, code) == 9                                   # one unit off, at pack time
    # a re-record of the same box (or a TikTok re-sync) never takes it off twice
    client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                data={"tracking": trk, "station": "S1", "duration": "20", "video": (io.BytesIO(EBML + b"again"), "v.webm")})
    _ingest(A, o["a"]["id"])
    assert _on_hand(A, code) == 9 and _ship(A, "PKA" + t)[0]["status"] == "packed"
    # CS finds the video for that box
    _login(client, A, "cs1", "cs")
    d = client.get("/api/search/" + trk).get_json()
    assert d["videos"] and d["videos"][0]["station"] == "S1"


def test_sticker_matched_after_packing_still_takes_stock_once(appmod, client, tiktok, r2):
    A = appmod
    t, room, label, o = _live(A, tiktok)
    hdr = _login(client, A, "worker1", "worker")
    client.post("/api/show/cleanout", headers=hdr, json={"label": label})
    client.post("/api/pick/complete/PKB" + t, headers=hdr)
    hdr = _login(client, A, "worker1", "worker")
    trk = _ship(A, "PKB" + t)[0]["tracking_code"]
    client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                data={"tracking": trk, "station": "S2", "video": (io.BytesIO(EBML + b"b"), "v.webm")})
    # the assistant only gets to #940 PART 2 after the box was packed
    code = "0" + str(uuid.uuid4().int)[:11]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,5,0)", (code, "Blush", code))
    c.commit(); c.close()
    hdr = _login(client, A, "worker3", "worker")
    assert client.post("/api/live/match", headers=hdr,
                       json={"show": label, "sticker": "940", "part": 2, "code": code}).get_json()["ok"]
    assert _on_hand(A, code) == 4
    client.post("/api/live/match", headers=hdr, json={"show": label, "sticker": "940", "part": 2, "code": code})
    assert _on_hand(A, code) == 4                                   # re-scan doesn't double count


# ── schema: a brand-new tenant must get every column on day one ───────────────
def test_new_tenant_schema_matches_after_restart(appmod):
    """sdb_init runs its ALTER TABLE upgrades before some CREATE TABLEs, so a column that
    exists only as an ALTER was missing on a brand-new tenant until the next restart.
    products.retail_price was: a live barcode scan then failed to auto-create the product
    ('table products has no column named retail_price')."""
    import sqlite3
    A = appmod
    org = "fresh" + uuid.uuid4().hex[:6]
    import os
    os.makedirs(os.path.dirname(A.shipments_db_path(org)), exist_ok=True)

    def cols():
        c = sqlite3.connect(A.shipments_db_path(org)); out = {}
        for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            out[t] = {r[1] for r in c.execute("PRAGMA table_info(%s)" % t)}
        c.close(); return out
    A.sdb_init(org); first = cols()
    A.sdb_init(org); second = cols()
    missing = {t: sorted(second[t] - first.get(t, set())) for t in second if second[t] - first.get(t, set())}
    assert missing == {}, "columns only added on a restart: %r" % missing
