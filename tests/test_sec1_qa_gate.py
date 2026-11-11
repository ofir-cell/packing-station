"""QA gate for SEC-1 (2FA follows the EFFECTIVE roles) — written by qa, independent of the
programmer's tests/test_sec1_2fa_effective_roles.py.

What is checked here that the programmer's file does not:
  * the hold covers EVERY route of the app (url_map sweep), not one admin endpoint;
  * the way out of the hold really is open: everything /me needs to enrol answers while held;
  * JSON callers get the same signal an un-enrolled PRIMARY admin always got;
  * the role change goes through the real admin API, and the admin action attempted in
    between is shown not to have happened;
  * the decision lives in the cookie + users.json only: a second OS process (another
    gunicorn worker) reaches the same decision;
  * the open point: a session issued BEFORE the fix is deployed (strict xfail).
"""
import json
import os
import re
import subprocess
import sys
import time
import uuid

import pytest

PW = "Passw0rd!x"
SECRET = "JBSWY3DPEHPK3PXP"
XSS = "<img src=x onerror=alert(1)>"


@pytest.fixture(scope="module")
def org(appmod):
    A = appmod
    o = "s1qa%s" % uuid.uuid4().hex[:6]
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (o, o.upper() + " Co", o[:10].upper(), "active"))
    c.commit(); c.close()
    A.provision_org(o)
    return o


def _user(A, org, role, extra=None, enrolled=False, **more):
    u = "q%s" % uuid.uuid4().hex[:8]
    rec = {"password": A._h(PW), "role": role, "name": more.pop("name", u), "org": org}
    if extra:
        rec["extra_roles"] = list(extra)
    if enrolled:
        rec["twofa_enabled"] = True; rec["twofa_secret"] = SECRET
    rec.update(more)
    with A.update_json(A.USERS_FILE) as users:
        users[u] = rec
    return u


def _login(A, username, headers=None):
    c = A.app.test_client()
    c.get("/login")
    c.csrf = {"X-CSRF-Token": c.get_cookie("csrf_token").value}
    h = dict(c.csrf); h.update(headers or {})
    r = c.post("/api/login", json={"username": username, "password": PW}, headers=h)
    return c, r.get_json()


def _is_hold(r, path):
    """The one signal of the enrollment hold: JSON 403 for /api/*, a redirect to /me otherwise."""
    if path.startswith("/api/"):
        return (r.status_code == 403 and r.is_json
                and (r.get_json() or {}).get("error") == "need_2fa_setup")
    return r.status_code == 302 and r.headers.get("Location", "").endswith("/me?setup2fa=1")


def _open(A, path):
    return path in A._2FA_SETUP_OPEN or path.startswith(A._2FA_SETUP_OPEN_PREFIXES)


def _all_paths(A):
    out = {}
    for rule in A.app.url_map.iter_rules():
        p = re.sub(r"<[^>]+>", "x", rule.rule)
        out.setdefault(p, set()).update(rule.methods or ())
    return out


# ───────────── 1. acceptance: held on every route, pages and JSON ─────────────

ADMIN_POSTS = ["/api/users/roles", "/api/users/name", "/api/label/buy", "/api/label/rates",
               "/api/email/test", "/api/commission-config", "/api/permissions",
               "/api/org/branding", "/api/badge-login", "/api/login"]


def test_extra_role_admin_without_2fa_is_held_on_every_route(appmod, org):
    A = appmod
    u = _user(A, org, "worker", ["admin"])
    c, r = _login(A, u)
    assert r["ok"] and r["must_setup_2fa"] is True

    paths = _all_paths(A)
    assert len(paths) > 300, "url_map sweep found too few routes to mean anything"
    leaks, n = [], 0
    for p, methods in sorted(paths.items()):
        if _open(A, p) or "GET" not in methods:
            continue
        n += 1
        resp = c.get(p)
        if not _is_hold(resp, p):
            leaks.append((p, resp.status_code))
    assert not leaks, "reachable while held: %r" % leaks[:20]
    assert n > 200

    # state-changing admin APIs: refused by the hold before the handler runs
    for p in ADMIN_POSTS:
        resp = c.post(p, json={"username": u, "role": "admin", "name": "x"}, headers=c.csrf)
        assert _is_hold(resp, p), (p, resp.status_code)
    rec = A.ldj(A.USERS_FILE)[u]
    assert rec["role"] == "worker" and rec["name"] == u and not rec.get("twofa_enabled")

    # a spread of true-admin / admin screens and APIs by name, so a route rename shows up
    for p in ("/api/users", "/api/audit-log", "/api/profit", "/admin/settings", "/admin/audit",
              "/admin/profit", "/home", "/pick", "/m/pick", "/api/shows", "/api/mobile/session"):
        assert _is_hold(c.get(p), p), p


