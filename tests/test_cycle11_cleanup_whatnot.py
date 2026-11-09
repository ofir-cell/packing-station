"""Cycle-11: Whatnot shows are exempt from the cancelled-items cleanup gate too.
TikTok shows still blocked. The gate is checked via the real /api/pick route."""
import uuid


def _show_with_cancelled(c, label, platform, batch, picked=0):
    sid = (platform[:2] + "S" + uuid.uuid4().hex[:8]).upper()
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label)
                 VALUES(?,?,?,?,?)""", (sid, "pending", platform, batch, label))
    c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,cancelled,picked)
                 VALUES(?,?,?,?,?,1,?)""", (sid, "O-" + sid, "101", "BEAUTY Mix Pull #101", 1, picked))
    c.commit()
    return sid


def test_whatnot_cancelled_items_do_not_block_pick(appmod, admin, sdb):
    c = sdb()
    lbl = "WN Live " + uuid.uuid4().hex[:5]
    sid = _show_with_cancelled(c, lbl, "whatnot", "csv-import")
    c.close()
    r = admin.get("/api/pick/" + sid).get_json()
    assert r["ok"] is True
    assert r["cleanup_blocked"] is False            # exempt — not blocked
    assert r["cleanup"]["has_cancellations"] is True  # data stays honest


def test_tiktok_cancelled_items_still_block_pick(appmod, admin, sdb):
    c = sdb()
    lbl = "TT Live " + uuid.uuid4().hex[:5]
    sid = _show_with_cancelled(c, lbl, "tiktok", "tiktok-api", picked=1)
    c.close()
    r = admin.get("/api/pick/" + sid).get_json()
    assert r["ok"] is True
    assert r["cleanup_blocked"] is True             # TikTok gated


def test_tiktok_cancelled_unpicked_now_counts(appmod, admin, sdb):
    """Fix: TikTok cancellations count for cleanup even before the item is individually
    picked — the warehouse bulk-pulls the show's stock, so a cancellation is on the table
    and must be cleared, exactly like Whatnot. (Previously hidden until picked → showed 0.)"""
    c = sdb()
    lbl = "TT Live " + uuid.uuid4().hex[:5]
    sid = _show_with_cancelled(c, lbl, "tiktok", "tiktok-api", picked=0)
    c.close()
    r = admin.get("/api/pick/" + sid).get_json()
    assert r["cleanup"]["has_cancellations"] is True   # now visible as cleanup work
    assert r["cleanup_blocked"] is True


def test_mark_cleared_then_finish_lets_picking_start(appmod, admin, sdb):
    """After marking every cancelled group cleared, the show is clean and the cleanout
    hand-off succeeds — i.e. the worker can finish cleanup and move to picking."""
    c = sdb()
    lbl = "TT Finish " + uuid.uuid4().hex[:5]
    sid = _show_with_cancelled(c, lbl, "tiktok", "tiktok-api", picked=0)
    c.close()
    # still blocked before clearing
    assert admin.get("/api/pick/" + sid).get_json()["cleanup_blocked"] is True
    # mark the (sku, part) group removed
    r = admin.post("/api/cleanup/" + lbl + "/mark", json={"sku": "101", "part": "", "removed": True},
                   headers=getattr(admin, "csrf", {"X-CSRF-Token": "tok"})).get_json()
    assert r["ok"] and r["is_clean"] is True            # table is now clean
    # the hand-off (cleanout) that the "start picking" button calls succeeds
    co = admin.post("/api/show/cleanout", json={"label": lbl},
                    headers=getattr(admin, "csrf", {"X-CSRF-Token": "tok"})).get_json()
    assert co.get("ok") is True
    # and picking is no longer blocked
    assert admin.get("/api/pick/" + sid).get_json()["cleanup_blocked"] is False


def test_shows_list_marks_whatnot_clean(appmod, admin, sdb):
    c = sdb()
    lbl = "WN Shows " + uuid.uuid4().hex[:5]
    _show_with_cancelled(c, lbl, "whatnot", "csv-import")
    c.close()
    shows = admin.get("/api/shows").get_json()
    row = next((d for d in shows if d["name"] == lbl), None)
    assert row is not None
    assert row["cleanup"]["is_clean"] is True       # no dirty pill / no hard block
    assert row["needs_cleanout"] is False
