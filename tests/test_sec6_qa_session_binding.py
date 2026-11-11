"""QA gate for the org-bound session check added with SEC-6 (`_session_revocation`).

That check runs on every request of every signed-in user, so the question here is the
opposite of the security one: does anybody LEGITIMATE get signed out or blocked?
Sessions are minted by the real sign-in endpoints wherever possible.
"""
import uuid

import pytest

PW = "Passw0rd!x"
_H = {}


def _pw(A):
    if "h" not in _H: _H["h"] = A._h(PW)
    return _H["h"]


def _mk_org(A):
    org = "sb" + uuid.uuid4().hex[:6]
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (org, org + " Co", org.upper(), "active"))
    c.commit(); c.close()
    A.provision_org(org)
    return org


def _user(A, name, **rec):
    rec.setdefault("role", "worker"); rec.setdefault("name", name)
    rec["password"] = _pw(A)
    with A.update_json(A.USERS_FILE) as users:
        users[name] = rec
    return name


def _login(A, username):
    c = A.app.test_client()
    c.get("/login")
    c.csrf = {"X-CSRF-Token": c.get_cookie("csrf_token").value}
    r = c.post("/api/login", json={"username": username, "password": PW}, headers=c.csrf)
    assert r.status_code == 200 and r.get_json()["ok"], r.get_json()
    return c


def _cookie(A, **sess):
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(sess)
    c.set_cookie("csrf_token", "tok"); c.csrf = {"X-CSRF-Token": "tok"}
    return c


def _alive(c, path="/api/shows", api_ok=True):
    """Two requests in a row answer 200 and the app still reports the user signed in.
    api_ok=False: a record with an EMPTY org value (or a cookie with no org) already gets
    500 on data endpoints on main (existing quirk, measured on unchanged main); for
    those only "not signed out, pages still open" is checked, i.e. same as before."""
    for _ in range(2):
        r = c.get(path)
        if api_ok:
            assert r.status_code == 200, (path, r.status_code, r.get_data(as_text=True)[:200])
        else:
            assert r.status_code not in (401, 402, 403), (path, r.status_code)
            assert c.get("/home").status_code == 200
    m = c.get("/api/mobile/session").get_json()
    assert m["signed_in"] is True
    return m


# ───────── ordinary users ─────────

@pytest.mark.parametrize("org_field", ["<missing>", "", None, "<default>"])
@pytest.mark.parametrize("role", ["worker", "picker", "cs", "manager"])
def test_founding_org_users_including_legacy_records_stay_signed_in(appmod, org_field, role):
    """Legacy accounts in users.json have no org field (or an empty one): they are the
    founding org's and must compare equal to a session that carries the default org."""
    A = appmod
    rec = {"role": role}
    if org_field == "<default>": rec["org"] = A.DEFAULT_ORG
    elif org_field != "<missing>": rec["org"] = org_field
    u = _user(A, "leg" + uuid.uuid4().hex[:8], **rec)
    m = _alive(_login(A, u), api_ok=org_field in ("<missing>", "<default>"))
    assert m["user"] == u and (m["org"] or A.DEFAULT_ORG) == A.DEFAULT_ORG


def test_founding_org_admin_stays_signed_in(appmod):
    A = appmod
    u = _user(A, "legadm" + uuid.uuid4().hex[:6], role="admin")           # no org field
    c = _login(A, u)                                                       # held at the 2FA-setup gate, not signed out
    for _ in range(2):
        assert c.get("/me").status_code == 200
    j = c.get("/api/shows").get_json()                      # the 2FA gate answers, not the revocation
    assert j["error"] == "need_2fa_setup"


@pytest.mark.parametrize("role", ["worker", "picker", "cs", "manager"])
def test_second_org_users_stay_signed_in(appmod, role):
    A = appmod
    org = _mk_org(A)
    u = _user(A, org + "-" + role, role=role, org=org)
    m = _alive(_login(A, u))
    assert m["org"] == org


