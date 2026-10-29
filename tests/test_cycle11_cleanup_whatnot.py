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
    # picked=1 so the cancelled item counts for a tiktok-api shipment
    sid = _show_with_cancelled(c, lbl, "tiktok", "tiktok-api", picked=1)
    c.close()
    r = admin.get("/api/pick/" + sid).get_json()
    assert r["ok"] is True
    assert r["cleanup_blocked"] is True             # TikTok still gated


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
