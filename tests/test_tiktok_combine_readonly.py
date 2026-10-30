"""Combine & Labels, stage A (read-only): list what TikTok says can be combined, joined
with our own pick/pack status. TikTok is replaced by a fake; the key guarantee tested
here is that this stage only ever READS from TikTok.
"""
import time, uuid

import pytest

MY_SHOP = "SHOP-COMBINE"


class FakeTT:
    def __init__(self, pages):
        self.pages, self.calls = pages, []      # pages: list of (groups, next_token)

    def request(self, method, url, params=None, body=None, **kw):
        self.calls.append((method, url, dict(params or {}), body))
        if "combinable_packages" in url:
            i = 0 if not (params or {}).get("page_token") else int(params["page_token"])
            groups, nxt = self.pages[i]
            return {"code": 0, "data": {"combinable_packages": groups, "next_page_token": nxt}}
        return {"code": 0, "data": {}}


@pytest.fixture
def shop(appmod, monkeypatch):
    A = appmod
    c = A.pdb()
    c.execute("INSERT OR REPLACE INTO tiktok_shops(org_id,shop_id,shop_name,active,granted_scopes) VALUES(?,?,?,1,?)",
              (A.DEFAULT_ORG, MY_SHOP, "Peach Beauty", "seller.order.info,seller.fulfillment.basic"))
    c.commit(); c.close()
    monkeypatch.setattr(A, "_tiktok_ready", lambda: True)
    # only OUR shop has a token; other shops left behind by other tests report an error
    monkeypatch.setattr(A, "_tt_valid_token", lambda org, sid: {"access_token": "t", "shop_cipher": "c"} if sid == MY_SHOP else None)
    monkeypatch.setattr(A, "_tt_ensure_cipher", lambda org, sid, tok: tok)
    yield
    c = A.pdb(); c.execute("DELETE FROM tiktok_shops WHERE shop_id=?", (MY_SHOP,)); c.commit(); c.close()


def _as(client, A, user="admin", role="admin"):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)


def _order_in_app(A, oid, pkg, buyer, status="pending"):
    c = A.sdb(A.DEFAULT_ORG)
    A._tt_apply_order(c, {"id": oid, "status": "AWAITING_SHIPMENT", "buyer_nickname": buyer,
                          "create_time": int(time.time()), "packages": [{"id": pkg}],
                          "recipient_address": {"full_address": "1 Main", "name": buyer},
                          "line_items": [{"id": "L", "seller_sku": "9", "sku_id": "9", "product_name": "Live PART 1",
                                          "sale_price": "5", "package_id": pkg}]}, label="Combine Show")
    if status != "pending":
        c.execute("UPDATE shipments SET status=? WHERE shipment_id=?", (status, pkg))
    c.commit(); c.close()


def _mine(d):
    return [g for g in d["groups"] if g.get("shop_id") == MY_SHOP]


def test_lists_combinable_groups_with_our_status(appmod, client, shop, monkeypatch):
    A = appmod
    t = uuid.uuid4().hex[:6]
    _order_in_app(A, "O1" + t, "P1" + t, "amy")
    _order_in_app(A, "O2" + t, "P2" + t, "amy")
    fake = FakeTT([([{"id": "CG" + t, "order_ids": ["O1" + t, "O2" + t]}], "")])
    monkeypatch.setattr(A, "_tt_request", fake.request)
    _as(client, A)
    d = client.get("/api/tiktok/combinable").get_json()
    g = _mine(d)
    assert len(g) == 1 and g[0]["buyer"] == "amy"
    assert g[0]["packages"] == sorted(["P1" + t, "P2" + t])
    assert g[0]["already_handled"] is False and g[0]["missing_in_app"] == 0
    assert d["write_enabled"] is False                              # locked by default


def test_stage_a_only_ever_reads_from_tiktok(appmod, client, shop, monkeypatch):
    A = appmod
    fake = FakeTT([([{"id": "X", "order_ids": ["NOPE"]}], "")])
    monkeypatch.setattr(A, "_tt_request", fake.request)
    _as(client, A)
    client.get("/api/tiktok/combinable")
    client.get("/api/tiktok/combinable?raw=1")
    assert fake.calls and all(m == "GET" and b is None for m, u, p, b in fake.calls)


def test_flags_orders_already_picked_and_orders_not_in_app(appmod, client, shop, monkeypatch):
    A = appmod
    t = uuid.uuid4().hex[:6]
    _order_in_app(A, "O1" + t, "P1" + t, "bob", status="picked")
    fake = FakeTT([([{"id": "CG" + t, "order_ids": ["O1" + t, "GHOST" + t]}], "")])
    monkeypatch.setattr(A, "_tt_request", fake.request)
    _as(client, A)
    g = _mine(client.get("/api/tiktok/combinable").get_json())[0]
    assert g["already_handled"] is True and g["missing_in_app"] == 1


def test_follows_pagination(appmod, client, shop, monkeypatch):
    A = appmod
    fake = FakeTT([([{"id": "A", "order_ids": ["a1", "a2"]}], "1"),
                   ([{"id": "B", "order_ids": ["b1", "b2"]}], "")])
    monkeypatch.setattr(A, "_tt_request", fake.request)
    _as(client, A)
    assert sorted(g["id"] for g in _mine(client.get("/api/tiktok/combinable").get_json())) == ["A", "B"]


def test_tiktok_error_is_shown_per_shop(appmod, client, shop, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_tt_request", lambda *a, **k: {"code": 105005, "message": "access denied"})
    _as(client, A)
    d = client.get("/api/tiktok/combinable").get_json()
    mine = [s for s in d["shops"] if s["shop_id"] == MY_SHOP][0]
    assert "105005" in mine["error"] and _mine(d) == []


def test_reports_fulfillment_permission(appmod, client, shop, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_tt_request", FakeTT([([], "")]).request)
    _as(client, A)
    mine = [s for s in client.get("/api/tiktok/combinable").get_json()["shops"] if s["shop_id"] == MY_SHOP][0]
    assert mine["has_fulfillment_scope"] is True
    c = A.pdb(); c.execute("UPDATE tiktok_shops SET granted_scopes='seller.order.info' WHERE shop_id=?", (MY_SHOP,)); c.commit(); c.close()
    mine = [s for s in client.get("/api/tiktok/combinable").get_json()["shops"] if s["shop_id"] == MY_SHOP][0]
    assert mine["has_fulfillment_scope"] is False


def test_raw_response_is_admin_only(appmod, client, shop, monkeypatch):
    A = appmod
    monkeypatch.setattr(A, "_tt_request", FakeTT([([], "")]).request)
    _as(client, A, "admin", "admin")
    assert "raw_first" in client.get("/api/tiktok/combinable?raw=1").get_json()
    _as(client, A, "cs1", "cs")
    assert "raw_first" not in client.get("/api/tiktok/combinable?raw=1").get_json()


def test_screen_is_for_admin_and_cs(appmod, client):
    A = appmod
    _as(client, A, "cs1", "cs")
    r = client.get("/admin/combine")
    assert r.status_code == 200 and b"Combine &amp; Labels" in r.data
    _as(client, A, "worker1", "worker")
    assert client.get("/admin/combine").status_code in (302, 401, 403)
    assert client.get("/api/tiktok/combinable").status_code in (302, 401, 403)