def test_badge_session_stays_signed_in(appmod):
    A = appmod
    org = _mk_org(A)
    for o in (org, None):
        badge = A._gen_badge_token() if hasattr(A, "_gen_badge_token") else "ABCD-EFGH-JKLM-" + uuid.uuid4().hex[:4].upper()
        rec = {"role": "worker", "badge_token": badge}
        if o: rec["org"] = o
        u = _user(A, "bdg" + uuid.uuid4().hex[:8], **rec)
        c = A.app.test_client(); c.get("/login")
        h = {"X-CSRF-Token": c.get_cookie("csrf_token").value}
        r = c.post("/api/badge-login", json={"token": badge}, headers=h)
        assert r.status_code == 200 and r.get_json().get("ok"), r.get_json()
        assert _alive(c)["user"] == u


# ───────── cookies issued before this deploy ─────────

def test_cookie_in_the_shape_main_issues_today_survives_the_deploy(appmod):
    """main's sign-in stores user, role, name, roles, org, brand (app.py on main: password
    and badge sign-in both set session['org']). Such a cookie must keep working."""
    A = appmod
    org = _mk_org(A)
    u1 = _user(A, "old" + uuid.uuid4().hex[:8], role="worker")                         # founding, legacy record
    u2 = _user(A, "old" + uuid.uuid4().hex[:8], role="worker", org=org)
    _alive(_cookie(A, user=u1, role="worker", name=u1, roles=["worker"], org=A.DEFAULT_ORG, brand=A.brand_for_session(A.DEFAULT_ORG)))
    _alive(_cookie(A, user=u2, role="worker", name=u2, roles=["worker"], org=org, brand=A.brand_for_session(org)))


def test_cookie_without_an_org_key_is_treated_as_the_founding_org(appmod):
    """A cookie with no org at all (older than multi-tenancy; cookies live 7 days, so none
    should exist) still works for a founding-org user, and is refused for anyone else."""
    A = appmod
    org = _mk_org(A)
    u1 = _user(A, "noorg" + uuid.uuid4().hex[:8], role="worker")
    u2 = _user(A, "noorg" + uuid.uuid4().hex[:8], role="worker", org=org)
    _alive(_cookie(A, user=u1, role="worker", name=u1, roles=["worker"]), api_ok=False)
    assert _cookie(A, user=u2, role="worker", name=u2, roles=["worker"]).get("/api/shows").status_code == 401


# ───────── platform owner and support mode ─────────

def test_platform_owner_and_support_mode_are_not_signed_out(appmod):
    A = appmod
    org = _mk_org(A)
    su = _user(A, "su" + uuid.uuid4().hex[:8], role="superadmin", org=A.PLATFORM_ORG)
    c = _cookie(A, user=su, role="superadmin", roles=["superadmin"], name="Platform Owner", org=A.PLATFORM_ORG)
    for target in (org, A.DEFAULT_ORG):
        for _ in range(2):
            assert c.get("/api/orgs").status_code == 200
        r = c.post("/api/impersonate", headers=c.csrf, json={"org_id": target})
        assert r.get_json()["ok"], r.get_json()
        m = _alive(c)                                                   # "view as": session org != the owner's record org
        assert m["org"] == target and m["user"] == su
        assert c.post("/api/impersonate/exit", headers=c.csrf, json={}).get_json()["ok"]
    assert c.get("/api/orgs").status_code == 200


def test_support_mode_into_a_deleted_company_ends(appmod):
    A = appmod
    org = _mk_org(A)
    su = _user(A, "su" + uuid.uuid4().hex[:8], role="superadmin", org=A.PLATFORM_ORG)
    c = _cookie(A, user=su, role="superadmin", roles=["superadmin"], name="Platform Owner", org=A.PLATFORM_ORG)
    assert c.post("/api/impersonate", headers=c.csrf, json={"org_id": org}).get_json()["ok"]
    _alive(c)
    assert A._delete_org_data(org)["ok"]
    assert c.get("/api/shows").status_code in (401, 402)


# ───────── things that must end a session, and things that must not ─────────

def test_user_moved_to_another_org_must_sign_in_again_and_then_works(appmod):
    A = appmod
    a, b = _mk_org(A), _mk_org(A)
    u = _user(A, "mv" + uuid.uuid4().hex[:8], role="worker", org=a)
    c = _login(A, u); _alive(c)
    with A.update_json(A.USERS_FILE) as users:
        users[u]["org"] = b
    r = c.get("/api/shows")
    assert r.status_code == 401 and r.get_json()["error"] == "session_revoked"   # never keeps acting on org a
    assert _alive(_login(A, u))["org"] == b


