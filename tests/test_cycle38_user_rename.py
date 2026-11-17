"""Cycle-38: admins can rename an employee's display name from the Employee Badges screen
(e.g. a 'Test 1' badge account → the real staff name). Backend /api/users/name updates the
name; the tenant guard blocks renaming another org's user; a blank name is rejected."""


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def test_admin_renames_worker(appmod, client):
    A = appmod; hdr = _admin(client, A)
    with A.update_json(A.USERS_FILE) as uu:
        uu["test1"] = {"password": "x", "role": "worker", "name": "Test 1", "org": A.DEFAULT_ORG}
    r = client.post("/api/users/name", json={"username": "test1", "name": "Edeline E."}, headers=hdr).get_json()
    assert r["ok"] is True and r["name"] == "Edeline E."
    with A.update_json(A.USERS_FILE) as uu:
        assert uu["test1"]["name"] == "Edeline E."


def test_blank_name_rejected(appmod, client):
    A = appmod; hdr = _admin(client, A)
    with A.update_json(A.USERS_FILE) as uu:
        uu["test2"] = {"password": "x", "role": "worker", "name": "Test 2", "org": A.DEFAULT_ORG}
    r = client.post("/api/users/name", json={"username": "test2", "name": "   "}, headers=hdr).get_json()
    assert r["ok"] is False


def test_unknown_user_404(appmod, client):
    A = appmod; hdr = _admin(client, A)
    r = client.post("/api/users/name", json={"username": "nope_zzz", "name": "X"}, headers=hdr)
    assert r.status_code == 404
