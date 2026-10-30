"""Order history: who opened / ticked / completed / undid / packed an order — so a
manager can see which worker touched an order even when nobody finished picking it."""
import uuid


def _as(client, A, name, role):
    with client.session_transaction() as s:
        s.clear(); s.update(user=name, role=role, roles=[role], name=name, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _mk(A):
    t = uuid.uuid4().hex[:8]; sid = "OH" + t
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("""INSERT INTO shipments(shipment_id,tracking_code,status,buyer_username,buyer_name,import_label,platform,total_items)
                 VALUES(?,?, 'pending', ?, 'Viri', 'Live', 'tiktok', 2)""", (sid, "9400" + t, "viri" + t))
    for sku in ("960", "959"):
        c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) VALUES(?,?,?,?,1)",
                  (sid, "O" + t, sku, "$1 BEAUTY"))
    c.commit()
    ids = [r[0] for r in c.execute("SELECT id FROM shipment_items WHERE shipment_id=? ORDER BY id", (sid,))]
    c.close()
    return sid, "viri" + t, ids


def _events(A, sid):
    c = A.sdb(A.DEFAULT_ORG)
    ev = A._order_events(c, sid); c.close()
    return [(e["actor"], e["action"]) for e in reversed(ev)]


def test_unfinished_pick_still_shows_who_touched_it(appmod, client):
    A = appmod; sid, user, ids = _mk(A)
    h = _as(client, A, "worker3", "picker")
    client.get("/api/pick/" + sid + "?force=1")
    client.get("/api/pick/" + sid + "?force=1")            # refresh: not logged twice
    assert client.post("/api/pick/item/%d/toggle" % ids[0], headers=h).get_json()["ok"]
    ev = _events(A, sid)
    assert ev == [("worker3", "opened"), ("worker3", "item_picked")]
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0] == "pending"
    c.close()
    # visible on the customer card and the Shipments detail
    h2 = _as(client, A, "admin", "admin")
    d = client.get("/api/customers/" + user).get_json()
    assert [e["actor"] for e in d["shipments"][0]["events"]] == ["worker3", "worker3"]
    d = client.get("/api/shipment/" + sid).get_json()
    assert d["events"][0]["action"] == "item_picked" and "#960" in d["events"][0]["detail"]


def test_complete_then_undo_keeps_the_picker_in_history(appmod, client):
    A = appmod; sid, user, ids = _mk(A)
    h = _as(client, A, "worker4", "picker")
    assert client.post("/api/pick/complete/" + sid, headers=h, json={}).get_json()["ok"]
    h = _as(client, A, "admin", "admin")
    assert client.post("/api/shipment/%s/revert" % sid, headers=h, json={"to": "pending"}).get_json()["ok"]
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT picked_by FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0] is None
    ev = A._order_events(c, sid); c.close()
    assert [(e["actor"], e["action"]) for e in reversed(ev)] == [("worker4", "picked"), ("admin", "undo")]
    assert "was picked by worker4" in ev[0]["detail"]


def test_issue_and_resolve_are_logged(appmod, client):
    A = appmod; sid, user, ids = _mk(A)
    h = _as(client, A, "worker5", "picker")
    assert client.post("/api/pick/issue/" + sid, headers=h, json={"reason": "#959 missing"}).get_json()["ok"]
    h = _as(client, A, "cs1", "cs")
    assert client.post("/api/pick/resolve/" + sid, headers=h, json={"action": "retry"}).get_json()["ok"]
    ev = _events(A, sid)
    assert ev[0] == ("worker5", "issue") and ev[1][1] == "resolved"
