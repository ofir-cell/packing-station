"""Workstream C (P0): deplete then undeplete nets to zero (stock fully restored)."""
import uuid


def test_deplete_then_undeplete_net_zero(appmod):
    org = appmod.DEFAULT_ORG; tag = uuid.uuid4().hex[:5]
    sid = f"nz-{tag}"; label = f"Show {tag}"; prod = f"P-{tag}"
    c = appmod.sdb(org)
    c.execute("INSERT OR REPLACE INTO products(sku,name,on_hand) VALUES(?,?,100)", (prod, "Lip"))
    c.execute("INSERT OR REPLACE INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,0,?)", (label, "S1", prod))
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'tiktok-api',?,'tiktok')", (sid, "packed", label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,'S1','Lip',1)", (sid, "O" + sid))
    c.commit()
    appmod._deplete_stock_for(c, sid); c.commit()
    mid = c.execute("SELECT on_hand FROM products WHERE sku=?", (prod,)).fetchone()[0]
    appmod._undeplete_stock_for(c, sid); c.commit()
    end = c.execute("SELECT on_hand FROM products WHERE sku=?", (prod,)).fetchone()[0]
    marker = c.execute("SELECT COALESCE(depleted_qty,0) FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()[0]
    c.close()
    assert mid == 99, f"deplete should take 1 off, got {mid}"
    assert end == 100, f"undeplete must restore to 100, got {end}"
    assert marker == 0, "depletion marker cleared after restore"
