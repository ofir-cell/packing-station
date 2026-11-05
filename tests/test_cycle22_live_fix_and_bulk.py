"""Cycle-22: two additions to the guided Live Mode, exercised at the backend they call.

1. "Just matched · tap to fix" — tapping a matched sticker re-opens it and the next scan
   must REPLACE the wrong product. That is just /api/live/match called again for the same
   (sticker, part): it upserts show_product_map, so the product_sku changes, no duplicate row.
2. "Bulk range" — one product (or several = a bundle) applied to every waiting sticker in a
   from–to range: /api/live/match for the first code on each sticker, plus /api/live/kit/add
   for each code when there are >=2 (making a bundle on every sticker)."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _prod(A, sku, barcode=None, on_hand=50, cost=2.0):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,?,?)",
              (sku, "P-" + sku, barcode or sku, on_hand, cost))
    c.commit(); c.close()


def _sold(A, label, sticker, part_name="Lipstick (Part 1)", price=12.0):
    """A real sold sticker: one shipment_item carrying the TikTok per-sale counter in .sku."""
    sid = "s-" + uuid.uuid4().hex[:8]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) "
              "VALUES(?,?,'tiktok-api',?,'tiktok')", (sid, "pending", label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue,cancelled) "
              "VALUES(?,?,?,?,1,?,0)", (sid, "O" + sid, str(sticker), part_name, price))
    c.commit(); c.close()
    return sid


def _mapped_sku(A, label, sticker, part=0):
    c = A.sdb(A.DEFAULT_ORG)
    r = c.execute("SELECT product_sku FROM show_product_map WHERE import_label=? AND sticker_sku=? AND part=?",
                  (label, str(sticker), part)).fetchone()
    c.close()
    return r["product_sku"] if r else None


def _map_count(A, label, sticker, part=0):
    c = A.sdb(A.DEFAULT_ORG)
    n = c.execute("SELECT COUNT(*) FROM show_product_map WHERE import_label=? AND sticker_sku=? AND part=?",
                  (label, str(sticker), part)).fetchone()[0]
    c.close()
    return n


def test_rematch_replaces_product_no_duplicate(appmod, client):
    """Tap-to-fix: matching the same sticker again swaps the product in place."""
    A = appmod; hdr = _admin(client, A); lab = "L" + uuid.uuid4().hex[:6]
    a = "WRONG" + uuid.uuid4().hex[:4]; b = "RIGHT" + uuid.uuid4().hex[:4]
    _prod(A, a, barcode="BC-A"); _prod(A, b, barcode="BC-B")
    _sold(A, lab, "100", part_name="Lip (Part 1)")
    r1 = client.post("/api/live/match", json={"show": lab, "sticker": "100", "part": 1, "code": "BC-A"}, headers=hdr).get_json()
    assert r1["ok"]
    assert _mapped_sku(A, lab, "100", 1) == a
    # worker tapped the chip and re-scanned the correct product
    r2 = client.post("/api/live/match", json={"show": lab, "sticker": "100", "part": 1, "code": "BC-B"}, headers=hdr).get_json()
    assert r2["ok"]
    assert _mapped_sku(A, lab, "100", 1) == b          # product replaced
    assert _map_count(A, lab, "100", 1) == 1           # upsert, not a second row


def test_matched_list_feeds_the_fix_chips(appmod, client):
    """The queue returns the matched stickers the 'tap to fix' chips render from."""
    A = appmod; hdr = _admin(client, A); lab = "L" + uuid.uuid4().hex[:6]
    p = "SKU" + uuid.uuid4().hex[:4]; _prod(A, p, barcode="BC-P")
    _sold(A, lab, "7", part_name="Gloss (Part 2)")
    client.post("/api/live/match", json={"show": lab, "sticker": "7", "part": 2, "code": "BC-P"}, headers=hdr)
    q = client.get("/api/live/match-queue?show=" + lab, headers=hdr).get_json()
    hit = [m for m in q["matched"] if str(m["sticker"]) == "7"]
    assert hit and hit[0]["part"] == 2 and hit[0]["product_sku"] == p


def test_bulk_single_product_across_range(appmod, client):
    """Bulk with ONE product: every waiting sticker in from–to gets that product; outside untouched."""
    A = appmod; hdr = _admin(client, A); lab = "L" + uuid.uuid4().hex[:6]
    p = "ONE" + uuid.uuid4().hex[:4]; _prod(A, p, barcode="BC-1")
    for n in (10, 11, 12, 13):
        _sold(A, lab, n, part_name="Item (Part 1)")
    # the UI filters poolAll() to 11..12, then calls match for each
    for n in (11, 12):
        assert client.post("/api/live/match", json={"show": lab, "sticker": str(n), "part": 1, "code": "BC-1"},
                           headers=hdr).get_json()["ok"]
    assert _mapped_sku(A, lab, "11", 1) == p
    assert _mapped_sku(A, lab, "12", 1) == p
    assert _mapped_sku(A, lab, "10", 1) is None        # below range, untouched
    assert _mapped_sku(A, lab, "13", 1) is None        # above range, untouched


def test_bulk_bundle_applies_kit_to_every_sticker(appmod, client):
    """Bulk with TWO products becomes a bundle on each sticker in the range."""
    A = appmod; hdr = _admin(client, A); lab = "L" + uuid.uuid4().hex[:6]
    a = "KA" + uuid.uuid4().hex[:4]; b = "KB" + uuid.uuid4().hex[:4]
    _prod(A, a, barcode="BC-KA"); _prod(A, b, barcode="BC-KB")
    for n in (20, 21):
        _sold(A, lab, n, part_name="Bundle (Part 1)")
    for n in (20, 21):
        client.post("/api/live/match", json={"show": lab, "sticker": str(n), "part": 1, "code": "BC-KA"}, headers=hdr)
        for code in ("BC-KA", "BC-KB"):
            client.post("/api/live/kit/add", json={"show": lab, "sticker": str(n), "part": 1, "code": code}, headers=hdr)
    for n in (20, 21):
        got = client.get("/api/live/kit?show=%s&sticker=%s&part=1" % (lab, n), headers=hdr).get_json()
        skus = sorted(x["sku"] for x in got["components"])
        assert skus == sorted([a, b]), "sticker %s should carry both components" % n
