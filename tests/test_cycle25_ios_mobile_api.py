"""Cycle-25: backend support for the native iOS app (LiveOpsHub iOS).

- auth failures are JSON 401/403 for the iOS client (X-Client: lohub-ios/...), and
  unchanged (redirect / plain 403) for the browser
- /api/mobile/session bootstraps the app with a CSRF token that actually works on POST
- /api/upload stores iPhone MP4 recordings as .mp4 / video/mp4 (WebM path unchanged)
"""
import io, os, uuid

IOS = {"X-Client": "lohub-ios/1.0.0"}


def _sess(client, A, uname, role="worker"):
    with A.update_json(A.USERS_FILE) as users:
        users[uname] = {"password": "x", "role": role, "name": uname, "org": A.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=A.DEFAULT_ORG, name=uname)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


# ── auth failures ─────────────────────────────────────────────────────────────
def test_signed_out_ios_gets_json_401(client):
    r = client.get("/api/me/stats", headers=IOS)
    assert r.status_code == 401
    assert r.get_json()["error"] == "not_signed_in"


def test_signed_out_browser_still_redirects(client):
    r = client.get("/api/me/stats")
    assert r.status_code in (301, 302)


def test_ios_role_denied_is_json_403(client, appmod):
    _sess(client, appmod, "w_" + uuid.uuid4().hex[:6], "worker")
    r = client.get("/api/home/fulfillment", headers=IOS)      # admin/cs only
    assert r.status_code == 403 and r.get_json()["error"] == "forbidden"


def test_browser_role_denied_unchanged(client, appmod):
    _sess(client, appmod, "w_" + uuid.uuid4().hex[:6], "worker")
    r = client.get("/api/home/fulfillment")
    assert r.status_code == 403 and r.get_data(as_text=True) == "Access denied"


# ── session bootstrap ─────────────────────────────────────────────────────────
def test_mobile_session_signed_out_issues_single_working_token(client):
    r = client.get("/api/mobile/session", headers=IOS)
    j = r.get_json()
    assert r.status_code == 200 and j["ok"] and j["signed_in"] is False
    cookies = [h for h in r.headers.getlist("Set-Cookie") if h.startswith("csrf_token=")]
    assert len(cookies) == 1, cookies                 # no second, conflicting token
    assert cookies[0].startswith("csrf_token=" + j["csrf_token"] + ";")
    # the returned token passes the CSRF check on a real POST (login: wrong password)
    r2 = client.post("/api/login", json={"username": "nobody", "password": "x"},
                     headers={**IOS, "X-CSRF-Token": j["csrf_token"]})
    assert r2.status_code == 200 and r2.get_json()["ok"] is False


def test_mobile_session_signed_in_reports_user(client, appmod):
    uname = "w_" + uuid.uuid4().hex[:6]
    _sess(client, appmod, uname, "worker")
    j = client.get("/api/mobile/session", headers=IOS).get_json()
    assert j["signed_in"] and j["user"] == uname and j["role"] == "worker"
    assert j["roles"] == ["worker"] and j["org"] == appmod.DEFAULT_ORG
    assert j["csrf_token"] == "tok"                   # echoes the existing cookie
    assert "min_version" in j


# ── MP4 uploads ───────────────────────────────────────────────────────────────
MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 64
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64


def _latest_video(A, trk):
    files = [f for f in os.listdir(A.video_dir()) if trk in f]
    assert files, "no video stored"
    return files[0]


def test_is_mp4_detection(appmod):
    assert appmod._is_mp4(MP4)
    assert not appmod._is_mp4(WEBM)
    assert not appmod._is_mp4(b"")


def test_upload_mp4_stored_as_mp4(client, appmod):
    h = _sess(client, appmod, "w_" + uuid.uuid4().hex[:6], "worker")
    trk = "IOS" + uuid.uuid4().hex[:10].upper()
    r = client.post("/api/upload", headers={**IOS, **h}, content_type="multipart/form-data",
                    data={"tracking": trk, "duration": "12.5",
                          "video": (io.BytesIO(MP4), trk + ".mp4", "video/mp4")})
    assert r.status_code == 200 and r.get_json()["ok"]
    with appmod.app.test_request_context():
        from flask import session
        session["org"] = appmod.DEFAULT_ORG
        fn = _latest_video(appmod, trk)
        assert fn.endswith(".mp4")
        data = open(os.path.join(appmod.video_dir(), fn), "rb").read()
        assert data == MP4                             # not run through the WebM cleaner


def test_upload_webm_still_webm(client, appmod):
    h = _sess(client, appmod, "w_" + uuid.uuid4().hex[:6], "worker")
    trk = "WEB" + uuid.uuid4().hex[:10].upper()
    r = client.post("/api/upload", headers=h, content_type="multipart/form-data",
                    data={"tracking": trk, "duration": "3",
                          "video": (io.BytesIO(WEBM), trk + ".webm", "video/webm")})
    assert r.status_code == 200 and r.get_json()["ok"]
    with appmod.app.test_request_context():
        from flask import session
        session["org"] = appmod.DEFAULT_ORG
        assert _latest_video(appmod, trk).endswith(".webm")


# ── public legal pages ────────────────────────────────────────────────────────
def test_privacy_and_terms_are_public(client):
    for path, word in (("/privacy", "Privacy"), ("/terms", "Terms"), ("/privacy.html", "Privacy")):
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.content_type.startswith("text/html")
        assert word in r.get_data(as_text=True)


# ── iOS app entry point ───────────────────────────────────────────────────────
IOS_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) LiveOpsHubiOS/1.0.0 Mobile")


def test_signed_out_ios_app_starts_on_password_login(client):
    r = client.get("/", headers={"User-Agent": IOS_UA})
    assert r.status_code in (301, 302) and r.headers["Location"].endswith("/login")


def test_signed_out_browser_still_starts_on_badge_login(client):
    r = client.get("/", headers={"User-Agent": "Mozilla/5.0 (iPhone) Safari"})
    assert r.headers["Location"].endswith("/badge-login")


def test_badge_page_offers_camera_scan_only_inside_app(client):
    html = client.get("/badge-login").get_data(as_text=True)
    assert "window.LOHubNative&&LOHubNative.scan" in html     # guarded: hidden in browsers


def test_csp_allows_only_the_pinned_2fa_qr_script(client):
    csp = client.get("/login").headers.get("Content-Security-Policy", "")
    script = next(d for d in csp.split(";") if d.strip().startswith("script-src"))
    assert "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js" in script
    assert "https://cdnjs.cloudflare.com " not in script + " "   # not the whole CDN
