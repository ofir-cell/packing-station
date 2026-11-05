"""Cycle-24: invoice → internal PO → warehouse-manager approval → stock, plus the
"this is a set" explode. Stock enters ONLY on approval. A set line puts stock on its
child unit SKUs (one if identical, one per unit if different), never on the container line.
The manager approves by internal PO number and never sees the supplier."""
import uuid


def _as(client, A, role, name=None):
    uname = (name or role) + "_u"
    with A.update_json(A.USERS_FILE) as users:
        u = dict(users.get(uname) or {})
        u.update({"password": u.get("password", "x"), "role": role, "name": name or role.title(), "org": A.DEFAULT_ORG})
        users[uname] = u
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=A.DEFAULT_ORG, name=name or role.title())
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _on_hand(A, sku):
    c = A.sdb(A.DEFAULT_ORG)
    r = c.execute("SELECT on_hand FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    return (r["on_hand"] if r else None)


def _to_po(client, A, hdr, lines, supplier="ACME Beauty"):
    r = client.post("/api/products/import-pdf/to-po",
                    json={"supplier": supplier, "items": lines}, headers=hdr).get_json()
    assert r["ok"]
    return r["po_id"]


def test_invoice_to_po_holds_stock_until_approval(appmod, client):
    A = appmod; hdr = _as(client, A, "admin")
    sku = "INV" + uuid.uuid4().hex[:5]
    poid = _to_po(client, A, hdr, [{"name": "Lip Oil", "store_sku": sku, "qty": 20, "unit_cost": 2}])
    # product exists but NO stock yet
    assert _on_hand(A, sku) == 0
    c = A.sdb(A.DEFAULT_ORG)
    st = c.execute("SELECT status FROM purchase_orders WHERE id=?", (poid,)).fetchone()["status"]; c.close()
    assert st == "awaiting_approval"
    # manager approves -> stock enters
    mh = _as(client, A, "manager")
    r = client.post("/api/po/%d/approve" % poid, headers=mh).get_json()
    assert r["ok"]
    assert _on_hand(A, sku) == 20
    c = A.sdb(A.DEFAULT_ORG)
    st = c.execute("SELECT status,approved_by FROM purchase_orders WHERE id=?", (poid,)).fetchone(); c.close()
    assert st["status"] == "received" and st["approved_by"]


def test_manager_never_sees_supplier(appmod, client):
    A = appmod; hdr = _as(client, A, "admin")
    poid = _to_po(client, A, hdr, [{"name": "X", "store_sku": "Q" + uuid.uuid4().hex[:5], "qty": 1}], supplier="Secret Vendor LLC")
    mh = _as(client, A, "manager")
    det = client.get("/api/po/%d/detail" % poid, headers=mh).get_json()
    assert det["ok"] and det["po"]["supplier"] is None and det["po"].get("supplier_hidden")
    lst = client.get("/api/po", headers=mh).get_json()
    assert all(p.get("supplier") is None for p in lst)
    # admin still sees it
    client.get("/api/po", headers=_as(client, A, "admin"))
    adet = client.get("/api/po/%d/detail" % poid, headers=hdr).get_json()
    assert adet["po"]["supplier"] == "Secret Vendor LLC"


def test_set_same_units_one_child_sku(appmod, client):
    """100 sets of 4 identical minis -> one new unit SKU, 400 units on approval."""
    A = appmod; hdr = _as(client, A, "admin")
    poid = _to_po(client, A, hdr, [{"name": "Mini Perfume Set", "store_sku": "SET" + uuid.uuid4().hex[:5], "qty": 100, "unit_cost": 1.0}])
    det = client.get("/api/po/%d/detail" % poid, headers=hdr).get_json()
    item_id = det["po"]["items"][0]["id"]
    r = client.post("/api/po/%d/line/%d/set" % (poid, item_id), json={"units": 4, "mode": "same"}, headers=hdr).get_json()
    assert r["ok"] and len(r["children"]) == 1
    child = r["children"][0]["sku"]
    _as(client, A, "manager"); mh = {"X-CSRF-Token": "tok"}
    client.set_cookie("csrf_token", "tok")
    client.post("/api/po/%d/approve" % poid, headers=mh)
    assert _on_hand(A, child) == 400          # 100 sets x 4 units
    # the container line's own SKU got no stock
    assert _on_hand(A, det["po"]["items"][0]["sku"]) == 0


def test_set_diff_units_one_sku_each(appmod, client):
    """50 sets of 3 different shades -> 3 new SKUs, 50 units each on approval."""
    A = appmod; hdr = _as(client, A, "admin")
    poid = _to_po(client, A, hdr, [{"name": "Shade Trio", "store_sku": "TRIO" + uuid.uuid4().hex[:5], "qty": 50}])
    det = client.get("/api/po/%d/detail" % poid, headers=hdr).get_json()
    item_id = det["po"]["items"][0]["id"]
    r = client.post("/api/po/%d/line/%d/set" % (poid, item_id),
                    json={"units": 3, "mode": "diff", "names": ["Red", "Pink", "Nude"]}, headers=hdr).get_json()
    assert r["ok"] and len(r["children"]) == 3
    skus = [ch["sku"] for ch in r["children"]]
    client.set_cookie("csrf_token", "tok"); _as(client, A, "manager")
    client.post("/api/po/%d/approve" % poid, headers={"X-CSRF-Token": "tok"})
    for s in skus:
        assert _on_hand(A, s) == 50
    # names carried through
    c = A.sdb(A.DEFAULT_ORG)
    names = sorted(x["name"] for x in c.execute("SELECT name FROM products WHERE sku IN (%s)" % ",".join("?" * 3), skus).fetchall())
    c.close()
    assert names == ["Nude", "Pink", "Red"]


def test_verify_barcode_matches_line(appmod, client):
    A = appmod; hdr = _as(client, A, "admin")
    sku = "BV" + uuid.uuid4().hex[:5]
    cc = A.sdb(A.DEFAULT_ORG); cc.execute("UPDATE products SET barcode='112233' WHERE sku=?", (sku,)); cc.close()
    poid = _to_po(client, A, hdr, [{"name": "Thing", "store_sku": sku, "qty": 5}])
    # set the barcode (product was created by to-po; set it now)
    cc = A.sdb(A.DEFAULT_ORG); cc.execute("UPDATE products SET barcode='112233' WHERE sku=?", (sku,)); cc.commit(); cc.close()
    det = client.get("/api/po/%d/detail" % poid, headers=hdr).get_json()
    item_id = det["po"]["items"][0]["id"]
    mh = _as(client, A, "manager")
    bad = client.post("/api/po/%d/line/%d/verify" % (poid, item_id), json={"code": "999"}, headers=mh).get_json()
    assert bad["ok"] is False
    good = client.post("/api/po/%d/line/%d/verify" % (poid, item_id), json={"code": "112233"}, headers=mh).get_json()
    assert good["ok"] and good["verified"]


def test_cs_cannot_approve(appmod, client):
    A = appmod; hdr = _as(client, A, "admin")
    poid = _to_po(client, A, hdr, [{"name": "Z", "store_sku": "Z" + uuid.uuid4().hex[:5], "qty": 1}])
    ch = _as(client, A, "cs")
    assert client.post("/api/po/%d/approve" % poid, headers=ch).status_code == 403
