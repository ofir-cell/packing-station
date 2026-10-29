"""Pack scan: between the label scan that starts the video and the box scan that stops it,
the packer scans each product he puts in the box. Ascending sticker order is a guide, any
order counts. Only stickers linked to a product (Live Match) are checked — packing never
links anything. Stopping early is allowed and the order is flagged with what's missing."""
import io, json, uuid

import pytest


def _as(client, A, user="worker1", role="worker"):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


@pytest.fixture
def box(appmod, monkeypatch):
    """Order with stickers 33, 41, 1, 17 (all single items). 1/17/33 are linked to products with
    barcodes; 41 was never linked. Another box in the same live has its own label."""
    A = appmod
    t = uuid.uuid4().hex[:6].upper()
    label = "Pack Live " + t
    trk = "9400" + str(uuid.uuid4().int)[:18]
    trk2 = "9400" + str(uuid.uuid4().int)[:18]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,buyer_name,status,import_label,import_batch) VALUES(?,?,?,?,?,'tiktok-api')",
              ("P" + t, trk, "Amy", "pending", label))
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,buyer_name,status,import_label,import_batch) VALUES(?,?,?,?,?,'tiktok-api')",
              ("Q" + t, trk2, "Bob", "pending", label))
    for st, q in (("33", 1), ("41", 1), ("1", 1), ("17", 1)):
        c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,?)",
                  ("P" + t, "O" + t, st, "Peach Live PART 1", q))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,?)",
              ("Q" + t, "OQ" + t, "5", "Peach Live PART 1", 1))
    prods = {}
    for st in ("1", "17", "33", "5"):
        sku = "PR" + st + t; bc = "88" + st.zfill(3) + t
        c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,0,0)", (sku, "Product " + st, bc))
        c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,1,?)", (label, st, sku))
        prods[st] = bc
    c.commit(); c.close()
    monkeypatch.setattr(A, "_barcode_lookup_online", lambda code: {"code": code, "name": "Lip Oil Cherry", "brand": "", "category": "",
                                                                   "image": "", "price": 0, "source": "test"})
    return {"t": t, "label": label, "trk": trk, "trk2": trk2, "bc": prods, "sid": "P" + t}


def _begin(client, hdr, trk):
    return client.post("/api/pack/begin", headers=hdr, json={"tracking": trk}).get_json()


def _scan(client, hdr, trk, code, expected=None):
    return client.post("/api/pack/scan", headers=hdr, json={"tracking": trk, "code": code, "expected_item_id": expected}).get_json()


def _upload(client, hdr, trk):
    data = {"tracking": trk, "station": "S1", "duration": "12", "video": (io.BytesIO(b"\x1a\x45\xdf\xa3webm"), trk + ".webm")}
    return client.post("/api/upload", headers=hdr, data=data, content_type="multipart/form-data").get_json()


def test_list_is_in_ascending_sticker_order_with_link_status(appmod, client, box):
    hdr = _as(client, appmod)
    d = _begin(client, hdr, box["trk"])
    assert d["enabled"] and [i["sticker"] for i in d["items"]] == ["1", "17", "33", "41"]
    assert [i["linked"] for i in d["items"]] == [True, True, True, False]


def test_any_order_counts(appmod, client, box):
    hdr = _as(client, appmod); trk = box["trk"]
    _begin(client, hdr, trk)
    assert _scan(client, hdr, trk, box["bc"]["33"])["result"] == "ok"           # out of order is fine
    r = _scan(client, hdr, trk, box["bc"]["17"])
    assert r["result"] == "ok" and [i["done"] for i in r["items"] if i["sticker"] == "17"] == [True]
    assert _scan(client, hdr, trk, box["bc"]["17"])["result"] == "already"


def test_wrong_product_is_rejected_and_never_stops_the_video(appmod, client, box):
    hdr = _as(client, appmod); trk = box["trk"]
    _begin(client, hdr, trk)
    r = _scan(client, hdr, trk, box["bc"]["5"])                                   # belongs to Bob's order
    assert r["result"] == "wrong" and r["product"] == "Product 5"
    assert [e["sticker"] for e in r["expected"]] == ["1", "17", "33"]
    c = appmod.sdb(appmod.DEFAULT_ORG)
    assert c.execute("SELECT COUNT(*) FROM show_product_map WHERE import_label=? AND sticker_sku='41'", (box["label"],)).fetchone()[0] == 0
    c.close()                                                                     # and nothing got linked to #41


def test_box_label_stops_and_another_label_moves_to_the_next_box(appmod, client, box):
    hdr = _as(client, appmod); trk = box["trk"]
    _begin(client, hdr, trk)
    assert _scan(client, hdr, trk, trk)["result"] == "stop"
    assert _scan(client, hdr, trk, box["trk2"])["result"] == "next_label"
    assert _scan(client, hdr, trk, "9400111122223333444455")["result"] == "next_label"   # unknown label: never a product
    c = appmod.sdb(appmod.DEFAULT_ORG)
    assert not c.execute("SELECT 1 FROM products WHERE barcode='9400111122223333444455'").fetchone()
    c.close()


def test_a_product_code_inside_some_tracking_number_is_not_taken_for_a_label(appmod, client, box):
    hdr = _as(client, appmod); trk = box["trk"]
    _begin(client, hdr, trk)
    piece = box["trk2"][4:14]                                                     # appears inside Bob's tracking
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,0,0)", ("PX" + box["t"], "Stray", piece))
    c.commit(); c.close()
    assert _scan(client, hdr, trk, piece)["result"] == "wrong"                    # never "next_label"


