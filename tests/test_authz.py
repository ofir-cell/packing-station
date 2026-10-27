"""Workstream C/Security (P0): user-management authorization — no manager->admin escalation.
Enforced server-side via req_true_admin (handler-level, not route-prefix alone)."""
import uuid


def _login(client, appmod, role):
    with client.session_transaction() as s:
        s.update(user=role[:4] + uuid.uuid4().hex[:3], role=role, roles=[role], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def test_unauthenticated_not_allowed(client):
    assert client.get("/api/users").status_code != 200


def test_worker_forbidden_from_users(client, appmod):
    _login(client, appmod, "worker")
    assert client.get("/api/users").status_code == 403


def test_manager_cannot_list_users(client, appmod):
    # the escalation: manager must NOT be elevated to admin on user management
    _login(client, appmod, "manager")
    assert client.get("/api/users").status_code == 403


def test_manager_cannot_mutate_user_or_permission_routes(client, appmod):
    hdr = _login(client, appmod, "manager")
    for path in ("/api/users/add", "/api/users/roles", "/api/users/name", "/api/users/delete",
                 "/api/users/pw", "/api/users/badge", "/api/users/badge/revoke",
                 "/api/permissions", "/api/permissions/pin"):
        r = client.post(path, json={}, headers=hdr)
        assert r.status_code == 403, f"{path} allowed a manager ({r.status_code})"


def test_admin_can_list_users(client, appmod):
    _login(client, appmod, "admin")
    assert client.get("/api/users").status_code == 200   # legitimate admin workflow preserved


def test_admin_not_forbidden_on_user_mutation(client, appmod):
    hdr = _login(client, appmod, "admin")
    # authz must pass for a true admin (body may be incomplete -> not 403)
    assert client.post("/api/users/add", json={"username": "zzz" + uuid.uuid4().hex[:4], "role": "worker"}, headers=hdr).status_code != 403
