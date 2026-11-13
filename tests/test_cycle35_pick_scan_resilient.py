"""Cycle-35: scanning a label in Picking must never hang silently. The scan chain had
no error handling, so any 500 (e.g. a hiccup computing the cleanup gate) left the scan
frozen — "doesn't finish, doesn't load the order". Server side: a cleanup-gate error no
longer 500s the whole pick detail; the order still loads so the floor keeps working."""
import uuid


def _worker(client, A):
    with A.update_json(A.USERS_FILE) as uu:
        uu["w1"] = {"password": "x", "role": "worker", "name": "Dana", "org": A.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="w1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Dana")
    client.set_cookie("csrf_token", "tok")


def _order(A, sid, label="TT Live Scan", trk=None):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code,buyer_name) "
              "VALUES(?,?,'tiktok','tiktok-api',?,?,?)", (sid, "pending", label, trk, "Jane"))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,'996','$1 BEAUTY Part 1',1)", (sid, "OA" + sid))
    c.commit(); c.close()


def test_pick_detail_survives_cleanup_gate_error(appmod, client, monkeypatch):
    A = appmod; _worker(client, A)
    sid = "SHP" + uuid.uuid4().hex[:6]
    _order(A, sid)

    def boom(_label):
        raise RuntimeError("cleanup gate blew up")
    monkeypatch.setattr(A, "_cleanup_progress", boom)

    r = client.get("/api/pick/" + sid)
    assert r.status_code == 200                      # NOT a 500 → no silent hang
    d = r.get_json()
    assert d["ok"] is True                           # the order still loads
    assert len(d["items"]) == 1
    assert d["cleanup_blocked"] is False             # gate failed open, picking proceeds


def test_scan_by_tracking_resolves_through_shipment_lookup(appmod, client):
    """The real scan path: /api/pick/<tracking> misses (it's not a shipment_id), the UI
    falls back to /api/shipment/<tracking>, which resolves the order by its label."""
    A = appmod; _worker(client, A)
    sid = "SHP" + uuid.uuid4().hex[:6]
    trk = "9218" + uuid.uuid4().hex[:14]
    _order(A, sid, trk=trk)

    assert client.get("/api/pick/" + trk).get_json()["ok"] is False     # tracking != shipment_id
    look = client.get("/api/shipment/" + trk).get_json()                # fallback
    assert look["ok"] is True and look["shipment"]["shipment_id"] == sid
    det = client.get("/api/pick/" + sid).get_json()                     # then open detail
    assert det["ok"] is True and len(det["items"]) == 1
