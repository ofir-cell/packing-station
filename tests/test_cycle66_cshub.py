"""Cycle-66: CS Hub tickets (Phase 1). Scoped API key auth -> AI creates/updates tickets; staff
take + decide; money decisions are owner/manager only; the AI can never decide; a human decision
queues the AI via a webhook. Risk scoring + reopen-on-conversation-key + atomic take."""
import uuid


# Real seeded users (conftest boots the default org): admin + cs1 exist and are active, so they
# pass the session-revocation gate. Map the role we want to a real username.
_USER = {"admin": "admin", "cs": "cs1"}


def _admin(client, A, role="admin"):
    user = _USER.get(role, "admin")
    with client.session_transaction() as s:
        s.update(user=user, role=role, roles=[role], org=A.DEFAULT_ORG, name=user)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _seed_shipment(A, trk, user="janed"):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:8]
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,
                 tracking_code,buyer_username,buyer_name) VALUES(?,'packed','whatnot','b','HERA Live',?,?,?)""",
              (sid, trk, user, "Jane D"))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,revenue) VALUES(?,?,?,?,1,20)",
              (sid, "O-"+trk, "P-A", "Serum A"))
    c.commit(); c.close()
    return sid


def _mint_key(client, A, scopes=None):
    hdr = _admin(client, A)
    body = {"label": "AI test", "org": A.DEFAULT_ORG}
    if scopes is not None:
        body["scopes"] = scopes
    r = client.post("/api/apikeys", json=body, headers=hdr).get_json()
    assert r["ok"] and r["key"].startswith("ghk_")
    return r["key"]


def test_scoped_key_auth_and_create_autofill(appmod, client):
    A = appmod
    key = _mint_key(client, A)
    trk = "9400" + uuid.uuid4().hex[:10]
    _seed_shipment(A, trk)
    ai = A.app.test_client()
    # AI creates a ticket from a customer message, matched by tracking.
    r = ai.post("/api/tickets", json={"tracking": trk, "type": "where_order",
                                      "inbound_text": "where is my order?",
                                      "platform_conversation_key": "wn:hera:janed"},
                headers={"Authorization": "Bearer " + key}).get_json()
    assert r["ok"] and r["id"]
    tid = r["id"]
    g = ai.get("/api/tickets/%d" % tid, headers={"Authorization": "Bearer " + key}).get_json()["ticket"]
    assert g["customer_name"] == "Jane D" and g["platform"] == "whatnot"
    assert g["import_label"] == "HERA Live" and g["shipment_id"]
    assert g["order_id"] == "O-" + trk
    # a bad key is rejected
    bad = ai.get("/api/tickets", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


def test_reopen_on_conversation_key(appmod, client):
    A = appmod
    key = _mint_key(client, A)
    ai = A.app.test_client()
    ck = "tt:peach:" + uuid.uuid4().hex[:6]
    h = {"Authorization": "Bearer " + key}
    tid = ai.post("/api/tickets", json={"platform": "tiktok", "username": "bob",
                                        "inbound_text": "hi", "platform_conversation_key": ck}, headers=h).get_json()["id"]
    # staff marks it done
    hdr = _admin(client, A)
    client.patch("/api/tickets/%d" % tid, json={"status": "done"}, headers=hdr)
    # customer replies on the same conversation -> reopens the SAME ticket
    r2 = ai.post("/api/tickets", json={"platform": "tiktok", "username": "bob",
                                       "inbound_text": "any update?", "platform_conversation_key": ck}, headers=h).get_json()
    assert r2["id"] == tid and r2["reopened"] is True
    g = client.get("/api/tickets/%d" % tid, headers=hdr).get_json()["ticket"]
    assert g["status"] == "customer_replied"


def test_money_gate_and_ai_cannot_decide(appmod, client):
    A = appmod
    key = _mint_key(client, A)
    ai = A.app.test_client()
    tid = ai.post("/api/tickets", json={"platform": "whatnot", "username": "amy", "inbound_text": "refund pls"},
                  headers={"Authorization": "Bearer " + key}).get_json()["id"]
    # AI may not set a decision at all
    rr = ai.patch("/api/tickets/%d" % tid, json={"decision": "full_refund"},
                  headers={"Authorization": "Bearer " + key})
    assert rr.status_code == 403
    # CS staff may NOT do a money decision (limit 0)
    cs = A.app.test_client(); cshdr = _admin(cs, A, role="cs")
    rc = cs.patch("/api/tickets/%d" % tid, json={"decision": "full_refund", "decision_amount": 20}, headers=cshdr)
    assert rc.status_code == 403
    # CS staff CAN do a non-money decision (send a reply)
    ro = cs.patch("/api/tickets/%d" % tid, json={"decision": "send_reply"}, headers=cshdr).get_json()
    assert ro["ok"] is True
    # Owner CAN do the money decision
    adm = A.app.test_client(); ahdr = _admin(adm, A, role="admin")
    ra = adm.patch("/api/tickets/%d" % tid, json={"decision": "full_refund", "decision_amount": 20}, headers=ahdr).get_json()
    assert ra["ok"] is True
    g = adm.get("/api/tickets/%d" % tid, headers=ahdr).get_json()["ticket"]
    assert g["decision"] == "full_refund" and g["status"] == "decided_wait_ai" and g["decided_by"]


def test_decision_fires_webhook(appmod, client, monkeypatch):
    A = appmod
    fired = []
    monkeypatch.setattr(A, "_ticket_webhook", lambda org, ev, t: fired.append((org, ev, t["id"])))
    hdr = _admin(client, A)
    tid = client.post("/api/tickets", json={"platform": "whatnot", "username": "zoe", "inbound_text": "q"},
                      headers=hdr).get_json()["id"]
    client.patch("/api/tickets/%d" % tid, json={"decision": "send_reply"}, headers=hdr)
    assert any(f[1] == "ticket.decided" and f[2] == tid for f in fired)


def test_atomic_take(appmod, client):
    A = appmod
    hdr = _admin(client, A, role="cs")
    tid = client.post("/api/tickets", json={"platform": "tiktok", "username": "kay", "inbound_text": "hi"},
                      headers=hdr).get_json()["id"]
    r1 = client.post("/api/tickets/%d/take" % tid, json={}, headers=hdr).get_json()
    assert r1["ok"] and r1["assigned_to"]
    # a different person can't steal it
    other = A.app.test_client(); ohdr = _admin(other, A, role="admin")
    r2 = other.post("/api/tickets/%d/take" % tid, json={}, headers=ohdr)
    assert r2.status_code == 409


def test_risk_red_on_repeat_refunds(appmod, client):
    A = appmod
    user = "risky" + uuid.uuid4().hex[:5]
    c = A.sdb(A.DEFAULT_ORG)
    for _ in range(3):
        c.execute("""INSERT INTO return_cases(customer_username,status,refund_amount,created_at)
                     VALUES(?,'decided',5,CURRENT_TIMESTAMP)""", (user,))
    c.commit(); c.close()
    hdr = _admin(client, A)
    r = client.post("/api/tickets", json={"platform": "whatnot", "username": user, "inbound_text": "another refund"},
                    headers=hdr).get_json()
    assert r["risk"] == "red"
