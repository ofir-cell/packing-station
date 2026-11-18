"""Cycle-53: the Shows board loads a short window by default and extends a week at a time.
Invariant that must hold: a show with pending work ALWAYS appears regardless of age — only
FINISHED (DONE) shows age out of the window — so the floor never loses an open/back-dated show.
`?meta=1` adds has_more so the board can show/hide 'Load more'."""
import uuid
from datetime import datetime, timedelta


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _mkshow(A, label, days_ago, status="pending"):
    """One shipment in `label`, imported `days_ago` days ago, with the given status."""
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:8]
    ts = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,imported_at) "
              "VALUES(?,?,'tiktok','tiktok-api',?,?)", (sid, status, label, ts))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity) "
              "VALUES(?,?,?,?,1)", (sid, "O" + sid, "100", "Serum Part 1"))
    c.commit(); c.close()
    return label


def _names(resp):
    return {s["name"] for s in resp}


def test_default_window_hides_old_done_keeps_open(appmod, client):
    A = appmod; _admin(client, A)
    recent = _mkshow(A, "RECENT " + uuid.uuid4().hex[:4], days_ago=2, status="pending")
    old_open = _mkshow(A, "OLDOPEN " + uuid.uuid4().hex[:4], days_ago=40, status="pending")
    old_done = _mkshow(A, "OLDDONE " + uuid.uuid4().hex[:4], days_ago=40, status="packed")
    # mark the old packed show DONE so it ages out
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO show_state(import_label,done,done_by,done_at) VALUES(?,1,'t',datetime('now'))",
              (old_done,)); c.commit(); c.close()

    d = client.get("/api/shows?meta=1&days=7").get_json()
    names = _names(d["shows"])
    assert recent in names            # within the 7-day window
    assert old_open in names          # 40 days old BUT still pending → always shown (the invariant)
    assert old_done not in names      # 40 days old AND done → aged out of the 7-day window
    assert d["has_more"] is True      # a wider window would reveal the hidden done show


def test_load_more_reveals_old_done(appmod, client):
    A = appmod; _admin(client, A)
    old_done = _mkshow(A, "OD " + uuid.uuid4().hex[:4], days_ago=40, status="packed")
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO show_state(import_label,done,done_by,done_at) VALUES(?,1,'t',datetime('now'))",
              (old_done,)); c.commit(); c.close()

    assert old_done not in _names(client.get("/api/shows?meta=1&days=7").get_json()["shows"])
    wide = client.get("/api/shows?meta=1&days=60").get_json()
    assert old_done in _names(wide["shows"])   # now inside the widened window


def test_bare_array_still_returned_without_meta(appmod, client):
    A = appmod; _admin(client, A)
    _mkshow(A, "B " + uuid.uuid4().hex[:4], days_ago=1)
    d = client.get("/api/shows").get_json()
    assert isinstance(d, list)   # every other caller keeps the old bare-array contract
