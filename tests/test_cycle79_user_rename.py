"""Cycle-79: editing a user's display name keeps their login username in sync (slug of the name).
Admin is never renamed; collisions get a numeric suffix; the user's data moves to the new handle."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _mk_user(A, uname, name, role="worker"):
    import app as _A
    with _A.update_json(_A.USERS_FILE) as users:
        users[uname] = {"name": name, "role": role, "org": A.DEFAULT_ORG, "pw": "x"}


def test_name_edit_renames_username(appmod, client):
    A = appmod; hdr = _admin(client, A)
    u = "w" + uuid.uuid4().hex[:6]
    _mk_user(A, u, "Old Name")
    r = client.post("/api/users/name", json={"username": u, "name": "Claudia"}, headers=hdr).get_json()
    assert r["ok"] and r["renamed"] is True and r["username"] == "claudia" or r["username"].startswith("claudia")
    import app as _A
    users = _A.ldj(_A.USERS_FILE)
    assert u not in users                       # old handle gone
    assert r["username"] in users and users[r["username"]]["name"] == "Claudia"


def test_admin_is_never_renamed(appmod, client):
    A = appmod; hdr = _admin(client, A)
    r = client.post("/api/users/name", json={"username": "admin", "name": "Big Boss"}, headers=hdr).get_json()
    assert r["ok"] and r["renamed"] is False and r["username"] == "admin"
    import app as _A
    assert _A.ldj(_A.USERS_FILE)["admin"]["name"] == "Big Boss"


def test_collision_gets_suffix(appmod, client):
    A = appmod; hdr = _admin(client, A)
    import app as _A
    # an existing 'maria'
    _mk_user(A, "maria", "Maria One")
    u = "w" + uuid.uuid4().hex[:6]
    _mk_user(A, u, "x")
    r = client.post("/api/users/name", json={"username": u, "name": "Maria"}, headers=hdr).get_json()
    assert r["ok"] and r["renamed"] is True and r["username"] != "maria"   # suffixed, no clobber
    users = _A.ldj(_A.USERS_FILE)
    assert users["maria"]["name"] == "Maria One"   # original untouched
