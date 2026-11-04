"""Cycle-19 (stage A): a kit/bundle sticker is physically several products. Inventory must
come off EVERY component (idempotently), restore on unpack, and never touch non-kit items.
COGS follows from the per-component stock_moves. Floor pick/pack expansion is stage B."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _prod(A, sku, on_hand=10, cost=3.0, barcode=None):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,?,?)",
              (sku, "P-" + sku, barcode, on_hand, cost))
    c.commit(); c.close()


def _on_hand(A, sku):
    c = A.sdb(A.DEFAULT_ORG)
    r = c.execute("SELECT on_hand FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    return r["on_hand"] if r else None


def _packed_order(A, label, sticker, product_name="Bundle Deal"):
    sid = "box-" + uuid.uuid4().hex[:6]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform) "
              "VALUES(?,?,'packed','tiktok-api',?,'tiktok')", (sid, "9400" + uuid.uuid4().hex[:10], label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,1)",
              (sid, "O" + sid, sticker, product_name))
    c.commit(); c.close()
    return sid


def _define_kit(A, label, sticker, comps, part=0):
    c = A.sdb(A.DEFAULT_ORG); A._kit_ensure(c)
    for csku, q in comps:
        c.execute("INSERT OR REPLACE INTO show_kit(import_label,sticker_sku,part,component_sku,qty) VALUES(?,?,?,?,?)",
                  (label, sticker, part, csku, q))
    c.commit(); c.close()


def test_kit_deducts_every_component(appmod):
    A = appmod; lab = "L" + uuid.uuid4().hex[:6]; a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a, on_hand=10, cost=2.0); _prod(A, b, on_hand=5, cost=4.0)
    _define_kit(A, lab, "50", [(a, 1), (b, 1)])
    sid = _packed_order(A, lab, "50")
    c = A.sdb(A.DEFAULT_ORG); A._deplete_stock_for(c, sid); c.commit(); c.close()
    assert _on_hand(A, a) == 9 and _on_hand(A, b) == 4          # both components came off


def test_kit_depletion_is_idempotent(appmod):
    A = appmod; lab = "L" + uuid.uuid4().hex[:6]; a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a, on_hand=10); _prod(A, b, on_hand=10)
    _define_kit(A, lab, "7", [(a, 1), (b, 2)])
    sid = _packed_order(A, lab, "7")
    for _ in range(3):                                          # run the depletion 3 times
        c = A.sdb(A.DEFAULT_ORG); A._deplete_stock_for(c, sid); c.commit(); c.close()
    assert _on_hand(A, a) == 9 and _on_hand(A, b) == 8          # qty 2 for b; never double-counted


def test_unpack_restores_every_component(appmod):
    A = appmod; lab = "L" + uuid.uuid4().hex[:6]; a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a, on_hand=10); _prod(A, b, on_hand=10)
    _define_kit(A, lab, "9", [(a, 1), (b, 1)])
    sid = _packed_order(A, lab, "9")
    c = A.sdb(A.DEFAULT_ORG); A._deplete_stock_for(c, sid); c.commit(); c.close()
    assert _on_hand(A, a) == 9 and _on_hand(A, b) == 9
    c = A.sdb(A.DEFAULT_ORG); A._undeplete_stock_for(c, sid); c.commit(); c.close()
    assert _on_hand(A, a) == 10 and _on_hand(A, b) == 10        # fully back on the shelf


def test_non_kit_item_unaffected(appmod):
    """A plain sticker (no kit) must still use the single-product path, untouched."""
    A = appmod; lab = "L" + uuid.uuid4().hex[:6]; p = "SP" + uuid.uuid4().hex[:5]
    _prod(A, p, on_hand=10)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,0,?)", (lab, "3", p))
    c.commit(); c.close()
    sid = _packed_order(A, lab, "3", product_name="Just One")
    c = A.sdb(A.DEFAULT_ORG); A._deplete_stock_for(c, sid); c.commit(); c.close()
    assert _on_hand(A, p) == 9                                   # single product, one deduction


def test_kit_add_endpoint_defines_and_lists(appmod, client):
    A = appmod; hdr = _admin(client, A); lab = "L" + uuid.uuid4().hex[:6]
    a = "KA" + uuid.uuid4().hex[:5]; b = "KB" + uuid.uuid4().hex[:5]
    _prod(A, a); _prod(A, b)
    r1 = client.post("/api/live/kit/add", json={"show": lab, "sticker": "22", "product_sku": a}, headers=hdr).get_json()
    r2 = client.post("/api/live/kit/add", json={"show": lab, "sticker": "22", "product_sku": b}, headers=hdr).get_json()
    assert r1["ok"] and r2["ok"]
    got = client.get("/api/live/kit?show=%s&sticker=22" % lab, headers=hdr).get_json()
    skus = sorted(x["sku"] for x in got["components"])
    assert skus == sorted([a, b])
    # removing one leaves the other
    client.post("/api/live/kit/remove", json={"show": lab, "sticker": "22", "component_sku": a}, headers=hdr)
    got = client.get("/api/live/kit?show=%s&sticker=22" % lab, headers=hdr).get_json()
    assert [x["sku"] for x in got["components"]] == [b]