def test_enrolled_extra_role_admin_has_no_session_before_the_code(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "worker", ["admin"], enrolled=True))
    assert r == {"ok": True, "twofa": True}
    for p in ("/api/users", "/api/audit-log", "/api/shows"):
        assert c.get(p).status_code in (302, 401, 403), p
    assert c.get("/api/mobile/session").get_json()["signed_in"] is False


# ───────────── 2. nobody is locked out: the way out is open ─────────────

def test_held_extra_role_admin_can_enrol_and_everything_me_needs_answers(appmod, org):
    A = appmod
    u = _user(A, org, "worker", ["admin"])
    c, _ = _login(A, u)

    # every page navigation lands on the enrol screen
    r = c.get("/", follow_redirects=True)
    assert r.status_code == 200 and r.request.path == "/me"
    html = r.get_data(as_text=True)
    assert 'var ROLE="admin"' in html and 'id="secSection"' in html and 'id="tfaSetupBtn"' in html
    # POSTs from this page carry the CSRF token (shim injected into the HTML)
    assert "X-CSRF-Token" in html

    # same-origin things the page loads: none of the enrol-critical ones may be held
    local = set(re.findall(r'''(?:src|href)=["'](/[^"'#? ]*)''', html))
    fetched = set(re.findall(r'''fetch\(\s*["'](/[^"'? ]*)''', html))
    held = sorted(p for p in local | fetched
                  if p not in ("/logout",) and _is_hold(c.get(p), p))
    needed = {"/api/2fa/status", "/api/me/stats"}
    assert needed <= (local | fetched) | {"/api/2fa/status"}
    assert not (needed & set(held)), held
    for p in local:
        if p.startswith("/static/"):
            assert c.get(p).status_code == 200, p
    # whatever else the page calls while held must fail as JSON, never as an HTML page
    for p in held:
        if p.startswith("/api/"):
            assert c.get(p).is_json, p

    # the QR library is the one external script; the CSP must allow exactly the URL the page uses
    qr = re.search(r'<script src="(https://[^"]+qrcode[^"]*)"', html).group(1)
    assert qr in r.headers["Content-Security-Policy"]

    st = c.get("/api/2fa/status").get_json()
    assert st["ok"] and st["required"] and st["must_setup"] and not st["enabled"]
    s = c.post("/api/2fa/setup", headers=c.csrf).get_json()
    assert s["ok"] and re.fullmatch(r"[A-Z2-7]{16,}", s["secret"])
    assert s["otpauth_uri"].startswith("otpauth://totp/") and s["secret"] in s["otpauth_uri"]
    # a wrong code neither enrols nor breaks the session
    bad = c.post("/api/2fa/enable", json={"code": "000000"}, headers=c.csrf)
    assert bad.is_json and bad.get_json()["ok"] is False
    assert _is_hold(c.get("/api/users"), "/api/users")
    en = c.post("/api/2fa/enable", json={"code": A._totp_at(s["secret"], time.time())}, headers=c.csrf).get_json()
    assert en["ok"] and len(en["recovery_codes"]) >= 6

    # the hold lifts on the very next request, for pages and for JSON
    assert c.get("/api/users").status_code == 200
    assert c.get("/home").status_code == 200
    assert c.get("/api/mobile/session").get_json()["roles"] == ["worker", "admin"]
    assert c.get("/api/2fa/status").get_json()["must_setup"] is False

    # and the next sign-in is password + code, with a recovery code as the spare key
    c.get("/logout")
    c2, r2 = _login(A, u)
    assert r2 == {"ok": True, "twofa": True}
    ok = c2.post("/api/login/2fa", json={"code": en["recovery_codes"][0]}, headers=c2.csrf).get_json()
    assert ok["ok"] and ok["used_recovery"] is True
    assert c2.get("/api/users").status_code == 200


