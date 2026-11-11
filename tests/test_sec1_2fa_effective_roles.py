"""SEC-1 (docs/security/2026-11-10-mobile-baseline.md): mandatory 2FA follows the user's
EFFECTIVE roles (primary + extra_roles), not the primary role only.

Policy is unchanged otherwise: 2FA is required for admin only. `/api/users` is
req_true_admin, so a 200 there means "this session really is an admin"; `/api/shows`
is open to every floor role, so a 200 there means "this session is not held".
"""
import time
import uuid

import pytest

PW = "Passw0rd!x"
SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture(scope="module")
def org(appmod):
    A = appmod
    o = "sec1%s" % uuid.uuid4().hex[:6]
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (o, o.upper() + " Co", o[:10].upper(), "active"))
    c.commit(); c.close()
    A.provision_org(o)
    return o


def _user(A, org, role, extra=None, enrolled=False, **more):
    u = "u%s" % uuid.uuid4().hex[:8]
    rec = {"password": A._h(PW), "role": role, "name": u, "org": org}
    if extra:
        rec["extra_roles"] = list(extra)
    if enrolled:
        rec["twofa_enabled"] = True; rec["twofa_secret"] = SECRET
    rec.update(more)
    with A.update_json(A.USERS_FILE) as users:
        users[u] = rec
    return u


def _login(A, username):
    c = A.app.test_client()
    c.get("/login")
    c.csrf = {"X-CSRF-Token": c.get_cookie("csrf_token").value}
    return c, c.post("/api/login", json={"username": username, "password": PW}, headers=c.csrf).get_json()


def _held(c):
    r = c.get("/api/users")
    return r.status_code == 403 and (r.get_json(silent=True) or {}).get("error") == "need_2fa_setup"


def _second_step(A, c):
    return c.post("/api/login/2fa", json={"code": A._totp_at(SECRET, time.time())}, headers=c.csrf).get_json()


def test_plain_worker_is_not_asked_for_2fa(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "worker"))
    assert r["ok"] and not r.get("twofa") and r.get("must_setup_2fa") is False
    assert c.get("/api/shows").status_code == 200          # works the floor, not held
    assert c.get("/api/users").status_code == 403 and not _held(c)   # plain role refusal
    assert 'var ROLE="worker"' in c.get("/me").get_data(as_text=True)


@pytest.mark.parametrize("role,extra", [("manager", None), ("cs", None), ("worker", ["manager", "cs"])])
def test_policy_not_widened_to_manager_or_cs(appmod, org, role, extra):
    A = appmod
    c, r = _login(A, _user(A, org, role, extra))
    assert r["ok"] and not r.get("twofa") and r.get("must_setup_2fa") is False
    assert c.get("/api/shows").status_code == 200


def test_primary_admin_not_enrolled_is_held(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "admin"))
    assert r["ok"] and r.get("must_setup_2fa") is True
    assert _held(c) and c.get("/api/shows").status_code == 403
    assert c.get("/api/2fa/status").get_json()["required"] is True


def test_primary_admin_enrolled_needs_the_code(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "admin", enrolled=True))
    assert r["ok"] and r.get("twofa") is True
    assert c.get("/api/users").status_code != 200           # password alone is not a session
    assert _second_step(A, c)["ok"]
    assert c.get("/api/users").status_code == 200


def test_worker_with_extra_admin_not_enrolled_is_held_and_can_enroll(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "worker", ["admin"]))
    assert r["ok"] and r.get("must_setup_2fa") is True
    assert _held(c) and c.get("/api/shows").status_code == 403
    # the hold must leave a way out: the Me screen shows the 2FA section for this user
    me = c.get("/me")
    assert me.status_code == 200 and 'var ROLE="admin"' in me.get_data(as_text=True)
    st = c.get("/api/2fa/status").get_json()
    assert st["required"] is True and st["must_setup"] is True
    secret = c.post("/api/2fa/setup", headers=c.csrf).get_json()["secret"]
    assert c.post("/api/2fa/enable", json={"code": A._totp_at(secret, time.time())}, headers=c.csrf).get_json()["ok"]
    assert c.get("/api/users").status_code == 200


def test_worker_with_extra_admin_enrolled_needs_the_code(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "worker", ["admin"], enrolled=True))
    assert r["ok"] and r.get("twofa") is True
    assert c.get("/api/users").status_code != 200
    assert _second_step(A, c)["ok"]
    assert c.get("/api/users").status_code == 200
    assert c.get("/api/shows").status_code == 200


def test_turning_2fa_off_holds_an_extra_role_admin_again(appmod, org):
    A = appmod
    c, _ = _login(A, _user(A, org, "worker", ["admin"], enrolled=True))
    assert _second_step(A, c)["ok"]
    assert c.post("/api/2fa/disable", json={"code": A._totp_at(SECRET, time.time())}, headers=c.csrf).get_json()["ok"]
    assert _held(c)


def test_admin_granted_mid_session_is_held_on_the_next_request(appmod, org):
    A = appmod
    u = _user(A, org, "worker")
    c, r = _login(A, u)
    assert r.get("must_setup_2fa") is False and c.get("/api/shows").status_code == 200
    with A.update_json(A.USERS_FILE) as users:
        users[u]["extra_roles"] = ["admin"]
    assert _held(c)                                          # the very next request, no admin in between
    assert c.get("/api/shows").status_code == 403
    assert c.get("/me").status_code == 200
    # admin taken away again -> an ordinary worker session, not stuck behind the hold
    with A.update_json(A.USERS_FILE) as users:
        users[u].pop("extra_roles")
    # (the hold gate runs before the role re-sync, so the release shows from the request after)
    c.get("/api/me")
    assert c.get("/api/shows").status_code == 200
    assert c.get("/api/users").status_code == 403 and not _held(c)


def test_primary_role_change_to_admin_mid_session_is_held(appmod, org):
    A = appmod
    u = _user(A, org, "worker")
    c, _ = _login(A, u)
    with A.update_json(A.USERS_FILE) as users:
        users[u]["role"] = "admin"
    assert _held(c)


def test_twofa_exempt_behaviour_is_unchanged(appmod, org):
    """SEC-3 is a separate fix: today the flag switches the requirement off, for a primary
    admin and (consistently) for an extra-role admin."""
    A = appmod
    for role, extra in (("admin", None), ("worker", ["admin"])):
        assert A._twofa_required({"role": role, "extra_roles": extra, "twofa_exempt": True}) is False
    assert A._twofa_required({"role": "worker", "extra_roles": ["admin"]}) is True
    assert A._twofa_required({"role": "worker"}) is False
    assert A._twofa_required(None) is False
