"""R5: SQLite concurrency — busy_timeout set, and stock deducts exactly once under races."""
import uuid, threading


def test_busy_timeout_configured(appmod):
    for opener in (lambda: appmod.sdb(appmod.DEFAULT_ORG), appmod.pdb):
        c = opener(); v = c.execute("PRAGMA busy_timeout").fetchone()[0]; c.close()
        assert v == 60000, f"busy_timeout must be 60000, got {v}"


def test_concurrent_deplete_deducts_once(appmod):
    org = appmod.DEFAULT_ORG; tag = uuid.uuid4().hex[:5]
    sid = f"cx-{tag}"; label = f"Show {tag}"; prod = f"P-{tag}"
    c = appmod.sdb(org)
    c.execute("INSERT OR REPLACE INTO products(sku,name,on_hand) VALUES(?,?,100)", (prod, "Lip"))
    c.execute("INSERT OR REPLACE INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,0,?)", (label, "S1", prod))
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'tiktok-api',?,'tiktok')", (sid, "packed", label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,'S1','Lip',1)", (sid, "O" + sid))
    c.commit(); c.close()

    def worker():
        cc = appmod.sdb(org)
        try: appmod._deplete_stock_for(cc, sid); cc.commit()
        finally: cc.close()
    ts = [threading.Thread(target=worker) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]

    c = appmod.sdb(org)
    on_hand = c.execute("SELECT on_hand FROM products WHERE sku=?", (prod,)).fetchone()[0]
    moves = c.execute("SELECT COUNT(*) FROM stock_moves WHERE sku=?", (prod,)).fetchone()[0]
    c.close()
    assert on_hand == 99, f"8 concurrent depletes must take exactly 1 off 100, got {on_hand}"
    assert moves == 1, f"exactly one stock_move expected, got {moves}"