def test_held_user_can_always_sign_out_and_someone_else_can_sign_in(appmod, org):
    A = appmod
    c, _ = _login(A, _user(A, org, "worker", ["admin"]))
    assert _is_hold(c.get("/api/users"), "/api/users")
    # a signed-in session is sent on from /login (unchanged behaviour); it ends on the enrol screen
    r = c.get("/login", follow_redirects=True)
    assert r.status_code == 200 and r.request.path in ("/me", "/login")
    assert c.get("/logout").status_code == 302
    assert c.get("/login").status_code == 200
    worker = _user(A, org, "worker")
    r = c.post("/api/login", json={"username": worker, "password": PW}, headers=c.csrf).get_json()
    assert r["ok"] and r["must_setup_2fa"] is False
    assert c.get("/api/shows").status_code == 200


def test_me_page_escapes_the_role_and_name_for_a_held_user(appmod, org):
    A = appmod
    c, _ = _login(A, _user(A, org, "worker", ["admin"], name=XSS))
    html = c.get("/me").get_data(as_text=True)
    assert XSS not in html
    # a non-admin session with a hostile role string in the cookie is still escaped
    w = A.app.test_client()
    with w.session_transaction() as s:
        s.update(user="nobody-%s" % uuid.uuid4().hex[:6], role='"><script>x</script>', roles=['"><script>x</script>'],
                 name="n", org=org)
    # (user does not exist -> session is revoked; the page must not echo the role either way)
    assert '"><script>x</script>' not in w.get("/me", follow_redirects=True).get_data(as_text=True)


# ───────────── 3. no change for everyone else ─────────────

@pytest.mark.parametrize("role,extra", [
    ("worker", None), ("picker", None), ("host", None), ("cs", None), ("manager", None),
    ("worker", ["picker", "host"]), ("host", ["cs"]), ("manager", ["cs", "worker"]),
])
def test_non_admin_roles_are_never_asked(appmod, org, role, extra):
    A = appmod
    assert A._twofa_required({"role": role, "extra_roles": extra}) is False
    c, r = _login(A, _user(A, org, role, extra))
    assert r["ok"] and r["must_setup_2fa"] is False and "twofa" not in r
    assert c.get("/api/mobile/session").get_json()["signed_in"] is True
    me = c.get("/me")
    assert me.status_code == 200 and 'var ROLE="%s"' % role in me.get_data(as_text=True)
    assert c.get("/home").status_code == 200                       # not redirected to enrol
    assert c.get("/api/users").status_code == 403                  # still no true-admin
    assert (c.get("/api/users").get_json(silent=True) or {}).get("error") != "need_2fa_setup"


def test_primary_admin_enrolled_and_not_enrolled_behave_as_before(appmod, org):
    A = appmod
    c, r = _login(A, _user(A, org, "admin"))
    assert r["ok"] and r["must_setup_2fa"] is True
    for p in ("/api/users", "/home", "/api/shows"):
        assert _is_hold(c.get(p), p)
    assert 'var ROLE="admin"' in c.get("/me").get_data(as_text=True)

    c, r = _login(A, _user(A, org, "admin", enrolled=True))
    assert r == {"ok": True, "twofa": True}
    assert c.post("/api/login/2fa", json={"code": A._totp_at(SECRET, time.time())}, headers=c.csrf).get_json()["ok"]
    assert c.get("/api/users").status_code == 200 and c.get("/home").status_code == 200


@pytest.mark.parametrize("role,extra", [("admin", None), ("worker", ["admin"])])
def test_twofa_exempt_account_signs_in_as_before(appmod, org, role, extra):
    """SEC-3 (the flag works in any org) is a separate, still open finding."""
    A = appmod
    c, r = _login(A, _user(A, org, role, extra, twofa_exempt=True))
    assert r["ok"] and r["must_setup_2fa"] is False
    assert c.get("/api/users").status_code == 200
    # only the literal True exempts
    assert A._twofa_required({"role": role, "extra_roles": extra, "twofa_exempt": "true"}) is True
    assert A._twofa_required({"role": role, "extra_roles": extra, "twofa_exempt": 1}) is True


