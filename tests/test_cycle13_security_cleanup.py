"""Cycle 13: stage-3 security cleanup (Packing Station review doc, section 2).

- badge login: per-IP failure limit, generous because the whole floor shares one IP
- public hire endpoint returns only what the hire's own onboarding page needs
- live-vision agent auth fails closed when AGENT_TOKEN is unset
"""
import importlib.util, os, sys, uuid


def _clear_badge_limit(A, ip="127.0.0.1"):
    A._login_rate_clear(ip, "__badge__")


def _badge(client, token):
    # the badge page sends the double-submit CSRF token like every other POST
    client.set_cookie("csrf_token", "tok")
    return client.post("/api/badge-login", json={"token": token}, headers={"X-CSRF-Token": "tok"})


def _set_badge(A, user, token):
    with A.update_json(A.USERS_FILE) as users:
        users[user]["badge_token"] = token


# ── badge login rate limit ────────────────────────────────────────────────────
def test_badge_misscans_below_limit_still_allow_login(appmod, client, monkeypatch):
    A = appmod; _clear_badge_limit(A)
    monkeypatch.setattr(A.time, "sleep", lambda s: None)     # skip the 0.5s delay per miss
    good = "GOOD" + uuid.uuid4().hex[:10].upper()
    _set_badge(A, "admin", good)
    for _ in range(A.BADGE_MAX_FAILS - 1):              # a messy morning of mis-scans
        assert _badge(client, "WRONGBADGE1").get_json()["ok"] is False
    r = _badge(client, good)
    assert r.status_code == 200 and r.get_json()["ok"] is True


def test_badge_login_locks_after_limit_and_success_resets(appmod, client, monkeypatch):
    A = appmod; _clear_badge_limit(A)
    monkeypatch.setattr(A.time, "sleep", lambda s: None)     # skip the 0.5s delay per miss
    good = "GOOD" + uuid.uuid4().hex[:10].upper()
    _set_badge(A, "admin", good)
    for _ in range(A.BADGE_MAX_FAILS):
        _badge(client, "WRONGBADGE1")
    r = _badge(client, good)
    assert r.status_code == 429                          # even a real badge waits out the window
    _clear_badge_limit(A)                                # window passes
    assert _badge(client, good).get_json()["ok"] is True
    # a successful login resets the counter for the floor
    rec = A._rate_load().get(A._rate_key("127.0.0.1", "__badge__"))
    assert not rec


def test_badge_limit_is_separate_from_password_login_limit(appmod):
    A = appmod
    assert A.BADGE_MAX_FAILS > A.LOGIN_MAX_FAILS


def test_malformed_badge_counts_as_failure(appmod, client):
    A = appmod; _clear_badge_limit(A)
    _badge(client, "x")
    rec = A._rate_load().get(A._rate_key("127.0.0.1", "__badge__"))
    assert rec and rec["count"] == 1
    _clear_badge_limit(A)


# ── public hire endpoint ──────────────────────────────────────────────────────
def test_public_hire_endpoint_hides_internal_fields(appmod, client):
    A = appmod
    tok = "tok-" + uuid.uuid4().hex[:12]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("""INSERT INTO new_hires(full_name,email,phone,role_target,invite_token,notes,created_by,provisioned_username)
                 VALUES('Dana','dana@example.com','555-0100','worker',?,'INTERNAL-NOTE-XYZ','boss','dana1')""", (tok,))
    c.commit(); c.close()
    r = client.get("/api/hire/" + tok)
    assert r.status_code == 200
    d = r.get_json()
    assert d["ok"] is True and "steps" in d and "progress" in d    # what the page uses
    body = r.get_data(as_text=True)
    for leaked in ("INTERNAL-NOTE-XYZ", "boss", "dana@example.com", "555-0100", "dana1", "_org", tok):
        assert leaked not in body, leaked
    assert d["hire"]["full_name"] == "Dana"


# ── live-vision agent auth ────────────────────────────────────────────────────
def _load_livevision(tmp_path, monkeypatch, token):
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    srv = os.path.join(here, "live-vision", "server")
    monkeypatch.setenv("LIVEVISION_DB", str(tmp_path / "lv.db"))
    if token is None: monkeypatch.delenv("AGENT_TOKEN", raising=False)
    else: monkeypatch.setenv("AGENT_TOKEN", token)
    monkeypatch.syspath_prepend(srv)
    for m in ("db", "matcher"): sys.modules.pop(m, None)
    spec = importlib.util.spec_from_file_location("lv_app_" + uuid.uuid4().hex[:6], os.path.join(srv, "app.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


class _Req:
    def __init__(self, tok): self.headers = {"X-Agent-Token": tok} if tok is not None else {}


def test_livevision_fails_closed_without_token(tmp_path, monkeypatch):
    lv = _load_livevision(tmp_path, monkeypatch, None)
    assert lv._auth_ok(_Req(None)) is False
    assert lv._auth_ok(_Req("anything")) is False


def test_livevision_accepts_only_the_right_token(tmp_path, monkeypatch):
    lv = _load_livevision(tmp_path, monkeypatch, "s3cret-token")
    assert lv._auth_ok(_Req("s3cret-token")) is True
    assert lv._auth_ok(_Req("wrong")) is False
    assert lv._auth_ok(_Req(None)) is False