def test_deleting_one_company_signs_out_only_that_company(appmod):
    A = appmod
    a, b = _mk_org(A), _mk_org(A)
    ua = _user(A, a + "-w", role="worker", org=a); ub = _user(A, b + "-w", role="worker", org=b)
    uf = _user(A, "fw" + uuid.uuid4().hex[:8], role="worker")
    ca, cb, cf = _login(A, ua), _login(A, ub), _login(A, uf)
    for c in (ca, cb, cf): _alive(c)
    assert A._delete_org_data(a)["ok"]
    assert ca.get("/api/shows").status_code in (401, 402)   # billing gate (402) or revocation (401), whichever runs first
    assert ca.get("/home").status_code in (302, 401, 402)
    _alive(cb); _alive(cf)


def test_a_failing_tombstone_lookup_never_locks_anyone_out(appmod, monkeypatch):
    """platform.db busy or unreadable for a moment: the check is skipped, nobody is signed out."""
    A = appmod
    u = _user(A, "fo" + uuid.uuid4().hex[:8], role="worker")
    c = _login(A, u); _alive(c)
    def boom(*a, **k): raise A.sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(A, "org_id_tombstoned", boom)
    _alive(c)


@pytest.mark.xfail(strict=True, reason="QA-SEC6-4 (hardening, not reachable through the app): a tombstone row for the "
                   "founding org signs out every founding-org user on every request until the next boot clears it; "
                   "_session_revocation should not consult tombstones for a protected org")
def test_founding_org_can_never_be_signed_out_by_a_stray_tombstone(appmod):
    """Belt and braces: even if a tombstone row for the founding org appeared (hand edit,
    restored file), the warehouse must not be signed out until the next boot clears it."""
    A = appmod
    u = _user(A, "st" + uuid.uuid4().hex[:8], role="worker")
    c = _login(A, u); _alive(c)
    p = A.pdb(); p.execute("INSERT OR REPLACE INTO org_tombstones(org_id,state) VALUES(?, 'deleted')", (A.DEFAULT_ORG,)); p.commit(); p.close()
    try:
        _alive(c)
    finally:
        p = A.pdb(); p.execute("DELETE FROM org_tombstones WHERE org_id=?", (A.DEFAULT_ORG,)); p.commit(); p.close()


# ───────── founding-org admins and their own account (item C) ─────────

def test_founding_admin_can_delete_only_their_own_account_when_another_admin_exists(appmod):
    A = appmod
    u1 = _user(A, "fa" + uuid.uuid4().hex[:8], role="admin")
    u2 = _user(A, "fa" + uuid.uuid4().hex[:8], role="admin", org=A.DEFAULT_ORG)
    for u, body in ((u1, {}), (u2, {"wipe_org": True})):
        c = _cookie(A, user=u, role="admin", roles=["admin"], name=u, org=A.DEFAULT_ORG)
        r = c.post("/api/account/delete", headers=c.csrf, json=body)
        j = r.get_json()
        assert r.status_code == 200 and j["ok"] and j["org_deleted"] is False and "org_cleanup" not in j, j
        assert u not in A.ldj(A.USERS_FILE)
    users = A.ldj(A.USERS_FILE)
    assert "admin" in users and not A.org_id_tombstoned(A.DEFAULT_ORG)
    p = A.pdb(); assert p.execute("SELECT 1 FROM organizations WHERE org_id=?", (A.DEFAULT_ORG,)).fetchone(); p.close()


def test_only_the_founding_org_is_internal_in_a_fresh_schema(appmod):
    A = appmod
    A.pdb_init()
    new = _mk_org(A)
    p = A.pdb()
    assert p.execute("SELECT COALESCE(internal,0) FROM organizations WHERE org_id=?", (A.DEFAULT_ORG,)).fetchone()[0] == 1
    assert p.execute("SELECT COALESCE(internal,0) FROM organizations WHERE org_id=?", (new,)).fetchone()[0] == 0
    p.close()
    assert A._org_delete_protected(A.DEFAULT_ORG) and A._org_delete_protected(None) and A._org_delete_protected("")
    assert not A._org_delete_protected(new)