def test_platform_owner_is_not_held(appmod):
    A = appmod
    u = "own%s" % uuid.uuid4().hex[:6]
    with A.update_json(A.USERS_FILE) as users:
        users[u] = {"password": A._h(PW), "role": "superadmin", "name": "Platform Owner", "org": A.PLATFORM_ORG}
    try:
        assert A._twofa_required(A.ldj(A.USERS_FILE)[u]) is False
        c, r = _login(A, u)
        assert r["ok"] and r["must_setup_2fa"] is False
        assert c.get("/admin/organizations").status_code == 200
        assert c.get("/", follow_redirects=False).headers["Location"].endswith("/admin/organizations")
    finally:
        with A.update_json(A.USERS_FILE) as users:
            users.pop(u, None)


def test_support_impersonation_session_is_not_held(appmod, org):
    """The platform owner acting as a tenant admin carries roles=['admin'] and no user record
    of that org; the re-decision must not catch it."""
    A = appmod
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user="owner-x", impersonator="owner-x", role="admin", roles=["admin"], org=org, name="Support")
    assert c.get("/api/users").status_code == 200


# ───────────── 4. JSON callers: same signal a primary admin always got ─────────────

@pytest.mark.parametrize("headers", [{}, {"X-Client": "lohub-ios/1.0.0", "Accept": "application/json"}])
def test_held_extra_admin_gets_the_same_answers_as_a_held_primary_admin(appmod, org, headers):
    A = appmod
    ce, _ = _login(A, _user(A, org, "worker", ["admin"]), headers)
    cp, _ = _login(A, _user(A, org, "admin"), headers)
    for method, p in [("GET", "/api/users"), ("GET", "/api/shows"), ("GET", "/api/mobile/session"),
                      ("POST", "/api/users/roles"), ("POST", "/api/label/buy"), ("GET", "/api/me/stats"),
                      ("GET", "/api/2fa/status"), ("GET", "/home"), ("GET", "/m/pick")]:
        a = ce.open(p, method=method, json={} if method == "POST" else None, headers=dict(ce.csrf, **headers))
        b = cp.open(p, method=method, json={} if method == "POST" else None, headers=dict(cp.csrf, **headers))
        assert (a.status_code, a.mimetype, a.headers.get("Location")) == \
               (b.status_code, b.mimetype, b.headers.get("Location")), p
        if p.startswith("/api/"):
            assert a.is_json, p                      # never an HTML page into a fetch().then(r.json())
            if not _open(A, p):
                assert a.status_code == 403 and a.get_json() == b.get_json()
                assert a.get_json()["error"] == "need_2fa_setup" and a.get_json()["ok"] is False


# ───────────── 5. role change in the middle of a session ─────────────

def _admin_client(A, org):
    c, r = _login(A, _user(A, org, "admin", enrolled=True))
    assert c.post("/api/login/2fa", json={"code": A._totp_at(SECRET, time.time())}, headers=c.csrf).get_json()["ok"]
    return c


def test_admin_granted_through_the_api_holds_the_open_session_before_any_admin_action(appmod, org):
    A = appmod
    boss = _admin_client(A, org)
    victim = _user(A, org, "worker")
    u = _user(A, org, "worker")
    c, r = _login(A, u)
    assert r["must_setup_2fa"] is False and c.get("/api/shows").status_code == 200

    assert boss.post("/api/users/roles", json={"username": u, "role": "worker", "extra_roles": ["admin"]},
                     headers=boss.csrf).get_json()["ok"]
    # the first request after the grant IS an admin action — it must not run
    r = c.post("/api/users/roles", json={"username": victim, "role": "admin"}, headers=c.csrf)
    assert _is_hold(r, "/api/users/roles")
    assert A.ldj(A.USERS_FILE)[victim]["role"] == "worker"
    assert _is_hold(c.get("/api/users"), "/api/users") and _is_hold(c.get("/home"), "/home")
    # held, not stuck: the enrol screen now shows the 2FA section and enrolling lifts it
    assert 'var ROLE="admin"' in c.get("/me").get_data(as_text=True)
    s = c.post("/api/2fa/setup", headers=c.csrf).get_json()
    assert c.post("/api/2fa/enable", json={"code": A._totp_at(s["secret"], time.time())}, headers=c.csrf).get_json()["ok"]
    assert c.get("/api/users").status_code == 200


