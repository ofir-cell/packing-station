"""Cycle-12: data deletion on deauthorization (TikTok/Apple privacy requirement).

- deauth (webhook topic 6) stops access immediately (tokens cleared) + stamps time
- retention purge deletes data for shops deauthorized > TT_DEAUTH_RETENTION_DAYS ago
- buyer PII in materialized shipments is anonymized (operational record kept)
- admin /api/tiktok/forget deletes immediately on request
"""
import json, hmac, hashlib, uuid
from datetime import datetime, timedelta


def _sign(A, body):
    return hmac.new(A.TIKTOK_APP_SECRET.encode(), A.TIKTOK_APP_KEY.encode() + body, hashlib.sha256).hexdigest()


def _put_shop(A, sid, active=1, deauth=None):
    c = A.pdb(); A._tt_shops_ensure(c)
    c.execute("""INSERT OR REPLACE INTO tiktok_shops(org_id,shop_id,active,access_token,refresh_token,shop_cipher,deauthorized_at)
                 VALUES(?,?,?,?,?,?,?)""", (A.DEFAULT_ORG, sid, active, "tok", "ref", "cph", deauth))
    c.commit(); c.close()


def _shop_row(A, sid):
    c = A.pdb()
    r = c.execute("SELECT * FROM tiktok_shops WHERE shop_id=?", (sid,)).fetchone()
    c.close()
    return dict(r) if r else None


def test_deauth_webhook_clears_tokens_and_stamps(appmod, client):
    sid = "S-" + uuid.uuid4().hex[:6]; _put_shop(appmod, sid)
    body = json.dumps({"type": 6, "shop_id": sid}).encode()
    r = client.post("/api/tiktok/webhook", data=body, headers={"Authorization": _sign(appmod, body)})
    assert r.status_code == 200
    row = _shop_row(appmod, sid)
    assert row["active"] == 0
    assert row["access_token"] == "" and row["refresh_token"] == "" and row["shop_cipher"] == ""
    assert row["deauthorized_at"]


def test_purge_deletes_data_and_anonymizes_shipments(appmod, sdb):
    org = appmod.DEFAULT_ORG; sid = "P-" + uuid.uuid4().hex[:6]
    _put_shop(appmod, sid, active=0)
    c = appmod.pdb()
    c.execute("""INSERT INTO tiktok_orders(order_id,org_id,shop_id,status,line_items,create_time,raw,updated_at)
                 VALUES(?,?,?,'AWAITING','[]',0,'{}','now')""", ("O-" + sid, org, sid))
    c.execute("""INSERT INTO tiktok_events(shop_id,org_id,type,order_id,status,payload)
                 VALUES(?,?,1,'O-1','x','{}')""", (sid, org))
    c.commit(); c.close()
    s = sdb()
    pkg = "PKG-" + sid
    s.execute("""INSERT INTO shipments(shipment_id,status,import_batch,buyer_name,address_full,buyer_username,postal_code)
                 VALUES(?,?,'tiktok-api','Jane Doe','1 Main St','jane','19702')""", (pkg, "pending"))
    s.commit(); s.close()

    out = appmod._tt_purge_shop_data(org, sid)
    assert out["orders"] >= 1 and out["events"] >= 1 and out["anonymized"] >= 1
    assert _shop_row(appmod, sid) is None            # shop row dropped
    c = appmod.pdb()
    assert c.execute("SELECT COUNT(*) n FROM tiktok_orders WHERE shop_id=?", (sid,)).fetchone()["n"] == 0
    c.close()
    s = sdb()
    row = s.execute("SELECT buyer_name,address_full,buyer_username,postal_code FROM shipments WHERE shipment_id=?", (pkg,)).fetchone()
    s.close()
    assert row["buyer_name"] is None and row["address_full"] is None and row["buyer_username"] is None and row["postal_code"] is None


def test_retention_purge_only_old_deauthorizations(appmod):
    org = appmod.DEFAULT_ORG
    old_ts = (datetime.now() - timedelta(days=appmod.TT_DEAUTH_RETENTION_DAYS + 5)).isoformat(timespec="seconds")
    new_ts = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    old_sid = "OLD-" + uuid.uuid4().hex[:5]; new_sid = "NEW-" + uuid.uuid4().hex[:5]; act_sid = "ACT-" + uuid.uuid4().hex[:5]
    _put_shop(appmod, old_sid, active=0, deauth=old_ts)
    _put_shop(appmod, new_sid, active=0, deauth=new_ts)
    _put_shop(appmod, act_sid, active=1)
    appmod._tt_retention_purge()
    assert _shop_row(appmod, old_sid) is None          # purged
    assert _shop_row(appmod, new_sid) is not None       # too recent — kept
    assert _shop_row(appmod, act_sid) is not None       # active — kept


def test_forget_endpoint_deletes_now(appmod, admin):
    org = appmod.DEFAULT_ORG; sid = "F-" + uuid.uuid4().hex[:6]
    _put_shop(appmod, sid, active=1)
    c = appmod.pdb()
    c.execute("""INSERT INTO tiktok_orders(order_id,org_id,shop_id,status,line_items,create_time,raw,updated_at)
                 VALUES(?,?,?,'x','[]',0,'{}','now')""", ("FO-" + sid, org, sid))
    c.commit(); c.close()
    r = admin.post("/api/tiktok/forget", json={"shop_id": sid}, headers=admin.csrf)
    assert r.status_code == 200 and r.get_json()["ok"]
    assert _shop_row(appmod, sid) is None
    c = appmod.pdb()
    assert c.execute("SELECT COUNT(*) n FROM tiktok_orders WHERE shop_id=?", (sid,)).fetchone()["n"] == 0
    c.close()


def test_forget_requires_shop_id(appmod, admin):
    r = admin.post("/api/tiktok/forget", json={}, headers=admin.csrf)
    assert r.status_code == 400
