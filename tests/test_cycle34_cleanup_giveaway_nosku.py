"""Cycle-34: a cancelled item that is a giveaway / has no SKU (shown with a "?" badge
under "No part") must be markable in Table Cleanup. It used to fail: the group carried
an empty sku, and /api/cleanup/<label>/mark rejected it with "Missing SKU", so the worker
could tap it but it silently reverted. Fix: no-SKU lines get a stable name-based identity,
distinct no-SKU products stay separate, and marking them clears the group."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _cancelled_line(c, label, sku, name):
    sid = "SK" + uuid.uuid4().hex[:10]
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
              "VALUES(?,'pending','whatnot','csv',?)", (sid, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,cancelled) "
              "VALUES(?,?,?,?,1,1)", (sid, "O" + sid, sku, name))
    c.commit()


def _groups(client, lbl):
    return {g["id"]: g for g in client.get("/api/cleanup/" + lbl).get_json()["groups"]}


def test_nosku_giveaway_is_markable_and_clears(appmod, client):
    A = appmod; hdr = _admin(client, A)
    lbl = "WN Give " + uuid.uuid4().hex[:5]
    c = A.sdb(A.DEFAULT_ORG)
    _cancelled_line(c, lbl, "940", "Gucci Lipstick Part 1")   # normal, has SKU
    _cancelled_line(c, lbl, "", "TATCHA MOSTUIRIZER")          # giveaway, no SKU, no part
    c.close()

    groups = _groups(client, lbl)
    assert "940" in groups                                     # real sku keeps its identity
    gid = next(k for k in groups if k.startswith("name:"))     # the no-sku giveaway
    assert groups[gid]["sku"] == ""                            # still shows "?" in the UI
    assert "tatcha" in gid

    # marking the no-sku giveaway used to 400 "Missing SKU"; now it clears
    r = client.post("/api/cleanup/" + lbl + "/mark",
                    json={"sku": gid, "part": "", "removed": True}, headers=hdr).get_json()
    assert r["ok"] is True
    g2 = _groups(client, lbl)[gid]
    assert g2["removed_at"] is not None and g2["removed_by"] == "Boss"

    # unmark puts it back to pending
    assert client.post("/api/cleanup/" + lbl + "/mark",
                       json={"sku": gid, "part": "", "removed": False}, headers=hdr).get_json()["ok"] is True
    assert _groups(client, lbl)[gid]["removed_at"] is None


def test_two_distinct_nosku_products_stay_separate(appmod, client):
    """Two different no-SKU giveaways must NOT merge into one blank group — each is its
    own cleanup line, and clearing one leaves the other pending."""
    A = appmod; hdr = _admin(client, A)
    lbl = "WN Give2 " + uuid.uuid4().hex[:5]
    c = A.sdb(A.DEFAULT_ORG)
    _cancelled_line(c, lbl, "", "TATCHA MOSTUIRIZER")
    _cancelled_line(c, lbl, "", "LANEIGE LIP MASK")
    c.close()
    groups = _groups(client, lbl)
    assert len(groups) == 2                                    # not collapsed into one
    gid0 = next(iter(groups))
    client.post("/api/cleanup/" + lbl + "/mark",
                json={"sku": gid0, "part": "", "removed": True}, headers=hdr)
    after = _groups(client, lbl)
    assert after[gid0]["removed_at"] is not None              # one cleared
    other = next(k for k in after if k != gid0)
    assert after[other]["removed_at"] is None                 # the other still pending
