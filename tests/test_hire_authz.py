"""AUDIT #6: the hire flow must not let a CS user assign/obtain admin. Server-side enforced."""
import uuid


def _login(client, appmod, role):
    uname = role[:4] + uuid.uuid4().hex[:3]
    with appmod.update_json(appmod.USERS_FILE) as _u:
        _u[uname] = {"password": "x", "role": role, "name": role, "org": appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user=uname, username=uname, role=role, roles=[role], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _create(client, hdr, role_target):
    return client.post("/api/hires", json={"full_name": "T " + uuid.uuid4().hex[:5], "role_target": role_target}, headers=hdr)


def test_cs_cannot_create_admin_hire(client, appmod):
    hdr = _login(client, appmod, "cs")
    for r in ("admin", "manager", "cs"):
        assert _create(client, hdr, r).status_code == 403, f"CS was allowed to assign {r}"


def test_cs_can_create_worker_hire(client, appmod):
    hdr = _login(client, appmod, "cs")
    r = _create(client, hdr, "worker")
    assert r.status_code == 200 and r.get_json().get("ok") is True   # legitimate hiring preserved


def test_admin_can_create_admin_hire(client, appmod):
    hdr = _login(client, appmod, "admin")
    r = _create(client, hdr, "admin")
    assert r.status_code == 200 and r.get_json().get("ok") is True


def test_cs_cannot_patch_hire_to_admin(client, appmod):
    hdr = _login(client, appmod, "cs")
    hid = _create(client, hdr, "worker").get_json()["id"]
    assert client.patch(f"/api/hires/{hid}", json={"role_target": "admin"}, headers=hdr).status_code == 403


def test_worker_cannot_access_hires(client, appmod):
    hdr = _login(client, appmod, "worker")
    assert client.get("/api/hires").status_code == 403
    assert _create(client, hdr, "worker").status_code == 403


def test_temp_password_not_in_hire_list(client, appmod):
    # seed a provisioned hire with a temp password, then confirm the list redacts it
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO new_hires(full_name,role_target,status,invite_token,provisioned_username,provisioned_password) "
              "VALUES('P','worker','provisioned','tok-'||hex(randomblob(4)),'puser','SUPERSECRETPW')")
    c.commit(); c.close()
    hdr = _login(client, appmod, "admin")
    body = client.get("/api/hires", headers=hdr).get_data(as_text=True)
    assert "SUPERSECRETPW" not in body, "plaintext temp password leaked in /api/hires list"
