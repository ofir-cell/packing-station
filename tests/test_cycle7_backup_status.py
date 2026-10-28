"""Cycle-7: /api/ops/backup-status must be admin-only and leak no secrets."""
import uuid


def test_backup_status_requires_admin(client, appmod):
    # unauth
    assert client.get("/api/ops/backup-status").status_code != 200
    # worker (seeded so session-revocation doesn't 401 first)
    u = "w"+uuid.uuid4().hex[:6]
    with appmod.update_json(appmod.USERS_FILE) as uu:
        uu[u] = {"password":"x","role":"worker","name":"w","org":appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user=u, role="worker", roles=["worker"], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token","tok")
    assert client.get("/api/ops/backup-status").status_code == 403


def test_backup_status_admin_ok_no_secrets(client, appmod):
    with appmod.update_json(appmod.USERS_FILE) as uu:
        uu["adm"] = {"password":"x","role":"admin","name":"A","org":appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user="adm", role="admin", roles=["admin"], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token","tok")
    r = client.get("/api/ops/backup-status")
    assert r.status_code == 200
    body = r.get_data(as_text=True).lower()
    j = r.get_json()
    # only safe flags/ids present; no secret-ish keys in the payload
    assert set(["ok","enabled","bucket_configured","last_run_id","last_ok","stale"]).issubset(j.keys())
    for leak in ("secret","access_key","password","token","r2_secret","aws_"):
        assert leak not in body, f"possible secret leak: {leak}"
