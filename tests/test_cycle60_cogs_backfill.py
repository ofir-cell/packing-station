"""Cycle-60: retroactive COGS. A product sold during a live with no cost yet records unit_cost=0.
When the admin fills the cost afterward (After-Live Cleanup → Save), the past zero-cost sales are
backfilled so that live's profit stops under-counting cost — without rewriting a real cost that was
already snapshotted at sale time."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _sale(A, sku, label, unit_cost, unit_price, qty=1):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost) VALUES(?,?,?,0,0)",
              (sku, "Prod " + sku, sku))
    c.execute("""INSERT INTO live_sales(import_label,sticker_sku,part,product_sku,qty,unit_cost,unit_price,sold_at,sold_by)
                 VALUES(?,?,?,?,?,?,?,datetime('now'),'t')""",
              (label, "100", 1, sku, qty, unit_cost, unit_price))
    c.commit(); c.close()


def test_filling_cost_backfills_zero_cogs(appmod, client):
    A = appmod; hdr = _admin(client, A)
    sku = "P" + uuid.uuid4().hex[:6]
    label = "LIVE " + uuid.uuid4().hex[:4]
    _sale(A, sku, label, unit_cost=0, unit_price=10, qty=3)   # sold with no cost yet

    # before: COGS is 0 → profit = full revenue
    c = A.sdb(A.DEFAULT_ORG)
    tot = A._live_totals(c, label, is_admin=True); c.close()
    assert tot["cogs"] == 0 and tot["profit"] == 30

    r = client.post("/api/products", json={"sku": sku, "name": "Prod", "cost": 4}, headers=hdr).get_json()
    assert r["ok"] and r["cogs_backfilled"] == 1          # the one zero-cost sale row was filled

    c = A.sdb(A.DEFAULT_ORG)
    tot = A._live_totals(c, label, is_admin=True)
    row = c.execute("SELECT unit_cost FROM live_sales WHERE product_sku=?", (sku,)).fetchone(); c.close()
    assert round(row["unit_cost"], 2) == 4.0
    assert tot["cogs"] == 12 and tot["profit"] == 18       # 3 units × $4 cost; profit 30 - 12


def test_does_not_overwrite_a_real_cost_snapshot(appmod, client):
    A = appmod; hdr = _admin(client, A)
    sku = "P" + uuid.uuid4().hex[:6]
    label = "LIVE " + uuid.uuid4().hex[:4]
    _sale(A, sku, label, unit_cost=7, unit_price=10, qty=2)   # already had a real cost at sale time

    r = client.post("/api/products", json={"sku": sku, "name": "Prod", "cost": 4}, headers=hdr).get_json()
    assert r["cogs_backfilled"] == 0                          # nothing rewritten

    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT unit_cost FROM live_sales WHERE product_sku=?", (sku,)).fetchone(); c.close()
    assert round(row["unit_cost"], 2) == 7.0                  # the historical snapshot is preserved
