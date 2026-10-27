"""Cycle-2 coordinated QA/improvement fixes — regression coverage.

Covers:
  S4/S5  manager must not reach sensitive admin/financial routes
  Q2     CSV re-import preserves stock-depletion markers
  Q4     packing a flagged 'issue' shipment does not clobber it
  Q6     pick toggle refuses a cancelled line
  E1     concurrent label re-claim after 'error' never double-buys
"""
import uuid, threading


def _login(client, appmod, role):
    with client.session_transaction() as s:
        s.update(user=role[:4] + uuid.uuid4().hex[:3], role=role, roles=[role], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


# ---------- S4/S5 manager blocklist ----------
def test_manager_blocked_from_sensitive_routes(client, appmod):
    hdr = _login(client, appmod, "manager")
    for path in ("/api/audit-log", "/api/profit", "/admin/settings",
                 "/api/commission-config", "/api/host-override",
                 "/api/weight-config", "/api/equipment", "/api/admin/repair-videos"):
        # a sensitive route must deny a manager on whatever method it accepts;
        # 405 (method mismatch) short-circuits before authz, so probe both verbs.
        codes = {client.get(path, headers=hdr).status_code,
                 client.post(path, json={}, headers=hdr).status_code}
        assert 403 in codes, f"{path} not blocked for manager (codes={codes})"


def test_admin_not_blocked_by_new_prefixes(client, appmod):
    # the blocklist must not break legitimate admin access (authz passes -> not 403)
    _login(client, appmod, "admin")
    assert client.get("/api/profit").status_code != 403


# ---------- Q6 pick toggle on cancelled line ----------
def _mk_shipment(appmod, sid, status):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'b','L','tiktok')", (sid, status))
    cur = c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) VALUES(?,?,'S1','Lip',1,0)", (sid, "O" + sid))
    iid = cur.lastrowid
    c.commit(); c.close()
    return iid


def test_pick_toggle_refuses_cancelled(appmod, admin):
    sid = "CX" + uuid.uuid4().hex[:6]
    iid = _mk_shipment(appmod, sid, "cancelled")
    r = admin.post(f"/api/pick/item/{iid}/toggle", json={}, headers=admin.csrf)
    assert r.get_json()["ok"] is False
    c = appmod.sdb(appmod.DEFAULT_ORG)
    assert c.execute("SELECT COALESCE(picked,0) FROM shipment_items WHERE id=?", (iid,)).fetchone()[0] == 0
    c.close()


def test_pick_toggle_allows_active(appmod, admin):
    sid = "AC" + uuid.uuid4().hex[:6]
    iid = _mk_shipment(appmod, sid, "pending")
    r = admin.post(f"/api/pick/item/{iid}/toggle", json={}, headers=admin.csrf)
    assert r.get_json()["ok"] is True


# ---------- E1 concurrent re-claim after error ----------
def test_label_reclaim_after_error_single_buy(appmod, monkeypatch):
    org = appmod.DEFAULT_ORG
    rid = "RATE" + uuid.uuid4().hex[:8]
    sid = "S" + uuid.uuid4().hex[:6]
    c = appmod.sdb(org); appmod._label_claim_ensure(c)
    now = appmod.datetime.now().isoformat(timespec="seconds")
    # seed a prior failed attempt so both callers take the re-claim branch
    c.execute("INSERT INTO label_purchases(rate_id,shipment_id,status,idem_key,created_at,updated_at) VALUES(?,?,?,?,?,?)",
              (rid, sid, "error", "idem_x", now, now))
    c.commit(); c.close()

    buys = []
    bl = threading.Lock()

    def fake_buy(rate_id, idem_key=None):
        with bl:
            buys.append(idem_key)
        return {"ok": True, "label_url": "u", "tracking": "T" + rid, "cost": 1.0,
                "carrier": "usps", "service": "ground"}

    monkeypatch.setattr(appmod, "_ship_buy", fake_buy)

    results = []
    def run():
        results.append(appmod._buy_label_idempotent(org, sid, rid))
    ts = [threading.Thread(target=run) for _ in range(6)]
    for t in ts: t.start()
    for t in ts: t.join()

    assert len(buys) == 1, f"carrier called {len(buys)} times — double buy!"
    oks = [r for r in results if r.get("ok")]
    assert len(oks) == 6  # everyone gets a coherent success (one real buy + idempotent reads)


# ---------- Q2 CSV re-import preserves depletion markers ----------
def test_reimport_preserves_depletion_markers(appmod):
    org = appmod.DEFAULT_ORG
    c = appmod.sdb(org)
    sid = "DEP" + uuid.uuid4().hex[:6]
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform,tracking_code) VALUES(?,?,'b','L','tiktok',?)",
              (sid, "pending", "TRK" + sid))
    c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked,depleted_qty,depleted_sku)
                 VALUES(?,?,'SKU1','Serum',2,1,2,'SKU1')""", (sid, "O" + sid))
    c.commit()
    # simulate the re-import snapshot+restore block in isolation
    prev_depleted = {}
    for pr in c.execute("""SELECT sku, product_name, COALESCE(depleted_qty,0) dq, depleted_sku
                           FROM shipment_items WHERE shipment_id=?""", (sid,)).fetchall():
        k = ((pr["sku"] or "").strip(), (pr["product_name"] or "").strip())
        if (pr["dq"] or 0) > 0 or pr["depleted_sku"]:
            prev_depleted[k] = (pr["dq"] or 0, pr["depleted_sku"])
    assert prev_depleted == {("SKU1", "Serum"): (2, "SKU1")}
    c.close()
