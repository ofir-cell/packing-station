"""Cycle-21: guided Live Mode — pick live→part→start sticker, advance up through the REAL
sold stickers (via the match queue), per-part progress, kit, no money for workers. The scan
itself reuses /api/live/match (already tested); here we cover the new progress data + render."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Ofir")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def test_match_queue_reports_matched_per_part(appmod, client):
    A = appmod; hdr = _admin(client, A); lab = "L" + uuid.uuid4().hex[:6]
    c = A.sdb(A.DEFAULT_ORG)
    # two sold stickers: one on part 0, one on part 2 (part comes from the listing name)
    for sid, sku, nm in [("s1", "10", "Serum"), ("s2", "11", "Cream Part 2")]:
        sidf = sid + lab
        c.execute("INSERT INTO shipments(shipment_id,status,import_label,import_batch,platform) VALUES(?,?,?,'tiktok-api','tiktok')", (sidf, "pending", lab))
        c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) VALUES(?,?,?,?,1,9)", (sidf, "O" + sidf, sku, nm))
    # match the part-2 one -> show_product_map row on part 2
    c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,on_hand,avg_cost) VALUES('PX','PX',NULL,5,1)")
    c.execute("INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku) VALUES(?,?,?,?)", (lab, "11", 2, "PX"))
    c.commit(); c.close()
    q = client.get("/api/live/match-queue?show=" + lab, headers=hdr).get_json()
    assert q["ok"]
    assert q["matched_by_part"].get("2") == 1 or q["matched_by_part"].get(2) == 1   # one matched in part 2
    # sticker 10 (part 0) is still waiting
    assert any(w["sticker"] == "10" and (w["part"] or 0) == 0 for w in q["waiting"])


def test_live_mode_is_guided_wizard(appmod, client):
    A = appmod; _admin(client, A)
    h = client.get("/admin/live").get_data(as_text=True)
    assert h.rstrip().endswith("</html>")
    for tok in ("Which live are you working on", "Which part", "Start from which sticker",
                'id="progScanned"', "/api/live/match-queue", '/api/live/match', 'id="kitBtn"'):
        assert tok in h, "missing " + tok


def test_match_live_hidden_from_menu(appmod, client):
    A = appmod; _admin(client, A)
    h = client.get("/admin/live").get_data(as_text=True)
    assert "/admin/match-live" not in h            # the menu no longer links Match Live
