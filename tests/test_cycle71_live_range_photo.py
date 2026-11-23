"""Cycle-71: Live Mode — one photo applied to a whole sticker range (photo-only: identify later,
no product bound, no stock moved). /api/live/sticker-photo-range stamps show_product_map.photo_url
for every sticker in the list."""
import io
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def test_range_photo_stamps_every_sticker_no_stock(appmod, client):
    A = appmod; hdr = _admin(client, A)
    label = "HERA Live " + uuid.uuid4().hex[:5]
    data = {"show": label, "part": "1", "stickers": "8,9,10,11,12",
            "file": (io.BytesIO(b"\xff\xd8\xffjpg"), "r.jpg")}
    r = client.post("/api/live/sticker-photo-range", data=data, headers=hdr,
                    content_type="multipart/form-data").get_json()
    assert r["ok"] is True and r["count"] == 5
    c = A.sdb(A.DEFAULT_ORG)
    rows = c.execute("""SELECT sticker_sku, photo_url, product_sku FROM show_product_map
                        WHERE import_label=? AND part=1 ORDER BY sticker_sku""", (label,)).fetchall()
    c.close()
    got = {row["sticker_sku"]: row for row in rows}
    for s in ("8", "9", "10", "11", "12"):
        assert s in got and got[s]["photo_url"]          # photo stamped
        assert (got[s]["product_sku"] or "") == ""        # photo-only: no product bound
    # all five share the one uploaded image
    assert len({got[s]["photo_url"] for s in ("8", "9", "10", "11", "12")}) == 1


def test_range_photo_requires_stickers(appmod, client):
    A = appmod; hdr = _admin(client, A)
    data = {"show": "X", "part": "0", "stickers": "",
            "file": (io.BytesIO(b"\xff\xd8\xffjpg"), "r.jpg")}
    r = client.post("/api/live/sticker-photo-range", data=data, headers=hdr,
                    content_type="multipart/form-data").get_json()
    assert r["ok"] is False
