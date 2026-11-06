"""Cycle-26: mandatory TOTP two-factor for ADMIN accounts (money lives there).
Admins must enrol; until they do, everything but the Me screen + enrolment is held.
Once enabled, password is step 1 and the 6-digit code (or a recovery code) is step 2.
Non-admins are unaffected."""
import time


def _pw(A, user, pw="secret123", role="admin"):
    with A.update_json(A.USERS_FILE) as uu:
        uu.setdefault(user, {"name": user, "org": A.DEFAULT_ORG})
        uu[user]["password"] = A._h(pw); uu[user]["role"] = role; uu[user]["name"] = user; uu[user]["org"] = A.DEFAULT_ORG
        uu[user].pop("twofa_enabled", None); uu[user].pop("twofa_secret", None); uu[user].pop("recovery_codes", None)


def _c(client):
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok", "Content-Type": "application/json"}


def test_admin_without_2fa_is_gated_until_enrolled(appmod, client):
    A = appmod; _pw(A, "admin"); H = _c(client)
    r = client.post("/api/login", json={"username": "admin", "password": "secret123"}, headers=H).get_json()
    assert r["ok"] and r.get("must_setup_2fa") is True
    # a money screen is blocked
    g = client.get("/api/inventory/stats")
    assert g.status_code == 403 and g.get_json()["error"] == "need_2fa_setup"
    # the Me screen + 2fa endpoints stay reachable
    assert client.get("/api/2fa/status").get_json()["must_setup"] is True


def test_enrol_then_gate_lifts(appmod, client):
    A = appmod; _pw(A, "admin"); H = _c(client)
    client.post("/api/login", json={"username": "admin", "password": "secret123"}, headers=H)
    s = client.post("/api/2fa/setup", headers=H).get_json()
    assert s["ok"] and s["otpauth_uri"].startswith("otpauth://totp/")
    secret = s["secret"]
    # wrong code is rejected
    assert client.post("/api/2fa/enable", json={"code": "000000"}, headers=H).get_json()["ok"] is False
    e = client.post("/api/2fa/enable", json={"code": A._totp_at(secret, time.time())}, headers=H).get_json()
    assert e["ok"] and len(e["recovery_codes"]) == 8
    assert client.get("/api/inventory/stats").status_code == 200   # gate lifted


def test_login_two_step_with_code_and_recovery(appmod, client):
    A = appmod; _pw(A, "admin"); H = _c(client)
    client.post("/api/login", json={"username": "admin", "password": "secret123"}, headers=H)
    secret = client.post("/api/2fa/setup", headers=H).get_json()["secret"]
    rec = client.post("/api/2fa/enable", json={"code": A._totp_at(secret, time.time())}, headers=H).get_json()["recovery_codes"]
    client.get("/logout")
    # step 1: password alone does NOT log in; it asks for the code
    H = _c(client)
    r = client.post("/api/login", json={"username": "admin", "password": "secret123"}, headers=H).get_json()
    assert r["ok"] and r.get("twofa") is True and "role" not in r
    # still not authenticated for money
    assert client.get("/api/inventory/stats").status_code in (302, 401, 403)
    # wrong code
    assert client.post("/api/login/2fa", json={"code": "123456"}, headers=H).get_json()["ok"] is False
    # right code completes
    assert client.post("/api/login/2fa", json={"code": A._totp_at(secret, time.time())}, headers=H).get_json()["ok"] is True
    assert client.get("/api/inventory/stats").status_code == 200
    # recovery code is single-use
    client.get("/logout"); H = _c(client)
    client.post("/api/login", json={"username": "admin", "password": "secret123"}, headers=H)
    r1 = client.post("/api/login/2fa", json={"code": rec[0]}, headers=H).get_json()
    assert r1["ok"] and r1["used_recovery"] is True
    client.get("/logout"); H = _c(client)
    client.post("/api/login", json={"username": "admin", "password": "secret123"}, headers=H)
    assert client.post("/api/login/2fa", json={"code": rec[0]}, headers=H).get_json()["ok"] is False   # already used


def test_non_admin_unaffected(appmod, client):
    A = appmod; _pw(A, "worker1", role="worker"); H = _c(client)
    r = client.post("/api/login", json={"username": "worker1", "password": "secret123"}, headers=H).get_json()
    assert r["ok"] and not r.get("twofa") and not r.get("must_setup_2fa")
    # worker cannot reach 2fa admin endpoints
    assert client.get("/api/2fa/status").status_code in (302, 403)


def test_wrong_password_still_fails(appmod, client):
    A = appmod; _pw(A, "admin"); H = _c(client)
    r = client.post("/api/login", json={"username": "admin", "password": "nope"}, headers=H).get_json()
    assert r["ok"] is False
