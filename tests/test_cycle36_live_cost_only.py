"""Cycle-36: in guided Live Mode, a sold sticker with NO barcode can get a one-off cost.
/api/live/cost-only records its COGS (qty from the CSV × the unit cost typed) into the live
P&L and marks the sticker handled, WITHOUT creating a catalog product or moving stock."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _sold(A, label, sticker, name, qty=1, rev=10.0):
    c = A.sdb(A.DEFAULT_ORG)
    for _ in range(qty):
        sid = "S" + uuid.uuid4().hex[:10]
        c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
                  "VALUES(?,'packed','tiktok','tiktok-api',?)", (sid, label))
        c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) "
                  "VALUES(?,?,?,?,1,?)", (sid, "O" + sid, sticker, name, rev))
    c.commit(); c.close()


def test_cost_only_records_cogs_and_clears_from_queue(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "TT Live " + uuid.uuid4().hex[:5]
    _sold(A, label, "465", "$1 Perfume Part 1", qty=2, rev=12.0)   # 2 sold, no barcode

    # it starts in the waiting queue (unmatched)
    q = client.get("/api/live/match-queue?show=" + label).get_json()
    assert any(w["sticker"] == "465" for w in q["waiting"])

    r = client.post("/api/live/cost-only", json={"show": label, "sticker": "465", "part": 1, "unit_cost": 3.5},
                    headers=hdr).get_json()
    assert r["ok"] is True and r["qty"] == 2 and r["unit_cost"] == 3.5 and r["cogs"] == 7.0

    # it leaves the waiting queue (handled)
    q2 = client.get("/api/live/match-queue?show=" + label).get_json()
    assert not any(w["sticker"] == "465" for w in q2["waiting"])
    assert q2["matched_count"] >= 1

    # COGS lands in the live P&L (2 × 3.5), and no catalog product was created
    c = A.sdb(A.DEFAULT_ORG)
    tot = A._live_totals(c, label, is_admin=True)
    assert tot["cogs"] == 7.0
    assert c.execute("SELECT COUNT(*) FROM products WHERE sku=?", ("NOBC-465-P1",)).fetchone()[0] == 0
    # no stock move for the synthetic sku
    assert c.execute("SELECT COUNT(*) FROM stock_moves WHERE sku=?", ("NOBC-465-P1",)).fetchone()[0] == 0
    c.close()


def test_cost_only_is_idempotent(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "TT Live " + uuid.uuid4().hex[:5]
    _sold(A, label, "77", "Gloss Part 1", qty=1, rev=8.0)
    client.post("/api/live/cost-only", json={"show": label, "sticker": "77", "part": 1, "unit_cost": 2}, headers=hdr)
    client.post("/api/live/cost-only", json={"show": label, "sticker": "77", "part": 1, "unit_cost": 4}, headers=hdr)
    c = A.sdb(A.DEFAULT_ORG)
    # only ONE live_sales row survives (the latest), COGS = 1 × 4
    assert c.execute("SELECT COUNT(*) FROM live_sales WHERE import_label=? AND product_sku='NOBC-77-P1'",
                     (label,)).fetchone()[0] == 1
    assert A._live_totals(c, label, is_admin=True)["cogs"] == 4.0
    c.close()


def test_cost_only_rejects_bad_cost(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "TT Live " + uuid.uuid4().hex[:5]
    _sold(A, label, "9", "Thing Part 1", qty=1)
    r = client.post("/api/live/cost-only", json={"show": label, "sticker": "9", "part": 1, "unit_cost": -1},
                    headers=hdr).get_json()
    assert r["ok"] is False
