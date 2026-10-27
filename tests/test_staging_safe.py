"""Staging safe mode: external side effects are blocked even when prod creds are present,
and R1-R3 logic still works (local fixtures, mocked external)."""
import json, hmac, hashlib, uuid
import pytest


def _sign(A, body):
    return hmac.new(A.TIKTOK_APP_SECRET.encode(), A.TIKTOK_APP_KEY.encode() + body, hashlib.sha256).hexdigest()


@pytest.fixture
def safe(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "STAGING_SAFE", True)
    return appmod


# ── external egress is blocked (no network) ──────────────────────────────────
def test_tiktok_request_blocked(safe):
    r = safe._tt_request("GET", "https://open-api.tiktokglobalshop.com/x")
    assert r.get("code") == "SAFE_MODE"          # returns sentinel, no network call


def test_shipstation_blocked(safe):
    with pytest.raises(RuntimeError):
        safe._ss("GET", "/v2/labels")


def test_usps_token_blocked(safe):
    with pytest.raises(RuntimeError):
        safe._usps_token()


def test_ups_token_blocked(safe):
    with pytest.raises(RuntimeError):
        safe._ups_token()


def test_r2_wrapper_blocks_writes_allows_reads(appmod):
    class _Inner:
        def put_object(self, **k): return {"real": True}
        def head_object(self, **k): return {"read": "ok"}
    w = appmod._SafeR2(_Inner())
    assert w.put_object(Bucket="b", Key="k", Body=b"x") == {"SafeMode": True}   # write blocked
    assert w.head_object(Bucket="b", Key="k") == {"read": "ok"}                 # read passes through


# ── email + postage already blocked by IS_STAGING ────────────────────────────
def test_email_suppressed_in_staging(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "IS_STAGING", True)
    ok, err = appmod._send_email("x@y.com", "subj", "<b>hi</b>")
    assert ok is True and err is None            # suppressed, nothing sent


def test_labels_blocked_in_staging(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "IS_STAGING", True)
    assert appmod._can_buy_labels() is False


# ── R1-R3 still work under safe mode ─────────────────────────────────────────
def test_r1_enforced_under_safe_mode(appmod, client, monkeypatch):
    monkeypatch.setattr(appmod, "STAGING_SAFE", True)
    sid = "S-" + uuid.uuid4().hex[:6]
    c = appmod.pdb(); c.execute("INSERT OR REPLACE INTO tiktok_shops(org_id,shop_id,active) VALUES(?,?,1)",
                                (appmod.DEFAULT_ORG, sid)); c.commit(); c.close()
    r = client.post("/api/tiktok/webhook", data=json.dumps({"type": 6, "shop_id": sid}))
    assert r.status_code == 401                  # unsigned still rejected
    body = json.dumps({"type": 6, "shop_id": sid}).encode()
    r2 = client.post("/api/tiktok/webhook", data=body, headers={"Authorization": _sign(appmod, body)})
    assert r2.status_code == 200                 # signed deauth still works in safe mode
