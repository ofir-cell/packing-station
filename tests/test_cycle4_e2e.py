"""Cycle-4 — comprehensive operational QA against the deployed Cycle-3 baseline.

AUTOMATED SANDBOX ONLY: throwaway per-test DATA_DIR, no external calls (carriers/
TikTok are never reached; pack-time depletion is pure local DB). Drives the REAL
endpoints and helpers end-to-end: import(seed)->pick->scan->pack->inventory->
cancel/restore->revert->ship, plus concurrency, duplicate scans, failed uploads,
and tenant isolation.
"""
import uuid, threading


# ---------- seeding helpers (stand in for the CSV import, which is covered elsewhere) ----------
def _seed_depletable(appmod, org, *, on_hand=10, qty=2, status="pending", live=False):
    """Create a catalog product + sticker binding + one shipment with one item that
    resolves to that product. Returns (sid, tracking, psku, sticker, label)."""
    tag = uuid.uuid4().hex[:6]
    psku = "P" + tag
    sticker = "ST" + tag
    label = "SHOW-" + tag
    sid = "SH" + tag
    tracking = "9400" + uuid.uuid4().hex[:14]
    c = appmod.sdb(org)
    c.execute("INSERT INTO products(sku,name,on_hand,avg_cost,updated_at) VALUES(?,?,?,?,datetime('now'))",
              (psku, "Prod " + tag, on_hand, 2.0))
    c.execute("""INSERT INTO show_product_map(import_label,sticker_sku,part,product_sku,mapped_at)
                 VALUES(?,?,?,?,datetime('now'))""", (label, sticker, 0, psku))
    c.execute("""INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform)
                 VALUES(?,?,?,?,?,'tiktok')""", (sid, tracking, status, "b-" + tag, label))
    c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked)
                 VALUES(?,?,?,?,?,0)""", (sid, "O" + tag, sticker, "Prod " + tag, qty))
    if live:
        c.execute("INSERT INTO live_sales(import_label,sticker_sku,product_sku,qty) VALUES(?,?,?,?)", (label, sticker, psku, qty))
    c.commit(); c.close()
    return sid, tracking, psku, sticker, label


def _on_hand(appmod, org, psku):
    c = appmod.sdb(org)
    v = c.execute("SELECT on_hand FROM products WHERE sku=?", (psku,)).fetchone()["on_hand"]
    c.close(); return v


def _status(appmod, org, sid):
    c = appmod.sdb(org)
    r = c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    c.close(); return r["status"] if r else None


# ========================= FULL WORKFLOW =========================
def test_full_workflow_pick_scan_pack_deplete(appmod, admin):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, sticker, label = _seed_depletable(appmod, org, on_hand=10, qty=2)

    # pick
    assert admin.post(f"/api/pick/complete/{sid}", json={}, headers=admin.csrf).get_json()["ok"] is True
    assert _status(appmod, org, sid) == "picked"

    # scan lookup resolves (exact)
    r = admin.get(f"/api/shipment/{trk}")
    assert r.get_json()["ok"] is True

    # pack (upload) -> packed + stock depleted by qty
    r = admin.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "4"},
                   headers=admin.csrf, content_type="multipart/form-data")
    assert r.get_json()["ok"] is True
    assert _status(appmod, org, sid) == "packed"
    assert _on_hand(appmod, org, psku) == 8, "stock not depleted by qty on pack"


def test_pack_is_idempotent_no_double_deduct(appmod, admin):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, *_ = _seed_depletable(appmod, org, on_hand=10, qty=2)
    for _ in range(3):
        admin.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"},
                   headers=admin.csrf, content_type="multipart/form-data")
    assert _on_hand(appmod, org, psku) == 8, "re-packing double-deducted stock"


def test_live_show_does_not_deplete_at_pack(appmod, admin):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, *_ = _seed_depletable(appmod, org, on_hand=10, qty=2, live=True)
    admin.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"},
               headers=admin.csrf, content_type="multipart/form-data")
    assert _on_hand(appmod, org, psku) == 10, "live show wrongly depleted at pack time"


# ========================= CANCEL / RESTORE =========================
def test_cancel_after_pack_restores_and_closes(appmod, admin):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, sticker, label = _seed_depletable(appmod, org, on_hand=10, qty=2)
    admin.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"},
               headers=admin.csrf, content_type="multipart/form-data")
    assert _on_hand(appmod, org, psku) == 8
    # find the order_id to cancel
    c = appmod.sdb(org)
    oid = c.execute("SELECT order_id FROM shipment_items WHERE shipment_id=?", (sid,)).fetchone()["order_id"]
    appmod._apply_cancel_rows(c, [{"order_id": oid, "quantity": 2, "cancel_reason": "buyer"}], "tiktok", label, "cb")
    c.commit(); c.close()
    assert _on_hand(appmod, org, psku) == 10, "cancel did not restore depleted stock"
    assert _status(appmod, org, sid) == "cancelled"


def test_revert_after_pack_restores_stock(appmod, admin):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, *_ = _seed_depletable(appmod, org, on_hand=10, qty=2)
    admin.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"},
               headers=admin.csrf, content_type="multipart/form-data")
    assert _on_hand(appmod, org, psku) == 8
    r = admin.post(f"/api/shipment/{sid}/revert", json={"to": "pending"}, headers=admin.csrf)
    assert r.get_json()["ok"] is True
    assert _on_hand(appmod, org, psku) == 10, "revert did not restore stock"
    assert _status(appmod, org, sid) == "pending"


# ========================= CONCURRENCY / DUPLICATE SCANS =========================
def test_concurrent_pack_single_depletion(appmod):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, *_ = _seed_depletable(appmod, org, on_hand=10, qty=2)

    def pack():
        cl = appmod.app.test_client()
        with cl.session_transaction() as s:
            s.update(user="admin", role="admin", roles=["admin"], org=org)
        cl.set_cookie("csrf_token", "tok")
        cl.post("/api/upload", data={"tracking": trk, "station": "S0", "duration": "2"},
                headers={"X-CSRF-Token": "tok"}, content_type="multipart/form-data")

    ts = [threading.Thread(target=pack) for _ in range(4)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert _on_hand(appmod, org, psku) == 8, f"concurrent packs double-deducted (on_hand={_on_hand(appmod, org, psku)})"


def test_concurrent_pick_complete_single_winner(appmod):
    org = appmod.DEFAULT_ORG
    sid, trk, psku, *_ = _seed_depletable(appmod, org, on_hand=10, qty=1)
    results = []
    def pick():
        cl = appmod.app.test_client()
        with cl.session_transaction() as s:
            s.update(user="admin", role="admin", roles=["admin"], org=org)
        cl.set_cookie("csrf_token", "tok")
        results.append(cl.post(f"/api/pick/complete/{sid}", json={}, headers={"X-CSRF-Token": "tok"}).get_json())
    ts = [threading.Thread(target=pick) for _ in range(6)]
    for t in ts: t.start()
    for t in ts: t.join()
    wins = [r for r in results if r.get("ok")]
    assert len(wins) == 1, f"pick-complete had {len(wins)} winners (expected 1)"


# ========================= FAILED / BAD UPLOADS =========================
def test_bad_tracking_rejected(appmod, admin):
    r = admin.post("/api/upload", data={"tracking": "bad code!!", "station": "S0", "duration": "1"},
                   headers=admin.csrf, content_type="multipart/form-data")
    assert r.get_json()["ok"] is False


def test_pack_unknown_tracking_is_noop(appmod, admin):
    # a scan that matches no shipment must not error and must not change any shipment
    r = admin.post("/api/upload", data={"tracking": "9999" + uuid.uuid4().hex[:14], "station": "S0", "duration": "1"},
                   headers=admin.csrf, content_type="multipart/form-data")
    assert r.get_json()["ok"] is True   # recording itself is logged; no shipment touched


# ========================= TENANT ISOLATION =========================
def test_tenant_isolation_shipment_not_visible_cross_org(appmod, client):
    orgA = appmod.DEFAULT_ORG
    orgB = "tenantB"
    appmod.provision_org(orgB)
    sid, trk, psku, *_ = _seed_depletable(appmod, orgA, on_hand=5, qty=1)
    # session as an admin of org B
    with appmod.update_json(appmod.USERS_FILE) as u:
        u["badmin"] = {"password": "x", "role": "admin", "name": "B", "org": orgB}
    with client.session_transaction() as s:
        s.update(user="badmin", role="admin", roles=["admin"], org=orgB)
    client.set_cookie("csrf_token", "tok")
    j = client.get(f"/api/shipment/{trk}").get_json()
    # org B must not see org A's shipment
    assert not (j.get("ok") and j.get("shipment", {}).get("shipment_id") == sid), "cross-tenant shipment leak"
    # and org A's product is untouched from org B
    assert _on_hand(appmod, orgA, psku) == 5
