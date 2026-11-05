"""Cycle-25: cost / COGS / profit are ADMIN-ONLY across the API. Non-admin roles
(cs, worker, picker) must never receive product cost, per-product COGS, total COGS,
or profit — while admins still get them. Covers the four leaks found in the audit:
/api/live/scan, /api/live/summary, /api/live/undo, /api/receive."""
import uuid


def _as(client, A, role, name=None):
    uname = (name or role) + "_u"
    with A.update_json(A.USERS_FILE) as users:
        u = dict(users.get(uname) or {})
        u.update({"password": u.get("password", "x"), "role": role, "name": name or role.title(), "org": A.DEFAULT_ORG})
        users[uname] = u
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=A.DEFAULT_ORG, name=name or role.title())
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _prod(A, sku, cost=3.5, target=12.0, on_hand=50):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,on_hand,avg_cost,target_price) VALUES(?,?,?,?,?,?)",
              (sku, "P-" + sku, "BC" + sku, on_hand, cost, target))
    c.commit(); c.close()


def test_receive_hides_cost_from_cs(appmod, client):
    A = appmod; sku = "RC" + uuid.uuid4().hex[:5]; _prod(A, sku)
    body = {"sku": sku, "qty": 5, "unit_cost": 4.0}
    r_cs = client.post("/api/receive", json=body, headers=_as(client, A, "cs")).get_json()
    assert r_cs["ok"] and "avg_cost" not in r_cs            # cs: no cost
    r_ad = client.post("/api/receive", json=body, headers=_as(client, A, "admin")).get_json()
    assert r_ad["ok"] and "avg_cost" in r_ad                # admin: cost present


def _scan(client, hdr, show, sku):
    return client.post("/api/live/scan", json={"show": show, "sticker": "1", "part": 1, "code": "BC" + sku, "qty": 1, "price": 10},
                       headers=hdr).get_json()


def test_live_scan_hides_cost_and_profit_from_worker(appmod, client):
    A = appmod; sku = "LS" + uuid.uuid4().hex[:5]; _prod(A, sku); show = "L" + uuid.uuid4().hex[:5]
    w = _scan(client, _as(client, A, "worker"), show, sku)
    assert w["ok"]
    assert "unit_cost" not in w["product"]                  # no per-unit cost
    assert "cogs" not in w["totals"] and "profit" not in w["totals"]   # no COGS/profit
    assert all("cogs" not in p for p in w["totals"]["products"])       # nor per-product COGS
    assert "revenue" in w["totals"]                         # revenue is fine
    # admin sees everything
    a = _scan(client, _as(client, A, "admin"), show, sku)
    assert a["product"]["unit_cost"] is not None and "cogs" in a["totals"] and "profit" in a["totals"]


def test_live_summary_and_undo_hide_profit(appmod, client):
    A = appmod; sku = "SU" + uuid.uuid4().hex[:5]; _prod(A, sku); show = "L" + uuid.uuid4().hex[:5]
    _scan(client, _as(client, A, "admin"), show, sku)       # seed a sale
    wh = _as(client, A, "picker")
    s = client.get("/api/live/summary?show=" + show, headers=wh).get_json()
    assert s["ok"] and "cogs" not in s["totals"] and "profit" not in s["totals"]
    u = client.post("/api/live/undo", json={"show": show}, headers=wh).get_json()
    assert u["ok"] and "cogs" not in u["totals"] and "profit" not in u["totals"]
    # admin summary keeps them
    sa = client.get("/api/live/summary?show=" + show, headers=_as(client, A, "admin")).get_json()
    assert "cogs" in sa["totals"] and "profit" in sa["totals"]