def test_first_request_after_the_grant_being_an_open_path_gives_no_admin(appmod, org):
    """/api/me and /me are open during the hold. If the first request after the grant is one of
    them it goes through — the session must still come out of it held."""
    A = appmod
    u = _user(A, org, "worker")
    c, _ = _login(A, u)
    with A.update_json(A.USERS_FILE) as users:
        users[u]["extra_roles"] = ["admin"]
    assert c.get("/api/me/stats").status_code == 200
    assert _is_hold(c.get("/api/users"), "/api/users")


def test_admin_taken_away_releases_the_hold_on_the_next_page_load(appmod, org):
    A = appmod
    boss = _admin_client(A, org)
    u = _user(A, org, "worker", ["admin"])
    c, r = _login(A, u)
    assert r["must_setup_2fa"] is True
    assert boss.post("/api/users/roles", json={"username": u, "role": "worker", "extra_roles": []},
                     headers=boss.csrf).get_json()["ok"]
    # a page load is sent to /me (open path) where the roles are re-read and the hold dropped
    r = c.get("/pick", follow_redirects=True)
    assert r.status_code == 200
    assert c.get("/api/shows").status_code == 200
    again = c.get("/api/users")
    assert again.status_code == 403 and not _is_hold(again, "/api/users")
    assert 'var ROLE="worker"' in c.get("/me").get_data(as_text=True)


def test_primary_admin_demoted_mid_session_loses_admin_at_once(appmod, org):
    A = appmod
    u = _user(A, org, "admin", enrolled=True)
    c, _ = _login(A, u)
    assert c.post("/api/login/2fa", json={"code": A._totp_at(SECRET, time.time())}, headers=c.csrf).get_json()["ok"]
    assert c.get("/api/users").status_code == 200
    with A.update_json(A.USERS_FILE) as users:
        users[u]["role"] = "worker"
    r = c.get("/api/users")
    assert r.status_code == 403 and not _is_hold(r, "/api/users")
    assert c.get("/api/shows").status_code == 200


_OTHER_WORKER = r"""
import os, sys, json
sys.path.insert(0, sys.argv[1])
import app as A
c = A.app.test_client()
c.set_cookie("session", sys.argv[2])
out = {}
for p in ("/api/users", "/api/shows", "/api/me/stats"):
    r = c.get(p)
    out[p] = [r.status_code, (r.get_json(silent=True) or {}).get("error")]
print("RESULT " + json.dumps(out))
"""


def test_a_second_process_reaches_the_same_decision(appmod, org):
    """Several gunicorn workers: the hold must come from the cookie and users.json only.
    The session is signed in as a plain worker in THIS process, admin is granted, and the
    first request after the grant is served by ANOTHER python process."""
    A = appmod
    u = _user(A, org, "worker")
    c, _ = _login(A, u)
    assert c.get("/api/shows").status_code == 200
    cookie = c.get_cookie("session").value
    with A.update_json(A.USERS_FILE) as users:
        users[u]["extra_roles"] = ["admin"]
    env = dict(os.environ, DATA_DIR=os.environ["DATA_DIR"], SECRET_KEY=A.app.secret_key if isinstance(A.app.secret_key, str)
               else A.app.secret_key.decode())
    env.pop("SUPERADMIN_USER", None)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = subprocess.run([sys.executable, "-c", _OTHER_WORKER, root, cookie], env=env,
                       capture_output=True, text=True, timeout=180)
    line = [l for l in p.stdout.splitlines() if l.startswith("RESULT ")]
    assert line, p.stderr[-800:]
    out = json.loads(line[0][7:])
    assert out["/api/users"] == [403, "need_2fa_setup"]
    assert out["/api/shows"] == [403, "need_2fa_setup"]
    assert out["/api/me/stats"][0] == 200


# ───────────── 6. open point: sessions issued before the fix ─────────────

@pytest.mark.xfail(strict=True, reason="SEC-1 residual: a session issued before the fix (extra-role admin, "
                                       "no 2FA, no must_setup_2fa in the cookie) keeps full admin until it "
                                       "expires (up to 7 days) — the hold is re-decided only when roles change")
def test_session_issued_before_the_fix_is_held_too(appmod, org):
    A = appmod
    u = _user(A, org, "worker", ["admin"])
    c = A.app.test_client()
    with c.session_transaction() as s:            # exactly what the old _finalize_login minted
        s.update(user=u, role="worker", roles=["worker", "admin"], name=u, org=org)
    c.set_cookie("csrf_token", "tok")
    assert _is_hold(c.get("/api/users"), "/api/users")
