"""Security baseline for the mobile app (2026-11-10) — docs/security/2026-11-10-mobile-baseline.md.

Two kinds of tests here:

* ``test_holds_*``  — things the review verified and that must keep holding (they pass).
* everything else   — a demonstration of an OPEN finding. Each asserts the SECURE
  behaviour, so it fails today and is marked ``xfail(strict=True, reason="SEC-n")``.
  When the owner fixes the finding the test starts passing, strict-xfail turns the suite
  red, and the marker is removed in the same PR. Run them for real with ``--runxfail``.

Everything runs against the throwaway DATA_DIR of tests/conftest.py. No network: every
outbound transport that a test could reach is replaced by a recorder.
"""
import io
import os
import uuid

import pytest

PW = "Passw0rd!x"
ROLES = ("worker", "picker", "host", "cs", "manager", "admin")


# ───────────────────────── helpers ─────────────────────────

def _mk_org(A, prefix):
    """A real second/third tenant: organizations row + provisioned data + its users."""
    org = "%s%s" % (prefix, uuid.uuid4().hex[:6])
    c = A.pdb()
    c.execute("INSERT INTO organizations(org_id,company_name,brand_mark,sub_status,plan) VALUES(?,?,?,?,'pro')",
              (org, org.upper() + " Co", org[:10].upper(), "active"))
    c.commit(); c.close()
    A.provision_org(org)
    with A.update_json(A.USERS_FILE) as users:
        for r in ROLES:
            users["%s-%s" % (org, r)] = {"password": A._h(PW), "role": r,
                                         "name": "%s %s" % (org, r), "org": org}
    return org


def _as(A, username):
    """Test client carrying the session the server would mint for this user."""
    info = A.ldj(A.USERS_FILE)[username]
    c = A.app.test_client()
    with c.session_transaction() as s:
        s.update(user=username, role=info["role"], roles=A._effective_roles(info),
                 name=info["name"], org=info["org"])
    c.set_cookie("csrf_token", "tok")
    c.csrf = {"X-CSRF-Token": "tok"}
    return c


def _password_login(A, username, password=PW, extra_headers=None):
    c = A.app.test_client()
    c.get("/login")
    tok = c.get_cookie("csrf_token").value
    c.csrf = {"X-CSRF-Token": tok}
    h = dict(c.csrf); h.update(extra_headers or {})
    return c, c.post("/api/login", json={"username": username, "password": password}, headers=h)


def _badge_login(A, token):
    c = A.app.test_client()
    c.get("/login")
    c.csrf = {"X-CSRF-Token": c.get_cookie("csrf_token").value}
    return c, c.post("/api/badge-login", json={"token": token}, headers=c.csrf)


def _ship(A, org, tracking, label="Show 1"):
    sid = "S-" + uuid.uuid4().hex[:10]
    c = A.sdb(org)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_batch,import_label,platform,"
              "buyer_name,buyer_username,address_full) VALUES(?,?,'pending','csv',?,'tiktok',"
              "'Secret Buyer','secretbuyer','1 Private Rd, Davie FL')", (sid, tracking, label))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) "
              "VALUES(?,?,'S1','Lip',1,0)", (sid, "O" + sid))
    c.commit(); c.close()
    return sid


