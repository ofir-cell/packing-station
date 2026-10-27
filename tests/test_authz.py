"""Workstream C (P0): authorization gates and escalation coverage."""
import uuid, pytest


def test_worker_forbidden_from_admin_endpoint(client, appmod):
    with client.session_transaction() as s:
        s.update(user="w", role="worker", roles=["worker"], org=appmod.DEFAULT_ORG)
    assert client.get("/api/users").status_code == 403


def test_unauthenticated_not_allowed(client):
    assert client.get("/api/users").status_code != 200   # redirect to login / 401


@pytest.mark.xfail(reason="AUDIT #7: manager is NOT blocked from /api/users — escalation gap; "
                          "Engineering fix: add '/api/users' to _MANAGER_BLOCK_PREFIXES",
                   strict=False)
def test_manager_cannot_reach_user_admin(client, appmod):
    with client.session_transaction() as s:
        s.update(user="m", role="manager", roles=["manager"], org=appmod.DEFAULT_ORG)
    assert client.get("/api/users").status_code == 403   # SHOULD be blocked
