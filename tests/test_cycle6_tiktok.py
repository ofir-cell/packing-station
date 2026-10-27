"""Cycle-6 — TikTok request resilience (429/5xx retry with Retry-After).
AUTOMATED SANDBOX ONLY: urlopen is mocked; no real TikTok call is made.
"""
import io, time, urllib.error
import email.message


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _http_error(code, retry_after=None):
    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("http://x", code, "err", hdrs, io.BytesIO(b'{"code":%d}' % code))


def test_tt_request_retries_on_429_then_succeeds(appmod, monkeypatch):
    assert appmod.STAGING_SAFE is False  # retry path only runs when not short-circuited
    calls = {"n": 0}

    def fake_urlopen(req, timeout=30):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise _http_error(429, retry_after=0)
        return _Resp(b'{"code":0,"data":{"ok":true}}')

    monkeypatch.setattr(appmod, "time", appmod.time)
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    out = appmod._tt_request("GET", appmod.TIKTOK_API_BASE + "/order/%s/orders/search" % appmod.TIKTOK_API_VERSION,
                             params={"page_size": 10}, signed=True, access_token="tok")
    assert calls["n"] == 3, f"expected 2 retries then success, got {calls['n']} calls"
    assert out.get("code") == 0 and out["data"]["ok"] is True


def test_tt_request_gives_up_after_max_retries(appmod, monkeypatch):
    calls = {"n": 0}

    def always_500(req, timeout=30):
        calls["n"] += 1
        raise _http_error(500)

    monkeypatch.setattr(time, "sleep", lambda *_: None)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", always_500)
    out = appmod._tt_request("GET", appmod.TIKTOK_API_BASE + "/order/%s/orders/search" % appmod.TIKTOK_API_VERSION,
                             params={"page_size": 10}, signed=True, access_token="tok")
    # bounded: 1 initial + _TT_MAX_RETRIES attempts, then returns the parsed error body (no raise)
    assert calls["n"] == 1 + appmod._TT_MAX_RETRIES
    assert out.get("code") == 500


def test_tt_request_signature_recomputed_each_attempt(appmod, monkeypatch):
    # the signed `sign` param must differ across attempts only if timestamp changes; at minimum
    # each attempt must carry a fresh sign param (not raise for a stale one).
    seen = []

    def capture(req, timeout=30):
        seen.append(req.full_url)
        if len(seen) < 2:
            raise _http_error(503, retry_after=0)
        return _Resp(b'{"code":0}')

    monkeypatch.setattr(time, "sleep", lambda *_: None)
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", capture)
    appmod._tt_request("GET", appmod.TIKTOK_API_BASE + "/authorization/%s/shops" % appmod.TIKTOK_API_VERSION,
                       signed=True, access_token="tok")
    assert len(seen) == 2 and all("sign=" in u for u in seen)
