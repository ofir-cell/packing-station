"""Cycle-63: per-show fulfilment health. The home backlog rows now carry % picked + wall-clock
time worked, and /api/show/health reports a show's status mix plus the four 'stuck' buckets —
overdue, picked-but-not-packed-too-long, abandoned picks, flagged issues."""
import time
import uuid
from datetime import datetime, timedelta


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _mk(A, label, status, ship_by=None, picked_at=None, pick_started_by=None,
        pick_started_at=None, packed_at=None, flag_reason=None):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:8]
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,ship_by,
                 picked_at,pick_started_by,pick_started_at,packed_at,flag_reason,imported_at)
                 VALUES(?,?,'tiktok','b',?,?,?,?,?,?,?,datetime('now'))""",
              (sid, status, label, ship_by or 0, picked_at, pick_started_by, pick_started_at, packed_at, flag_reason))
    c.commit(); c.close()
    return sid


def test_show_health_buckets(appmod, client):
    A = appmod; _admin(client, A)
    L = "LIVE " + uuid.uuid4().hex[:4]
    now = int(time.time())
    old = (datetime.now() - timedelta(hours=10)).isoformat(timespec="seconds")
    start = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
    _mk(A, L, "packed", packed_at=start, pick_started_at=start)        # packed
    _mk(A, L, "picked", picked_at=old, pick_started_at=old)            # picked-stale
    _mk(A, L, "pending", pick_started_by="Dana", pick_started_at=start)  # abandoned
    _mk(A, L, "pending", ship_by=now - 3600)                           # overdue
    _mk(A, L, "issue", flag_reason="damaged")                         # issue

    d = client.get("/api/show/health?show=" + L).get_json()
    assert d["ok"] is True
    assert d["counts"]["total"] == 5 and d["counts"]["packed"] == 1
    assert d["stuck"]["picked_stale"]["count"] == 1
    assert d["stuck"]["abandoned"]["count"] == 1
    assert d["stuck"]["overdue"]["count"] == 1
    assert d["stuck"]["issues"]["count"] == 1
    assert d["pct_packed"] == 20                                       # 1 of 5
    assert d["worked_sec"] > 0                                         # wall-clock since first activity


def test_today_backlog_has_picked_and_worked(appmod, client):
    A = appmod; _admin(client, A)
    L = "BL " + uuid.uuid4().hex[:4]
    start = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    _mk(A, L, "pending")                                   # keeps the show in the backlog (pending>0)
    _mk(A, L, "picked", pick_started_at=start, picked_at=start)
    d = client.get("/api/today").get_json()
    row = next((s for s in d["backlog"]["shows"] if s["name"] == L), None)
    assert row is not None
    assert "pct_picked" in row and row["pct_picked"] == 50            # 1 picked of 2
    assert row["worked_sec"] > 0
