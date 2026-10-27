"""Cycle-4 — access control, tenant isolation (writes), session revocation, iPad nav.
AUTOMATED SANDBOX ONLY."""
import uuid


def _as(client, appmod, role, org=None, seed=True):
    org = org or appmod.DEFAULT_ORG
    uname = role[:3] + uuid.uuid4().hex[:6]
    if seed:
        with appmod.update_json(appmod.USERS_FILE) as u:
            u[uname] = {"password": "x", "role": role, "name": role, "org": org}
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=org)
    client.set_cookie("csrf_token", "tok")
    return uname, {"X-CSRF-Token": "tok"}


# ---------- permission matrix on representative sensitive routes ----------
def test_worker_denied_admin_surfaces(client, appmod):
    _as(client, appmod, "worker")
    for path in ("/api/users", "/api/profit", "/api/audit-log", "/admin/settings"):
        code = {client.get(path).status_code, client.post(path, json={}, headers={"X-CSRF-Token": "tok"}).status_code}
        assert 403 in code or 401 in code, f"{path} reachable by worker ({code})"


def test_cs_denied_user_management(client, appmod):
    _as(client, appmod, "cs")
    assert client.get("/api/users").status_code in (401, 403)


def test_admin_reaches_admin_surfaces(client, appmod):
    _as(client, appmod, "admin")
    assert client.get("/api/users").status_code == 200


# ---------- cross-tenant WRITE is denied ----------
def test_cross_tenant_revert_denied(client, appmod):
    orgA = appmod.DEFAULT_ORG
    orgB = "tenantC"
    appmod.provision_org(orgB)
    sid = "XT" + uuid.uuid4().hex[:6]
    c = appmod.sdb(orgA)
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform) VALUES(?,?,'b','L','tiktok')",
              (sid, "packed"))
    c.commit(); c.close()
    _as(client, appmod, "admin", org=orgB)   # admin, but of a DIFFERENT tenant
    j = client.post(f"/api/shipment/{sid}/revert", json={"to": "pending"}, headers={"X-CSRF-Token": "tok"}).get_json()
    assert j.get("ok") is False, "org B admin reverted org A's shipment (tenant isolation breach)"
    # org A's shipment is untouched
    c = appmod.sdb(orgA)
    assert c.execute("SELECT status FROM shipments WHERE shipment_id=?", (sid,)).fetchone()["status"] == "packed"
    c.close()


# ---------- session revocation under the live flow ----------
def test_session_revoked_midflow(client, appmod):
    uname, hdr = _as(client, appmod, "admin")
    assert client.get("/api/users").status_code == 200          # works while account exists
    with appmod.update_json(appmod.USERS_FILE) as u:
        u.pop(uname, None)                                       # account deleted mid-session
    assert client.get("/api/users").status_code == 401          # next request is revoked


def test_demotion_takes_effect_next_request(client, appmod):
    uname, hdr = _as(client, appmod, "admin")
    assert client.get("/api/users").status_code == 200
    with appmod.update_json(appmod.USERS_FILE) as u:
        u[uname]["role"] = "worker"                              # demoted
    assert client.get("/api/users").status_code == 403          # elevated access gone immediately


# ---------- iPad navigation: persistent Back + Home never leaves a worker trapped ----------
def test_ipad_nav_back_home_present(client, appmod):
    _as(client, appmod, "worker")
    html = client.get("/home").get_data(as_text=True)
    assert 'class="sb-back"' in html and 'class="sb-home"' in html, "persistent Back/Home nav missing"
