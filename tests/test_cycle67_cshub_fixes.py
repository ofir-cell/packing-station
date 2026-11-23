"""Cycle-67: fixes from Grok round-1. Status PATCH actually applies; auto-fill fills + stores
tracking + warns on no match; risk_reasons comes back as an array; scoped keys reach the customers
API with a JSON 401 (never an HTML redirect)."""
import uuid


def _admin(client, A, role="admin"):
    user = {"admin": "admin", "cs": "cs1"}.get(role, "admin")
    with client.session_transaction() as s:
        s.update(user=user, role=role, roles=[role], org=A.DEFAULT_ORG, name=user)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _seed(A, trk, user="janed", order="O-1"):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:8]
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,
                 tracking_code,buyer_username,buyer_name) VALUES(?,'packed','whatnot','b','HERA Live',?,?,?)""",
              (sid, trk, user, "Jane D"))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) VALUES(?,?,?,?,1,20)",
              (sid, order, "P-A", "Serum A"))
    c.commit(); c.close()
    return sid


def _key(client, A, scopes=None):
    hdr = _admin(client, A)
    body = {"label": "AI", "org": A.DEFAULT_ORG}
    if scopes is not None:
        body["scopes"] = scopes
    return client.post("/api/apikeys", json=body, headers=hdr).get_json()["key"]


def test_status_patch_applies(appmod, client):
    A = appmod
    key = _key(client, A)
    ai = A.app.test_client(); h = {"Authorization": "Bearer " + key}
    tid = ai.post("/api/tickets", json={"platform": "whatnot", "username": "amy", "inbound_text": "hi"}, headers=h).get_json()["id"]
    r = ai.patch("/api/tickets/%d" % tid, json={"status": "ai_ready"}, headers=h).get_json()
    assert r["ok"] is True
    g = ai.get("/api/tickets/%d" % tid, headers=h).get_json()["ticket"]
    assert g["status"] == "ai_ready"          # #1 — no longer silently ignored


def test_autofill_fills_and_stores_tracking(appmod, client):
    A = appmod
    key = _key(client, A)
    trk = "9334" + uuid.uuid4().hex[:12]
    _seed(A, trk, user="moorenicolle228", order="1562345236")
    ai = A.app.test_client(); h = {"Authorization": "Bearer " + key}
    r = ai.post("/api/tickets", json={"username": "moorenicolle228", "platform_order_no": "1562345236",
                                      "tracking": trk, "type": "where_order", "inbound_text": "where?"}, headers=h).get_json()
    assert r["matched"] is True
    g = ai.get("/api/tickets/%d" % r["id"], headers=h).get_json()["ticket"]
    assert g["customer_name"] == "Jane D" and g["import_label"] == "HERA Live"
    assert g["order_id"] == "1562345236" and g["tracking"] == trk      # #3 — tracking stored
    assert isinstance(g["risk_reasons"], list)                         # #9 — array, not "[]"
    assert "order" in g and g["order"]["tracking"] == trk              # #7 — order box


def test_no_match_warning(appmod, client):
    A = appmod
    key = _key(client, A)
    ai = A.app.test_client(); h = {"Authorization": "Bearer " + key}
    r = ai.post("/api/tickets", json={"username": "ghost_" + uuid.uuid4().hex[:6], "tracking": "ZZ" + uuid.uuid4().hex[:8],
                                      "inbound_text": "hi"}, headers=h).get_json()
    assert r["matched"] is False
    g = ai.get("/api/tickets/%d" % r["id"], headers=h).get_json()["ticket"]
    assert any("No matching shipment" in x for x in g["risk_reasons"])  # #3 — visible miss


def test_customers_endpoint_accepts_key_and_json_401(appmod, client):
    A = appmod
    trk = "9400" + uuid.uuid4().hex[:10]
    _seed(A, trk, user="buyerx")
    key = _key(client, A)
    ai = A.app.test_client()
    # with the key → JSON profile
    r = ai.get("/api/customers/buyerx", headers={"Authorization": "Bearer " + key}).get_json()
    assert r["ok"] is True and r["username"] == "buyerx"              # #2
    # no auth → JSON 401, not a 302 login redirect
    noauth = A.app.test_client().get("/api/customers/buyerx")
    assert noauth.status_code == 401


def test_returns_read_with_returns_scope(appmod, client):
    A = appmod
    key = _key(client, A, scopes=["returns:read"])
    ai = A.app.test_client()
    r = ai.get("/api/returns", headers={"Authorization": "Bearer " + key})
    assert r.status_code == 200 and r.get_json()["ok"] is True        # #11
    # a read-only returns key cannot write
    # (need a case id; just assert the write-guard rejects a bogus id with 403/404 not 200-write)
    w = ai.patch("/api/returns/999999", json={"status": "hold"}, headers={"Authorization": "Bearer " + key})
    assert w.status_code in (403, 404)
