"""Cycle-54 (incident fix): the picker's scan path must NEVER make an external barcode lookup.
Those lookups are up to 4 sequential 6s HTTP calls; on a busy live they starved every gunicorn
worker and took the whole app down (all requests 499'd after ~300s while CPU sat near 0). The scan
path now auto-creates an unverified stub product instantly and defers enrichment."""
import uuid


def _worker(client, A):
    with A.update_json(A.USERS_FILE) as uu:
        uu["w1"] = {"password": "x", "role": "worker", "name": "Dana", "org": A.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="w1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="Dana")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _order(A):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "SHP" + uuid.uuid4().hex[:8]
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label) "
              "VALUES(?,'pending','tiktok','tiktok-api','TT Live')", (sid,))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,?,?,1)", (sid, "O" + sid, "465", "BEAUTY Part 1"))
    iid = c.execute("SELECT id FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()["id"]
    c.commit(); c.close()
    return iid


def test_scan_unknown_barcode_never_calls_online(appmod, client, monkeypatch):
    A = appmod; hdr = _worker(client, A)
    iid = _order(A)
    # If the hot scan path ever reaches the online lookup again, fail loudly.
    def _boom(*a, **k):
        raise AssertionError("scan path must not call _barcode_lookup_online (blocks workers)")
    monkeypatch.setattr(A, "_barcode_lookup_online", _boom)

    code = "9" + uuid.uuid4().hex[:11]
    r = client.post("/api/pick/item/%d/scan" % iid, json={"code": code}, headers=hdr).get_json()
    assert r["ok"] is True and r["auto_created"] is True      # stub created instantly, no network
    c = A.sdb(A.DEFAULT_ORG)
    assert c.execute("SELECT COUNT(*) n FROM products WHERE barcode=?", (code,)).fetchone()["n"] == 1
    c.close()


def test_kill_switch_disables_online_lookup(appmod, monkeypatch):
    A = appmod
    monkeypatch.setenv("BARCODE_ONLINE_LOOKUP", "0")
    # even called directly, the online lookup returns None immediately (no HTTP)
    assert A._barcode_lookup_online("0123456789012") is None
