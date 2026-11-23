"""Cycle-64: Warehouse Analytics 'by show'. For a date range, break the packed packages down by
live — which lives were packed, how complete each one is, and how many lives closed (and %).
Also: show pack-time is REAL labor (sum of pack durations), never wall-clock across nights."""
import csv
import os
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _ship(A, label, status, trk, total_items=1):
    c = A.sdb(A.DEFAULT_ORG)
    sid = "S" + uuid.uuid4().hex[:8]
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label,tracking_code,total_items)
                 VALUES(?,?,'tiktok','b',?,?,?)""", (sid, status, label, trk, total_items))
    c.commit(); c.close()


def _write_log(A, rows):
    path = A.log_file(A.DEFAULT_ORG)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "worker", "station", "duration_seconds", "tracking_number"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def test_by_show_and_lives_closed(appmod, client):
    A = appmod; _admin(client, A)
    LA = "LIVE A " + uuid.uuid4().hex[:4]
    LB = "LIVE B " + uuid.uuid4().hex[:4]
    # LIVE A: 2 orders, both packed → 100% → closed. LIVE B: 2 orders, 1 packed → 50% → not closed.
    _ship(A, LA, "packed", "A1"); _ship(A, LA, "packed", "A2")
    _ship(A, LB, "packed", "B1"); _ship(A, LB, "pending", "B2")
    _write_log(A, [
        {"date": "2026-11-10", "worker": "maria", "station": "1", "duration_seconds": "20", "tracking_number": "A1"},
        {"date": "2026-11-10", "worker": "maria", "station": "1", "duration_seconds": "30", "tracking_number": "A2"},
        {"date": "2026-11-10", "worker": "test6", "station": "2", "duration_seconds": "40", "tracking_number": "B1"},
    ])
    d = client.get("/api/packer-analytics?from=2026-11-10&to=2026-11-10").get_json()
    assert d["ok"] is True
    shows = {s["label"]: s for s in d["shows"]}
    assert shows[LA]["packages"] == 2 and shows[LA]["pct_complete"] == 100 and shows[LA]["closed"] is True
    assert shows[LB]["packages"] == 1 and shows[LB]["pct_complete"] == 50 and shows[LB]["closed"] is False
    assert d["lives"]["touched"] == 2 and d["lives"]["closed"] == 1 and d["lives"]["pct_closed"] == 50


def test_show_health_pack_time_is_real_labor(appmod, client):
    A = appmod; _admin(client, A)
    L = "LIVE " + uuid.uuid4().hex[:4]
    _ship(A, L, "packed", "T1"); _ship(A, L, "packed", "T2")
    _write_log(A, [
        {"date": "2026-11-10", "worker": "m", "station": "1", "duration_seconds": "25", "tracking_number": "T1"},
        {"date": "2026-11-10", "worker": "m", "station": "1", "duration_seconds": "35", "tracking_number": "T2"},
    ])
    d = client.get("/api/show/health?show=" + L).get_json()
    assert d["worked_sec"] == 60            # 25 + 35 real seconds, not a multi-hour wall-clock span