def _status(A, org, sid):
    c = A.sdb(org)
    r = c.execute("SELECT status,picked_by,packed_by FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    c.close()
    return dict(r)


MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 256


def _upload(c, tracking, data=MP4, name="v.mp4"):
    return c.post("/api/upload", headers=c.csrf, content_type="multipart/form-data",
                  data={"tracking": tracking, "station": "IOS", "duration": "1.0",
                        "video": (io.BytesIO(data), name)})


@pytest.fixture(scope="module")
def two_orgs(appmod):
    return _mk_org(appmod, "orga"), _mk_org(appmod, "orgb")


# ───────────────── verified: these hold today ─────────────────

def test_holds_cross_org_mobile_endpoints(appmod, two_orgs):
    """Every endpoint pick.js / mobile.js / the Swift client call, as each role of org B
    against org A's shipment: nothing is read and nothing changes."""
    A = appmod; orga, orgb = two_orgs
    trk = "TRKA" + uuid.uuid4().hex[:10].upper()
    sid = _ship(A, orga, trk, label="A-only show")
    for role in ROLES:
        c = _as(A, "%s-%s" % (orgb, role))
        assert (c.get("/api/shipment/" + trk).get_json() or {}).get("ok") is False, role
        r = c.get("/api/pick/" + sid)
        assert r.status_code == 403 or r.get_json().get("ok") is False, role
        for path in ("/api/pick/complete/" + sid, "/api/pick/issue/" + sid):
            r = c.post(path, headers=c.csrf, json={"reason": "x"})
            assert r.status_code == 403 or r.get_json().get("ok") is False, (role, path)
        body = c.get("/api/shows").get_data(as_text=True) + c.get("/m/api/pick/extras").get_data(as_text=True)
        assert "A-only show" not in body, role
        _upload(c, trk)                                   # lands in org B's own log, never on org A
    assert _status(A, orga, sid) == {"status": "pending", "picked_by": None, "packed_by": None}


def test_holds_cross_org_packing_video(appmod, two_orgs):
    """A packing video of org A cannot be fetched by org B, even with the exact file name;
    the R2 key of every media object starts with the owning org."""
    A = appmod; orga, orgb = two_orgs
    trk = "TRKV" + uuid.uuid4().hex[:10].upper()
    _ship(A, orga, trk)
    assert _upload(_as(A, orga + "-worker"), trk).get_json()["ok"]
    fn = [f for f in os.listdir(A.video_dir(orga)) if trk in f][0]
    assert _as(A, orga + "-admin").get("/media/video/" + fn).status_code == 200
    assert _as(A, orgb + "-admin").get("/media/video/" + fn).status_code == 404
    assert _as(A, orga + "-worker").get("/media/video/" + fn).status_code == 403     # admin/cs only
    assert A.app.test_client().get("/media/video/" + fn).status_code in (301, 302)
    assert A._r2_media_key("videos", fn, orga) == "%s/videos/%s" % (orga, fn)


def test_holds_session_csrf_and_cookie_flags(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    c, r = _password_login(A, orga + "-worker")
    assert r.get_json()["ok"]
    sc = [h for h in r.headers.getlist("Set-Cookie") if h.startswith("session=")][0]
    assert "HttpOnly" in sc and "Secure" in sc and "SameSite=Lax" in sc
    for path in ("/api/pick/item/1/toggle", "/api/upload", "/api/account/delete"):
        assert c.post(path).status_code == 403, path                 # no X-CSRF-Token
    anon = A.app.test_client()
    for path in ("/m/pick", "/m/api/pick/extras", "/api/shows", "/api/shipment/X1", "/api/pick/my-stats"):
        assert anon.get(path).status_code in (301, 302), path
    s = anon.get("/api/mobile/session")
    assert s.get_json()["signed_in"] is False and "user" not in s.get_json()
    assert "Access-Control-Allow-Origin" not in s.headers


def test_holds_label_purchase_fenced_to_owner_orgs(appmod, two_orgs):
    """The shared carrier account can only BUY for the founding org(s)."""
    A = appmod; _, orgb = two_orgs
    c = _as(A, orgb + "-admin")
    for path in ("/api/label/buy", "/api/label/buy-multi"):
        assert c.post(path, headers=c.csrf, json={"shipment_id": "x", "rate_id": "y"}).status_code == 403, path


def test_holds_unenrolled_admin_and_suspended_org_are_held(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    c, r = _password_login(A, orga + "-admin")
    assert r.get_json().get("must_setup_2fa") is True
    assert c.get("/api/shows").status_code == 403 and c.get("/api/users").status_code == 403
    org = _mk_org(A, "susp")
    w = _as(A, org + "-worker")
    assert w.get("/api/shows").status_code == 200
    p = A.pdb(); p.execute("UPDATE organizations SET active=0 WHERE org_id=?", (org,)); p.commit(); p.close()
    assert w.get("/api/shows").status_code == 402
    assert _password_login(A, org + "-worker")[1].status_code == 403


def test_holds_support_tickets_are_per_org(appmod, two_orgs):
    A = appmod; orga, orgb = two_orgs
    a = _as(A, orga + "-cs")
    r = a.post("/api/support/tickets", headers=a.csrf, json={"subject": "secret-subject-A", "body": "b"}).get_json()
    assert r["ok"]
    tid = r.get("id") or r.get("ticket_id") or (r.get("ticket") or {}).get("id")
    b = _as(A, orgb + "-admin")
    assert "secret-subject-A" not in b.get("/api/support/tickets").get_data(as_text=True)
    if tid:
        rr = b.get("/api/support/tickets/%s" % tid)
        assert "secret-subject-A" not in rr.get_data(as_text=True)


# ───────────────── open findings (strict xfail) ─────────────────

# SEC-1 fixed (2FA is decided on the effective roles) — runs as a normal test now.
# More cases: tests/test_sec1_2fa_effective_roles.py
def test_sec1_extra_role_admin_must_enroll_2fa(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    adm = _as(A, orga + "-admin")
    u = "shadow" + uuid.uuid4().hex[:6]
    assert adm.post("/api/users/add", headers=adm.csrf, json={
        "username": u, "password": PW, "name": "Shadow", "role": "worker", "extra_roles": ["admin"]}).get_json()["ok"]
    c, r = _password_login(A, u)
    assert r.get_json()["ok"]
    # /api/users is req_true_admin: reaching it means this session IS an admin.
    reached_admin = c.get("/api/users").status_code == 200
    assert not reached_admin or r.get_json().get("must_setup_2fa") is True


@pytest.mark.xfail(strict=True, reason="SEC-2: a badge scan alone opens an admin session (no password, no 2FA)")
def test_sec2_badge_login_never_yields_admin(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    adm = _as(A, orga + "-admin")
    u = "floor" + uuid.uuid4().hex[:6]
    badge = adm.post("/api/users/add", headers=adm.csrf, json={
        "username": u, "password": PW, "name": "Floor", "role": "worker"}).get_json()["badge_token"]
    assert adm.post("/api/users/roles", headers=adm.csrf, json={"username": u, "role": "admin"}).get_json()["ok"]
    c, r = _badge_login(A, badge)
    assert not (r.get_json().get("ok") and c.get("/api/users").status_code == 200)


@pytest.mark.xfail(strict=True, reason="SEC-3: twofa_exempt is honoured for any org, not only an isolated demo org")
def test_sec3_twofa_exempt_only_inside_a_sandbox_org(appmod, two_orgs):
    A = appmod; _, orgb = two_orgs                      # orgb is an ordinary paying tenant
    u = "exempt" + uuid.uuid4().hex[:6]
    with A.update_json(A.USERS_FILE) as users:
        users[u] = {"password": A._h(PW), "role": "admin", "name": "X", "org": orgb, "twofa_exempt": True}
    c, r = _password_login(A, u)
    assert r.get_json().get("must_setup_2fa") is True or c.get("/api/users").status_code != 200


@pytest.mark.xfail(strict=True, reason="SEC-4: no per-org outbound fence — a demo org can email anyone and call the owner's carrier / AI accounts")
def test_sec4_sandbox_org_sends_nothing_outside(appmod, monkeypatch):
    """Contract proposed in the report: organizations.sandbox=1 ⇒ no outbound side effect.
    (The column name is the programmer's call; what must hold is the last block.)"""
    A = appmod
    org = _mk_org(A, "demo")
    p = A.pdb()
    cols = {r[1] for r in p.execute("PRAGMA table_info(organizations)").fetchall()}
    if "sandbox" in cols:
        p.execute("UPDATE organizations SET sandbox=1 WHERE org_id=?", (org,)); p.commit()
    p.close()
    sent = []
    monkeypatch.setattr(A, "IS_STAGING", False)
    monkeypatch.setattr(A, "EMAIL_ENABLED", True)
    monkeypatch.setattr(A, "RESEND_ENABLED", True)
    monkeypatch.setattr(A, "_send_via_resend", lambda to, *a, **k: (sent.append(("email", to)) or (True, None)))
    monkeypatch.setattr(A, "SHIPSTATION_ENABLED", True)
    monkeypatch.setattr(A, "EASYPOST_ENABLED", True)
    monkeypatch.setattr(A, "_easypost_rates", lambda *a, **k: (sent.append(("carrier-rates", a[0])) or ("sid", [])))
    c = _as(A, org + "-admin")
    c.post("/api/email/test", headers=c.csrf, json={"to": "someone@outside.example"})
    c.post("/api/label/rates", headers=c.csrf, json={
        "to_address": {"street1": "1 A St", "city": "Davie", "state": "FL", "zip": "33328"},
        "from_address": {"street1": "2 B St", "zip": "33328"}, "weight_oz": 8})
    assert sent == []


@pytest.mark.xfail(strict=True, reason="SEC-5: the owner's carrier account number is shown to every tenant's admin/cs/manager")
def test_sec5_owner_carrier_account_not_disclosed_to_other_orgs(appmod, two_orgs, monkeypatch):
    A = appmod; _, orgb = two_orgs
    monkeypatch.setattr(A, "UPS_ENABLED", True)
    monkeypatch.setattr(A, "UPS_ACCOUNT_NUMBER", "ZZ99TEST")          # fake value
    monkeypatch.setattr(A, "_ups_token", lambda *a, **k: "t")
    for role in ("admin", "cs", "manager"):
        c = _as(A, "%s-%s" % (orgb, role))
        assert "ZZ99TEST" not in c.get("/api/ship/carriers").get_data(as_text=True), role


@pytest.mark.xfail(strict=True, reason="SEC-6: deleting an org leaves its TikTok tokens (and R2 media) behind")
def test_sec6_org_wipe_removes_platform_rows_and_media(appmod, monkeypatch):
    A = appmod
    org = _mk_org(A, "gone")
    p = A.pdb()
    p.execute("INSERT INTO tiktok_shops(org_id,shop_id,shop_name,access_token,refresh_token,active) "
              "VALUES(?,?,?,?,?,1)", (org, "shop-" + org, "Shop", "fake-access", "fake-refresh"))
    p.commit(); p.close()

    class FakeR2:                                         # records what the wipe asks storage to do
        calls = []
        def __getattr__(self, name):
            def f(*a, **k):
                FakeR2.calls.append(name)
                return {"Contents": [], "KeyCount": 0}
            return f
    with A.update_json(A.USERS_FILE) as users:            # leave exactly one admin
        for k in [k for k, v in users.items() if v.get("org") == org and k != org + "-admin"]:
            del users[k]
    c = _as(A, org + "-admin")
    monkeypatch.setattr(A, "r2", FakeR2())
    r = c.post("/api/account/delete", headers=c.csrf, json={"wipe_org": True})
    monkeypatch.setattr(A, "r2", None)
    assert r.get_json().get("org_deleted") is True
    p = A.pdb()
    left = p.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=?", (org,)).fetchone()[0]
    p.close()
    problems = []
    if left:
        problems.append("TikTok shop tokens of the deleted org are still stored")
    if not any(n.startswith("delete") for n in FakeR2.calls):
        problems.append("storage was never asked to delete the org's objects (calls: %r)" % FakeR2.calls)
    assert not problems, problems


@pytest.mark.xfail(strict=True, reason="SEC-7: account / organization deletion needs no re-authentication")
def test_sec7_account_delete_requires_password(appmod):
    A = appmod
    org = _mk_org(A, "reauth")
    c = _as(A, org + "-worker")
    r = c.post("/api/account/delete", headers=c.csrf, json={})        # session cookie only
    assert r.status_code in (400, 401, 403) and (org + "-worker") in A.ldj(A.USERS_FILE)


@pytest.mark.xfail(strict=True, reason="SEC-8: a Host can read any order (address, fees) and mark it packed")
def test_sec8_host_cannot_pack_or_read_orders(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    trk = "TRKH" + uuid.uuid4().hex[:10].upper()
    sid = _ship(A, orga, trk)
    c = _as(A, orga + "-host")
    assert c.get("/m/pick").status_code == 403                        # the screen is closed to a host…
    look = c.get("/api/shipment/" + trk)
    leaked = "address_full" in ((look.get_json() or {}).get("shipment") or {}) if look.is_json else False
    _upload(c, trk)
    assert not leaked and _status(A, orga, sid)["status"] == "pending"


@pytest.mark.xfail(strict=True, reason="SEC-9: /api/upload stores any bytes as a packing video")
def test_sec9_upload_rejects_non_video(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    trk = "TRKX" + uuid.uuid4().hex[:10].upper()
    r = _upload(_as(A, orga + "-worker"), trk, data=b"<html><script>alert(1)</script></html>", name="x.html")
    stored = [f for f in os.listdir(A.video_dir(orga)) if trk in f]
    assert r.get_json().get("ok") is False and stored == []


@pytest.mark.xfail(strict=True, reason="SEC-10: a password reset (or logout) does not end the sessions already issued")
def test_sec10_password_reset_revokes_old_sessions(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    u = "sess" + uuid.uuid4().hex[:6]
    with A.update_json(A.USERS_FILE) as users:
        users[u] = {"password": A._h(PW), "role": "worker", "name": "S", "org": orga}
    c, r = _password_login(A, u)
    assert c.get("/api/shows").status_code == 200
    adm = _as(A, orga + "-admin")
    assert adm.post("/api/users/pw", headers=adm.csrf, json={"username": u, "password": "N3w-Passw0rd!"}).get_json()["ok"]
    assert c.get("/api/shows").status_code in (301, 302, 401)


@pytest.mark.xfail(strict=True, reason="SEC-11: login throttle is per (IP, username) only — no per-account cap")
def test_sec11_login_lockout_is_per_account(appmod, two_orgs):
    A = appmod; orga, _ = two_orgs
    codes = []
    for i in range(30):                                   # 30 wrong passwords, each from another address
        codes.append(_password_login(A, orga + "-cs", "wrong-%d" % i,
                                     {"X-Forwarded-For": "198.51.100.%d" % i})[1].status_code)
    assert 429 in codes


@pytest.mark.xfail(strict=True, reason="SEC-12: TikTok OAuth state is not bound to the session that started it")
def test_sec12_tiktok_callback_needs_the_initiating_session(appmod, two_orgs, monkeypatch):
    A = appmod; orga, _ = two_orgs
    shop = "victim-" + uuid.uuid4().hex[:6]
    monkeypatch.setattr(A, "_tt_token_exchange", lambda code: {"data": {
        "access_token": "fake-a", "refresh_token": "fake-r", "open_id": "o", "seller_name": "Victim"}})
    monkeypatch.setattr(A, "_tt_get_shops", lambda tok: {"data": {"shops": [{"id": shop, "name": "Victim shop"}]}})
    state = A._tt_state(orga)                              # minted for an org-A admin ("the attacker")
    A.app.test_client().get("/api/tiktok/callback?code=abc&state=" + state)   # opened by someone else, signed out
    p = A.pdb()
    n = p.execute("SELECT COUNT(*) FROM tiktok_shops WHERE org_id=? AND shop_id=?", (orga, shop)).fetchone()[0]
    p.close()
    assert n == 0, "a shop authorised by another browser was attached to org A"


@pytest.mark.xfail(strict=True, reason="SEC-13: hire-document reader falls back to the founding tenant's un-prefixed key for every org")
def test_sec13_hire_doc_legacy_fallback_only_for_founding_org(appmod, two_orgs):
    A = appmod; _, orgb = two_orgs
    tail = "hire_uploads/7/3/id_%s.png" % uuid.uuid4().hex[:6]
    os.makedirs(A.HIRE_LOCAL_UPLOAD_DIR, exist_ok=True)
    with open(os.path.join(A.HIRE_LOCAL_UPLOAD_DIR, tail.replace("/", "__")), "wb") as f:
        f.write(b"FOUNDING-TENANT-ID-PHOTO")              # a pre-namespacing object of the founding tenant
    c = A.sdb(orgb)                                        # org B's own row, whose own object is absent
    cur = c.execute("INSERT INTO onboarding_uploads(hire_id,step_id,field_name,original_filename,storage_key) "
                    "VALUES(7,3,'id','id.png',?)", (orgb + "/" + tail,))
    up = cur.lastrowid; c.commit(); c.close()
    r = _as(A, orgb + "-admin").get("/api/hires/7/upload/%d" % up)
    assert b"FOUNDING-TENANT-ID-PHOTO" not in r.data


@pytest.mark.xfail(strict=True, reason="SEC-14: /api/orgs/create is wired to the helper, not the view — creating a company returns 500")
def test_sec14_platform_owner_can_create_an_org(appmod):
    A = appmod
    with A.update_json(A.USERS_FILE) as users:
        users["plat-owner"] = {"password": A._h(PW), "role": "superadmin", "name": "P", "org": A.PLATFORM_ORG}
    c = _as(A, "plat-owner")
    A.app.config["PROPAGATE_EXCEPTIONS"] = False
    try:
        r = c.post("/api/orgs/create", headers=c.csrf, json={
            "org_id": "new" + uuid.uuid4().hex[:6], "company_name": "New Co",
            "admin_username": "new" + uuid.uuid4().hex[:6]})
    finally:
        A.app.config["PROPAGATE_EXCEPTIONS"] = None
    assert r.status_code == 200 and r.get_json()["ok"]
