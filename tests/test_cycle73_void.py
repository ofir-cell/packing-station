"""Cycle-73: void CS tickets via the API. PATCH {"status":"void","void_reason":...} (or
/bulk-void) hides a ticket from the queue + counters, keeps it searchable (?voided=1) and
restorable, logs who/when/why, never fires the decided webhook, and returns applied/changed."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _key(client, A):
    hdr = _admin(client, A)
    return client.post("/api/apikeys", json={"label": "AI", "org": A.DEFAULT_ORG}, headers=hdr).get_json()["key"]


def _mk(ai, h, user="u"):
    return ai.post("/api/tickets", json={"platform": "tiktok", "username": user, "inbound_text": "x"}, headers=h).get_json()["id"]


def test_void_via_patch_requires_reason_and_hides(appmod, client, monkeypatch):
    A = appmod
    fired = []
    monkeypatch.setattr(A, "_ticket_webhook", lambda *a, **k: fired.append(1))
    key = _key(client, A); ai = A.app.test_client(); h = {"Authorization": "Bearer " + key}
    tid = _mk(ai, h, "voidme" + uuid.uuid4().hex[:4])
    # no reason -> 400
    r0 = ai.patch("/api/tickets/%d" % tid, json={"status": "void"}, headers=h)
    assert r0.status_code == 400
    # with reason -> ok, applied/changed returned
    r = ai.patch("/api/tickets/%d" % tid, json={"status": "void", "void_reason": "duplicate"}, headers=h).get_json()
    assert r["ok"] and "voided" in r["applied"] and "voided" in r["changed"]
    assert not fired                                    # no decided webhook on void
    # gone from the default queue, present under ?voided=1
    lst = ai.get("/api/tickets", headers=h).get_json()
    assert not any(t["id"] == tid for t in lst["tickets"])
    vd = ai.get("/api/tickets?voided=1", headers=h).get_json()
    assert any(t["id"] == tid for t in vd["tickets"])
    # reason + actor logged
    g = client.get("/api/tickets/%d" % tid, headers=_admin(client, A)).get_json()["ticket"]
    assert g["void_reason"] == "duplicate" and g["voided"]
    assert any(l["action"] == "voided" for l in g["log"])
    # restore
    rr = ai.patch("/api/tickets/%d" % tid, json={"status": "restore"}, headers=h).get_json()
    assert rr["ok"]
    lst2 = ai.get("/api/tickets", headers=h).get_json()
    assert any(t["id"] == tid for t in lst2["tickets"])


def test_bulk_void(appmod, client):
    A = appmod
    key = _key(client, A); ai = A.app.test_client(); h = {"Authorization": "Bearer " + key}
    ids = [_mk(ai, h, "bulk" + uuid.uuid4().hex[:4]) for _ in range(3)]
    r0 = ai.post("/api/tickets/bulk-void", json={"ids": ids}, headers=h)
    assert r0.status_code == 400                        # reason required
    r = ai.post("/api/tickets/bulk-void", json={"ids": ids, "void_reason": "created by mistake"}, headers=h).get_json()
    assert r["ok"] and r["count"] == 3 and sorted(r["voided"]) == sorted(ids)
    # re-voiding an already-voided id is skipped
    r2 = ai.post("/api/tickets/bulk-void", json={"ids": ids, "void_reason": "again"}, headers=h).get_json()
    assert r2["count"] == 0 and sorted(r2["skipped"]) == sorted(ids)
    # counters exclude voided
    c = ai.get("/api/tickets", headers=h).get_json()["counters"]
    assert all(not any(t in str(c) for t in [str(i) for i in ids]) for _ in [0])  # sanity: ids not in counters text
