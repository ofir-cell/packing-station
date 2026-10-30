"""Cycle-13: self-serve account deletion (Apple App Store requirement + data-subject right)."""
import os, uuid


def _add_user(A, uname, role="worker", org=None):
    with A.update_json(A.USERS_FILE) as users:
        users[uname] = {"password": "x", "role": role, "name": uname, "org": (org or A.DEFAULT_ORG)}


def _exists(A, uname):
    with A.update_json(A.USERS_FILE) as users:
        return uname in users


def _sess(client, A, uname, role="worker", org=None):
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=(org or A.DEFAULT_ORG), name=uname)
    client.set_cookie("csrf_token", "tok")
    client.csrf = {"X-CSRF-Token": "tok"}
    return client


def test_delete_own_worker_account(appmod, client):
    uname = "tmpw_" + uuid.uuid4().hex[:6]; _add_user(appmod, uname, "worker")
    _sess(client, appmod, uname, "worker")
    r = client.post("/api/account/delete", json={}, headers=client.csrf)
    assert r.status_code == 200 and r.get_json()["ok"]
    assert not _exists(appmod, uname)


def test_last_admin_requires_org_confirm(appmod, client):
    org = "torg_" + uuid.uuid4().hex[:6]; uname = "tmpa_" + uuid.uuid4().hex[:6]
    _add_user(appmod, uname, "admin", org=org)
    _sess(client, appmod, uname, "admin", org=org)
    r = client.post("/api/account/delete", json={}, headers=client.csrf)
    assert r.status_code == 409 and r.get_json().get("need_org_confirm")
    assert _exists(appmod, uname)          # not deleted without confirmation


def test_last_admin_wipe_org(appmod, client):
    org = "torg_" + uuid.uuid4().hex[:6]; uname = "tmpa_" + uuid.uuid4().hex[:6]
    _add_user(appmod, uname, "admin", org=org)
    d = appmod.org_path(org); os.makedirs(d, exist_ok=True); open(os.path.join(d, "marker.txt"), "w").close()
    _sess(client, appmod, uname, "admin", org=org)
    r = client.post("/api/account/delete", json={"wipe_org": True}, headers=client.csrf)
    j = r.get_json()
    assert r.status_code == 200 and j["ok"] and j["org_deleted"]
    assert not _exists(appmod, uname)
    assert not os.path.isdir(d)            # org folder removed


def test_delete_requires_login(appmod, client):
    r = client.post("/api/account/delete", json={})
    assert r.status_code in (301, 302, 401, 403)


def test_me_page_renders_delete_control(appmod, client):
    """The /me profile page must expose the self-serve delete control and
    post to /api/account/delete (completes the Apple in-app deletion loop)."""
    uname = "tmpu_" + uuid.uuid4().hex[:6]; _add_user(appmod, uname, "worker")
    _sess(client, appmod, uname, "worker")
    r = client.get("/me")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'id="delBtn"' in html
    assert "/api/account/delete" in html
    assert "delete=1" in html          # mobile deep-link handler present
