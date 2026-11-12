"""Shared fixtures: boots app.py once against a throwaway DATA_DIR.

Run: python3 -m pytest -q tests
"""
import os, sys, tempfile, pytest

_DATA = tempfile.mkdtemp(prefix="ps-test-")
os.environ.setdefault("SECRET_KEY", "t" * 40)
os.environ["DATA_DIR"] = _DATA
os.environ.setdefault("TIKTOK_APP_KEY", "testkey")
os.environ.setdefault("TIKTOK_APP_SECRET", "testsecret")
for k in ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "TIKTOK_WEBHOOK_ALLOW_UNSIGNED"):
    os.environ.pop(k, None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as A  # noqa: E402
import threading  # noqa: E402

# app.py starts its TikTok sweep thread at import. In a test process that thread polls
# every "connected" shop the tests seeded: it opened connections to TikTok's real hosts
# (with fake tokens) and, when a test had replaced app._tt_request with a fake, called
# that fake from the background at a random moment. Tests may still call the sweep
# themselves (main thread); the background thread does nothing here.
_real_tt_sweep_once = A._tt_sweep_once


def _tt_sweep_once_main_thread_only(*a, **k):
    if threading.current_thread() is threading.main_thread():
        return _real_tt_sweep_once(*a, **k)


A._tt_sweep_once = _tt_sweep_once_main_thread_only


@pytest.fixture(scope="session")
def appmod():
    return A


@pytest.fixture
def client(appmod):
    return appmod.app.test_client()


@pytest.fixture
def admin(client, appmod):
    """Client logged in as admin of the default org, with a valid CSRF cookie."""
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    client.csrf = {"X-CSRF-Token": "tok"}
    return client


@pytest.fixture
def sdb(appmod):
    """Shipments DB of the default org (outside a request)."""
    def _open():
        # opened OUTSIDE a request context on purpose: the explicit org makes the
        # request context unnecessary, and it keeps the connection from being swept
        # by the request-teardown cleanup (C4-2).
        return appmod.sdb(appmod.DEFAULT_ORG)
    return _open
