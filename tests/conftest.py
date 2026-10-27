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
        with appmod.app.test_request_context():
            from flask import session
            session["org"] = appmod.DEFAULT_ORG
            return appmod.sdb(appmod.DEFAULT_ORG)
    return _open
