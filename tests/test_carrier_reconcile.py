"""Workstream A: safe reconciliation of UNCERTAIN label purchases. Carrier is mocked.
Reconciliation never re-purchases — it only records an authoritative carrier outcome."""
import uuid


def _mk_uncertain(appmod, rid, sid, idem="idemX"):
    c = appmod.sdb(appmod.DEFAULT_ORG); appmod._label_claim_ensure(c)
    c.execute("INSERT INTO label_purchases(rate_id,shipment_id,status,idem_key,created_at,updated_at) VALUES(?,?,'uncertain',?,'n','n')", (rid, sid, idem))
    c.commit(); c.close()


def test_reconcile_found_marks_bought_without_repurchase(appmod, monkeypatch):
    buys = []
    monkeypatch.setattr(appmod, "_ship_buy", lambda *a, **k: buys.append(1))
    monkeypatch.setattr(appmod, "_carrier_label_lookup",
                        lambda rid, idem=None: {"found": True, "tracking": "TK1", "label_url": "L", "cost": 5.0, "carrier": "usps", "service": "priority"})
    rid = "r-" + uuid.uuid4().hex[:6]; _mk_uncertain(appmod, rid, "S1")
    res = appmod._reconcile_label_purchase(appmod.DEFAULT_ORG, rid)
    assert res["status"] == "bought" and res.get("resolved") is True
    assert len(buys) == 0, "reconcile must NEVER re-purchase"
    c = appmod.sdb(appmod.DEFAULT_ORG)
    row = c.execute("SELECT status,tracking FROM label_purchases WHERE rate_id=?", (rid,)).fetchone(); c.close()
    assert row["status"] == "bought" and row["tracking"] == "TK1"


def test_reconcile_not_found_marks_error_retryable(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "_carrier_label_lookup", lambda rid, idem=None: {"found": False})
    rid = "r-" + uuid.uuid4().hex[:6]; _mk_uncertain(appmod, rid, "S2")
    res = appmod._reconcile_label_purchase(appmod.DEFAULT_ORG, rid)
    assert res["status"] == "error" and res.get("retryable") is True


def test_reconcile_unknown_stays_uncertain(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "_carrier_label_lookup", lambda rid, idem=None: {"found": None})
    rid = "r-" + uuid.uuid4().hex[:6]; _mk_uncertain(appmod, rid, "S3")
    res = appmod._reconcile_label_purchase(appmod.DEFAULT_ORG, rid)
    assert res["status"] == "uncertain" and res.get("unresolved") is True


def test_reconcile_never_autoretries_purchase(appmod, monkeypatch):
    buys = []
    monkeypatch.setattr(appmod, "_ship_buy", lambda *a, **k: buys.append(1))
    monkeypatch.setattr(appmod, "_carrier_label_lookup", lambda rid, idem=None: {"found": None})
    rid = "r-" + uuid.uuid4().hex[:6]; _mk_uncertain(appmod, rid, "S4")
    appmod._reconcile_label_purchase(appmod.DEFAULT_ORG, rid)
    assert len(buys) == 0


def test_reconcile_blocked_in_safe_mode(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "STAGING_SAFE", True)   # real _carrier_label_lookup → blocked/unknown
    rid = "r-" + uuid.uuid4().hex[:6]; _mk_uncertain(appmod, rid, "S5")
    res = appmod._reconcile_label_purchase(appmod.DEFAULT_ORG, rid)
    assert res["status"] == "uncertain" and res.get("blocked") is True


def test_reconcile_endpoint_admin_only(client):
    assert client.post("/api/label/reconcile", json={"rate_id": "x"}).status_code != 200
