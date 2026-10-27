"""Regression tests for the Oct-2026 P0 TikTok fixes (AUDIT_2026-10.md #1-#3)."""
import json, hmac, hashlib, uuid


def _sign(A, body):
    return hmac.new(A.TIKTOK_APP_SECRET.encode(), A.TIKTOK_APP_KEY.encode() + body, hashlib.sha256).hexdigest()


def _shop(A, shop_id):
    c = A.pdb()
    c.execute("INSERT OR REPLACE INTO tiktok_shops(org_id,shop_id,active) VALUES(?,?,1)", (A.DEFAULT_ORG, shop_id))
    c.commit(); c.close()


def _shops(A):
    c = A.pdb()
    r = {x["shop_id"]: x["active"] for x in c.execute("SELECT shop_id,active FROM tiktok_shops")}
    c.close(); return r


# ── #1 webhook ────────────────────────────────────────────────────────────────
def test_unsigned_webhook_cannot_deactivate_shop(appmod, client):
    sid = "S-" + uuid.uuid4().hex[:6]; _shop(appmod, sid)
    r = client.post("/api/tiktok/webhook", data=json.dumps({"type": 6, "shop_id": sid}))
    assert r.status_code == 401
    assert _shops(appmod)[sid] == 1


def test_unsigned_webhook_cannot_remap_shop_id(appmod, client):
    before = _shops(appmod)
    r = client.post("/api/tiktok/webhook", data=json.dumps({"type": 1, "shop_id": "EVIL", "data": {"order_id": "1"}}))
    assert r.status_code == 401
    assert _shops(appmod) == before and "EVIL" not in _shops(appmod)


def test_signed_unknown_shop_is_ignored_not_adopted(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "_tt_valid_token", lambda *a, **k: None)
    before = _shops(appmod)
    body = json.dumps({"type": 1, "shop_id": "NEW-" + uuid.uuid4().hex[:6], "data": {"order_id": "1"}}).encode()
    r = client.post("/api/tiktok/webhook", data=body, headers={"Authorization": _sign(appmod, body)})
    assert r.status_code == 200
    assert _shops(appmod) == before


def test_signed_deauth_still_works(appmod, client):
    sid = "S-" + uuid.uuid4().hex[:6]; _shop(appmod, sid)
    body = json.dumps({"type": 6, "shop_id": sid}).encode()
    r = client.post("/api/tiktok/webhook", data=body, headers={"Authorization": _sign(appmod, body)})
    assert r.status_code == 200
    assert _shops(appmod)[sid] == 0


# ── #2 sweep keeps local progress ─────────────────────────────────────────────
def _mk(c, sid, status, label="Old Show"):
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'tiktok-api',?,'tiktok')",
              (sid, status, label))
    c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked,depleted_qty,depleted_sku)
                 VALUES(?,?,'S1','Lip',1,1,1,'S1')""", (sid, "O" + sid))


def _order(sid, status="AWAITING_SHIPMENT"):
    return {"id": "O" + sid, "status": status, "packages": [{"id": sid}],
            "line_items": [{"id": "L", "seller_sku": "S1", "sku_id": "S1", "product_name": "Lip",
                            "sale_price": "5", "package_id": sid}],
            "recipient_address": {"full_address": "1 Main"}}


def test_sweep_does_not_reset_progress(appmod, sdb):
    c = sdb(); tag = uuid.uuid4().hex[:5]
    cases = {"picked": "picked", "issue": "issue", "packed": "packed", "pending": "pending", "cancelled": "cancelled"}
    for st in cases: _mk(c, f"{st}-{tag}", st)
    c.commit()
    for st in cases: appmod._tt_apply_order(c, _order(f"{st}-{tag}"), label="New Show")
    c.commit()
    got = {st: c.execute("SELECT status FROM shipments WHERE shipment_id=?", (f"{st}-{tag}",)).fetchone()[0] for st in cases}
    c.close()
    assert got == cases


def test_tiktok_cancel_still_overrides(appmod, sdb):
    c = sdb(); sid = "pk-" + uuid.uuid4().hex[:5]
    _mk(c, sid, "packed"); c.commit()
    appmod._tt_apply_order(c, _order(sid, "CANCELLED"), label="X"); c.commit()
    assert c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()[0] == "cancelled"
    c.close()


# ── #3 regroup is non-destructive ─────────────────────────────────────────────
def test_regroup_keeps_status_items_and_restores_labels(appmod, admin, sdb, monkeypatch):
    c = sdb(); tag = uuid.uuid4().hex[:5]
    a, b = f"rgA-{tag}", f"rgB-{tag}"
    _mk(c, a, "packed"); _mk(c, b, "picked"); c.commit(); c.close()

    def fake_pull(org, days=30):          # re-pull only reaches shipment A
        s = sdb()
        s.execute("UPDATE shipments SET import_label=COALESCE(import_label,'Live New') WHERE shipment_id=?", (a,))
        s.commit(); s.close()
        return {"ok": True, "shows": ["Live New"]}
    monkeypatch.setattr(appmod, "_tt_pull_core", fake_pull)

    r = admin.post("/api/tiktok/regroup", json={"days": 45}, headers=admin.csrf)
    assert r.status_code == 200 and r.get_json()["ok"]
    c = sdb()
    rows = {x["shipment_id"]: (x["status"], x["import_label"]) for x in
            c.execute("SELECT shipment_id,status,import_label FROM shipments WHERE shipment_id IN (?,?)", (a, b))}
    items = c.execute("SELECT COUNT(*), SUM(depleted_qty) FROM shipment_items WHERE shipment_id IN (?,?)", (a, b)).fetchone()
    c.close()
    assert rows[a] == ("packed", "Live New")
    assert rows[b] == ("picked", "Old Show")     # not reached → old label restored
    assert tuple(items) == (2, 2)                # items + depletion untouched
