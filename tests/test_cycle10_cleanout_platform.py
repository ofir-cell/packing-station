"""Cycle-10: table-cleanout gate is TikTok-only; Whatnot shows are exempt."""
import uuid


def _mk_show(c, label, platform, status="pending"):
    sid = f"S-{uuid.uuid4().hex[:8]}"
    c.execute("""INSERT INTO shipments(shipment_id,status,platform,import_batch,import_label)
                 VALUES(?,?,?,?,?)""",
              (sid, status, platform, platform + "-batch", label))
    c.execute("""INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity)
                 VALUES(?,?,?,?,1)""", (sid, "O-" + sid, "SK1", "Thing"))
    c.commit()
    return sid


def test_whatnot_show_never_needs_cleanout(appmod, sdb):
    c = sdb()
    lbl = "WN Show " + uuid.uuid4().hex[:5]
    _mk_show(c, lbl, "whatnot")
    assert appmod._show_platform(c, lbl) == "whatnot"
    assert appmod._show_needs_cleanout(c, lbl) is False   # exempt
    c.close()


def test_tiktok_show_still_needs_cleanout_until_marked(appmod, sdb):
    c = sdb()
    lbl = "TT Show " + uuid.uuid4().hex[:5]
    _mk_show(c, lbl, "tiktok")
    assert appmod._show_platform(c, lbl) == "tiktok"
    assert appmod._show_needs_cleanout(c, lbl) is True    # still gated
    appmod._show_mark_cleanout(c, lbl, "tester")
    assert appmod._show_needs_cleanout(c, lbl) is False   # released after cleanout
    c.close()


def test_whatnot_show_with_no_pending_is_false_too(appmod, sdb):
    c = sdb()
    lbl = "WN Done " + uuid.uuid4().hex[:5]
    _mk_show(c, lbl, "whatnot", status="shipped")
    assert appmod._show_needs_cleanout(c, lbl) is False
    c.close()
