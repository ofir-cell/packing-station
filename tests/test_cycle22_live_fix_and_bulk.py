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


def _as(client, A, name, role="worker"):
    uname = name.lower()
    with A.update_json(A.USERS_FILE) as users:          # so session-revocation sees a live account
        u = dict(users.get(uname) or {})                # MERGE — never drop seeded fields (badge_token, etc.)
        u.update({"password": u.get("password", "x"), "role": role, "name": name, "org": A.DEFAULT_ORG})
        users[uname] = u
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=A.DEFAULT_ORG, name=name)
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


def test_history_is_per_worker_with_mine_flag(appmod, client):
    """Two workers on the same live each see only their own matches via ?mine=1,
    while the global queue (no flag) shows both."""
    A = appmod; lab = "L" + uuid.uuid4().hex[:6]
    pa = "DANA" + uuid.uuid4().hex[:4]; pb = "NOA" + uuid.uuid4().hex[:4]
    _prod(A, pa, barcode="BC-DANA"); _prod(A, pb, barcode="BC-NOA")
    _sold(A, lab, "30"); _sold(A, lab, "31")
    hd = _as(client, A, "Dana")
    client.post("/api/live/match", json={"show": lab, "sticker": "30", "part": 1, "code": "BC-DANA"}, headers=hd)
    hn = _as(client, A, "Noa")
    client.post("/api/live/match", json={"show": lab, "sticker": "31", "part": 1, "code": "BC-NOA"}, headers=hn)
    # Noa's own history: only her sticker
    mine = client.get("/api/live/match-queue?mine=1&show=" + lab, headers=hn).get_json()
    assert sorted(str(m["sticker"]) for m in mine["matched"]) == ["31"]
    # Dana's own history: only hers
    _as(client, A, "Dana")
    dmine = client.get("/api/live/match-queue?mine=1&show=" + lab).get_json()
    assert sorted(str(m["sticker"]) for m in dmine["matched"]) == ["30"]
    # Global (no flag) shows both; progress count is global either way
    glob = client.get("/api/live/match-queue?show=" + lab).get_json()
    assert sorted(str(m["sticker"]) for m in glob["matched"]) == ["30", "31"]
    assert glob["matched_count"] == 2


def test_audit_log_records_who_matched_what(appmod, client):
    """The append-only log keeps every action (match, replace, bundle) with the worker,
    even after a re-match overwrites the current product."""
    A = appmod; lab = "L" + uuid.uuid4().hex[:6]
    a = "WR" + uuid.uuid4().hex[:4]; b = "RT" + uuid.uuid4().hex[:4]
    _prod(A, a, barcode="BC-WR"); _prod(A, b, barcode="BC-RT")
    _sold(A, lab, "40")
    hd = _as(client, A, "Dana")
    client.post("/api/live/match", json={"show": lab, "sticker": "40", "part": 1, "code": "BC-WR"}, headers=hd)
    client.post("/api/live/match", json={"show": lab, "sticker": "40", "part": 1, "code": "BC-RT"}, headers=hd)  # correction
    hdr = _admin(client, A)
    log = client.get("/api/live/match-log?show=" + lab, headers=hdr).get_json()
    assert log["ok"]
    acts = [(r["who"], r["sticker"], r["action"], r["product_sku"]) for r in log["rows"]]
    assert ("Dana", "40", "match", a) in acts       # the first link is preserved
    assert ("Dana", "40", "replace", b) in acts     # and the correction is its own row
    assert "Dana" in log["workers"]


def test_match_log_is_manager_only(appmod, client):
    A = appmod; _as(client, A, "Floorhand22", "worker")
    r = client.get("/api/live/match-log")
    assert r.status_code in (302, 403)              # workers cannot read the audit trail
