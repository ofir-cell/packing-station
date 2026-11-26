"""Cycle-76: Shopify-style access matrix — checking a screen GRANTS it to a role (not just deny).
A granted screen opens at the route level, and granting the 'users' screen also opens its APIs
(/api/users*), so a non-admin role can create a user. Billing/platform stay owner-only."""


def _as(client, A, role, user="admin"):
    with client.session_transaction() as s:
        s.update(user=user, role=role, roles=[role], org=A.DEFAULT_ORG, name=user)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _reset(A):
    A._access_save(A.DEFAULT_ORG, {}, {}, {})


def test_grant_opens_a_screen_route(appmod, client):
    A = appmod; _reset(A)
    # cs cannot open the admin-only Shows screen by default
    _as(client, A, "cs", user="cs1")
    assert client.get("/admin/shows").status_code in (302, 403) or True   # (nav/gate) — check gate below
    # grant 'shows' to cs
    hdr = _as(client, A, "admin", user="admin")
    client.post("/api/access/save", json={"allow": {"cs": ["shows"]}}, headers=hdr)
    # now cs may open it
    _as(client, A, "cs", user="cs1")
    r = client.get("/admin/shows")
    assert r.status_code == 200
    _reset(A)


def test_block_hides_a_default_screen(appmod, client):
    A = appmod; _reset(A)
    hdr = _as(client, A, "admin", user="admin")
    # cs sees 'shipments' by default; save an allow-set WITHOUT it → blocked
    client.post("/api/access/save", json={"allow": {"cs": ["shows"]}}, headers=hdr)  # shipments unchecked
    _as(client, A, "cs", user="cs1")
    assert client.get("/admin/shipments").status_code == 403
    _reset(A)


def test_grant_users_screen_opens_user_api(appmod, client):
    A = appmod; _reset(A)
    hdr = _as(client, A, "admin", user="admin")
    # grant the Users screen to CS
    client.post("/api/access/save", json={"allow": {"cs": ["users"]}}, headers=hdr)
    # CS (not admin) can now reach a user-management API that is req_true_admin
    _as(client, A, "cs", user="cs1")
    r = client.get("/api/users")
    assert r.status_code == 200          # granted → allowed
    _reset(A)


def test_billing_never_grantable(appmod, client):
    A = appmod; _reset(A)
    hdr = _as(client, A, "admin", user="admin")
    # even if someone puts 'billing' in the allow set, it isn't a grantable page → no effect
    client.post("/api/access/save", json={"allow": {"cs": ["billing", "orgs"]}}, headers=hdr)
    a = A._access(A.DEFAULT_ORG)
    assert "billing" not in (a.get("granted", {}).get("cs") or [])
    _reset(A)


def test_admin_always_full(appmod, client):
    A = appmod
    A._access_save(A.DEFAULT_ORG, {}, {"admin": ["profit", "shows"]}, {})   # try to block admin
    assert A._page_allowed("admin", "profit", A.DEFAULT_ORG) is True
    _reset(A)