def test_packing_never_links_or_creates_products(appmod, client, box):
    A = appmod; hdr = _as(client, A); trk = box["trk"]
    items = _begin(client, hdr, trk)["items"]
    i41 = [i for i in items if i["sticker"] == "41"][0]
    code = "0711234" + box["t"]
    r = _scan(client, hdr, trk, code, expected=i41["id"])
    assert r["result"] == "wrong" and r["product"] is None
    c = A.sdb(A.DEFAULT_ORG)
    assert not c.execute("SELECT 1 FROM show_product_map WHERE import_label=? AND sticker_sku='41'", (box["label"],)).fetchone()
    assert not c.execute("SELECT 1 FROM products WHERE barcode=?", (code,)).fetchone()
    c.close()


def test_stopping_early_flags_the_order_with_whats_missing(appmod, client, box):
    A = appmod; hdr = _as(client, A); trk = box["trk"]
    _begin(client, hdr, trk)
    _scan(client, hdr, trk, box["bc"]["1"]); _scan(client, hdr, trk, box["bc"]["17"])
    d = _upload(client, hdr, trk)
    assert d["ok"] and d["pack"]["check"] == "missing"
    assert [m["sticker"] for m in d["pack"]["missing"]] == ["33"]             # #41 is not linked: not checked
    hdr = _as(client, A, "admin", "admin")
    rows = client.get("/api/pack/missing").get_json()["rows"]
    assert box["sid"] in [r["shipment_id"] for r in rows]
    assert client.post("/api/pack/missing/%s/checked" % box["sid"], headers=hdr).get_json()["ok"]
    assert box["sid"] not in [r["shipment_id"] for r in client.get("/api/pack/missing").get_json()["rows"]]


def test_everything_scanned_is_complete_and_scans_point_to_the_video(appmod, client, box):
    A = appmod; hdr = _as(client, A); trk = box["trk"]
    _begin(client, hdr, trk)
    for st in ("1", "17", "33"):
        _scan(client, hdr, trk, box["bc"][st])
    d = _upload(client, hdr, trk)                                                 # unlinked #41 never blocks
    assert d["pack"] == {"check": "complete", "missing": []}
    c = A.sdb(A.DEFAULT_ORG)
    vids = {r["video_file"] for r in c.execute("SELECT video_file FROM pack_scans WHERE shipment_id=? AND result='ok'", (box["sid"],))}
    c.close()
    assert len(vids) == 1 and None not in vids


def test_a_new_recording_of_the_same_box_starts_the_list_from_zero(appmod, client, box):
    hdr = _as(client, appmod); trk = box["trk"]
    _begin(client, hdr, trk); _scan(client, hdr, trk, box["bc"]["1"])
    d = _begin(client, hdr, trk)
    assert all(i["scanned"] == 0 for i in d["items"])


def test_switching_it_off_goes_back_to_start_stop_only(appmod, client, box):
    A = appmod
    hdr = _as(client, A, "worker1", "worker")
    assert client.post("/api/pack/setting", headers=hdr, json={"on": False}).status_code in (302, 401, 403)
    hdr = _as(client, A, "admin", "admin")
    assert client.post("/api/pack/setting", headers=hdr, json={"on": False}).get_json()["on"] is False
    try:
        hdr = _as(client, A)
        assert _begin(client, hdr, box["trk"])["enabled"] is False
        assert _upload(client, hdr, box["trk"])["pack"] is None
    finally:
        hdr = _as(client, A, "admin", "admin")
        client.post("/api/pack/setting", headers=hdr, json={"on": True})


def test_a_box_with_nothing_linked_is_never_flagged(appmod, client, box):
    A = appmod; hdr = _as(client, A)
    c = A.sdb(A.DEFAULT_ORG); c.execute("DELETE FROM show_product_map WHERE import_label=?", (box["label"],)); c.commit(); c.close()
    d = _begin(client, hdr, box["trk"])
    assert d["enabled"] and not any(i["linked"] for i in d["items"])
    assert _upload(client, hdr, box["trk"])["pack"] is None


# ── independent review findings ───────────────────────────────────────────────
def test_box_not_in_the_system_never_stops_on_a_product(appmod, client, box):
    hdr = _as(client, appmod)
    ghost = "9400" + "7" * 18
    assert _scan(client, hdr, ghost, box["bc"]["1"])["result"] == "wrong"        # product: keep recording
    assert _scan(client, hdr, ghost, box["trk"])["result"] == "next_label"       # a real label moves on
    assert _scan(client, hdr, ghost, ghost)["result"] == "stop"


def test_cancelled_order_gets_plain_start_stop(appmod, client, box):
    A = appmod; hdr = _as(client, A)
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", (box["sid"],)); c.commit(); c.close()
    assert _begin(client, hdr, box["trk"])["enabled"] is False


def test_orders_without_tracking_still_move_to_the_next_box_by_order_id(appmod, client, box):
    A = appmod; hdr = _as(client, A)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipments SET tracking_code=NULL WHERE shipment_id IN (?,?)", (box["sid"], "Q" + box["t"]))
    c.commit(); c.close()
    assert _scan(client, hdr, box["sid"], "Q" + box["t"])["result"] == "next_label"


def test_a_duplicate_barcode_in_the_catalog_still_matches_the_linked_product(appmod, client, box):
    A = appmod; hdr = _as(client, A)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,0,0)", ("AAA" + box["t"], "Old duplicate", box["bc"]["1"]))
    c.commit(); c.close()
    _begin(client, hdr, box["trk"])
    assert _scan(client, hdr, box["trk"], box["bc"]["1"])["result"] == "ok"
