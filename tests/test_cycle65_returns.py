"""Cycle-65: Returns module (Phase 1). Receive a return -> match the original outbound shipment by
tracking -> open a case with the order's expected items -> photograph -> the AI assistant reads/
writes via a bearer key (audited) -> warehouse restocks (adds back to inventory)."""
import io
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _outbound(A, trk):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:8]
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code,
                 buyer_username,buyer_name) VALUES(?,'packed','tiktok','b','TT Live',?,'janed','Jane D')""",
              (sid, trk))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,2)",
              (sid, "O123", "P-A", "Serum A"))
    c.execute("INSERT OR IGNORE INTO products(sku,name,on_hand,avg_cost) VALUES('P-A','Serum A',5,3)")
    c.commit(); c.close()
    return sid


def test_receive_matches_and_seeds_items(appmod, client):
    A = appmod; hdr = _admin(client, A)
    trk = "9300" + uuid.uuid4().hex[:10]
    _outbound(A, trk)
    r = client.post("/api/returns", json={"tracking_in": trk, "return_type": "customer_return"}, headers=hdr).get_json()
    assert r["ok"] and r["matched"] is True and r["status"] == "matched"
    cid = r["id"]
    g = client.get("/api/returns/%d" % cid).get_json()["case"]
    assert g["customer_name"] == "Jane D" and g["import_label"] == "TT Live" and g["order_id"] == "O123"
    assert len(g["items"]) == 1 and g["items"][0]["sku"] == "P-A" and g["items"][0]["qty_expected"] == 2


def test_duplicate_tracking_warns(appmod, client):
    A = appmod; hdr = _admin(client, A)
    trk = "9300" + uuid.uuid4().hex[:10]
    _outbound(A, trk)
    client.post("/api/returns", json={"tracking_in": trk}, headers=hdr)
    r2 = client.post("/api/returns", json={"tracking_in": trk}, headers=hdr).get_json()
    assert r2["ok"] is False and r2["duplicate"] is True


def test_photo_and_unmatched(appmod, client):
    A = appmod; hdr = _admin(client, A)
    r = client.post("/api/returns", json={"tracking_in": "NOPE" + uuid.uuid4().hex[:6]}, headers=hdr).get_json()
    assert r["matched"] is False and r["status"] == "unmatched"
    cid = r["id"]
    data = {"label": "outside", "file": (io.BytesIO(b"\xff\xd8\xffjpg"), "p.jpg")}
    p = client.post("/api/returns/%d/photo" % cid, data=data, headers=hdr, content_type="multipart/form-data").get_json()
    assert p["ok"] and "/return-photo/" in p["view_url"]
    g = client.get("/api/returns/%d" % cid).get_json()["case"]
    assert len(g["photos"]) == 1 and g["photos"][0]["label"] == "outside"


def test_ai_bearer_key_patch_is_audited(appmod, client, monkeypatch):
    A = appmod; hdr = _admin(client, A)
    monkeypatch.setenv("RETURNS_AI_KEY", "secret-ai-key")
    trk = "9300" + uuid.uuid4().hex[:10]
    _outbound(A, trk)
    cid = client.post("/api/returns", json={"tracking_in": trk}, headers=hdr).get_json()["id"]
    # fresh client with NO session — only the bearer key
    import flask
    aic = A.app.test_client()
    # ai_tags as a JSON array must NOT 500 (it's stored JSON-encoded); platform_order_no is patchable.
    r = aic.patch("/api/returns/%d" % cid, json={"decision": "restock", "ai_summary": "matched to TT request",
                                                 "ai_tags": ["damaged", "wrong_shade"], "platform_order_no": "1509039434"},
                  headers={"Authorization": "Bearer secret-ai-key"}).get_json()
    assert r["ok"] is True
    g = client.get("/api/returns/%d" % cid).get_json()["case"]
    assert g["decision"] == "restock" and g["decision_by"] == "AI"
    assert g["platform_order_no"] == "1509039434"
    assert "damaged" in g["ai_tags"]              # stored as JSON, round-trips with the tag inside
    actions = [l["action"] for l in g["log"]]
    assert any(a.startswith("set decision") for a in actions)      # the AI change is in the audit log
    # a wrong key is rejected
    bad = aic.get("/api/returns", headers={"Authorization": "Bearer wrong"})
    assert bad.status_code == 401


def test_restock_adds_to_inventory(appmod, client):
    A = appmod; hdr = _admin(client, A)
    trk = "9300" + uuid.uuid4().hex[:10]
    _outbound(A, trk)
    cid = client.post("/api/returns", json={"tracking_in": trk}, headers=hdr).get_json()["id"]
    # mark 2 received on the item
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE return_items SET qty_received=2 WHERE case_id=?", (cid,)); c.commit()
    before = c.execute("SELECT on_hand FROM products WHERE sku='P-A'").fetchone()["on_hand"]; c.close()
    client.post("/api/returns/%d/action" % cid, json={"action": "restocked"}, headers=hdr)
    c = A.sdb(A.DEFAULT_ORG)
    after = c.execute("SELECT on_hand FROM products WHERE sku='P-A'").fetchone()["on_hand"]
    st = c.execute("SELECT status FROM return_cases WHERE id=?", (cid,)).fetchone()["status"]; c.close()
    assert after == before + 2 and st == "restocked"
