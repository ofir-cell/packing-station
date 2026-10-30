"""Daily-flow tests: the four things the warehouse does hundreds of times a day.

  1. A worker scans their badge and is logged in
  2. A pack recording is uploaded, stored in R2 under the tracking number, and the
     shipment is marked packed
  3. A Whatnot show CSV is imported: one package per buyer, all of its items
  4. CS looks up a tracking number and gets that package's video

Until now none of these had a test (QA review, Oct 29 2026). They use a fake R2
client, so nothing leaves the machine. The last test runs the whole day end to end.
"""
import io, uuid

import pytest

EBML = b"\x1a\x45\xdf\xa3"          # every .webm the recorder produces starts with this


# ── helpers ───────────────────────────────────────────────────────────────────
class FakeR2:
    """Stands in for the boto3 R2 client: records what would have been stored."""
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType=None, **kw):
        self.objects[Key] = bytes(Body)

    def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
        self.objects[key] = fileobj.read()

    def generate_presigned_url(self, op, Params=None, ExpiresIn=None):
        return "https://r2.example/%s?expires=%s" % (Params["Key"], ExpiresIn)


@pytest.fixture
def r2(appmod, monkeypatch):
    fake = FakeR2()
    monkeypatch.setattr(appmod, "r2", fake)
    monkeypatch.setattr(appmod, "R2_BUCKET", "test-bucket")
    return fake


def _csrf(client):
    # the app injects a fetch wrapper that sends this on every POST; tests do it by hand
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _badge_of(A, user):
    return A.ldj(A.USERS_FILE)[user]["badge_token"]


def _login_as(client, A, user, role, **extra):
    with client.session_transaction() as s:
        s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG, **extra)
    return _csrf(client)


def _whatnot_csv(rows):
    hdr = ["order_id", "shipment_id", "product_name", "product_quantity", "buyer_username",
           "shipping_address", "tracking_code", "original_item_price", "placed_at", "cancelled_or_failed"]
    out = io.StringIO()
    out.write(",".join(hdr) + "\n")
    for r in rows:
        out.write(",".join('"%s"' % str(r.get(h, "")) for h in hdr) + "\n")
    return out.getvalue().encode()


def _import(client, hdr, csv_bytes, label):
    return client.post("/api/shipments/import", headers=hdr, content_type="multipart/form-data",
                       data={"file": (io.BytesIO(csv_bytes), "show.csv"), "label": label})


def _shipment(A, sid):
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    items = c.execute("SELECT * FROM shipment_items WHERE shipment_id=?", (sid,)).fetchall()
    c.close()
    return (dict(row) if row else None), [dict(i) for i in items]


def _new_show(A):
    """Two buyers. Buyer A won two auctions that ship together in one package."""
    tag = uuid.uuid4().hex[:6].upper()
    pkgA, pkgB = "WN-A-" + tag, "WN-B-" + tag
    trkA, trkB = "9400111" + tag + "01", "9400111" + tag + "02"
    rows = [
        {"order_id": "O1-" + tag, "shipment_id": pkgA, "product_name": "Lip Oil #12", "product_quantity": 1,
         "buyer_username": "buyer_a", "shipping_address": "Ana Buyer, 1 Main St, Miami, FL 33101",
         "tracking_code": trkA, "original_item_price": "$9.00", "placed_at": "2026-10-29 19:05:00"},
        {"order_id": "O2-" + tag, "shipment_id": pkgA, "product_name": "Blush #3", "product_quantity": 1,
         "buyer_username": "buyer_a", "shipping_address": "Ana Buyer, 1 Main St, Miami, FL 33101",
         "tracking_code": trkA, "original_item_price": "$12.50", "placed_at": "2026-10-29 19:20:00"},
        {"order_id": "O3-" + tag, "shipment_id": pkgB, "product_name": "Serum #7", "product_quantity": 1,
         "buyer_username": "buyer_b", "shipping_address": "Ben Buyer, 2 Oak Ave, Davie, FL 33314",
         "tracking_code": trkB, "original_item_price": "$15.00", "placed_at": "2026-10-29 19:31:00"},
    ]
    return tag, (pkgA, trkA), (pkgB, trkB), _whatnot_csv(rows)


# ── 1. badge login ────────────────────────────────────────────────────────────
def test_badge_scan_logs_worker_in(appmod, client):
    A = appmod
    hdr = _csrf(client)
    r = client.post("/api/badge-login", json={"token": _badge_of(A, "worker1")}, headers=hdr)
    d = r.get_json()
    assert r.status_code == 200 and d["ok"] is True and d["role"] == "worker"
    with client.session_transaction() as s:
        assert s["user"] == "worker1" and s["org"] == A.DEFAULT_ORG


def test_badge_is_case_insensitive_like_a_scanner(appmod, client):
    A = appmod
    hdr = _csrf(client)
    r = client.post("/api/badge-login", json={"token": _badge_of(A, "worker2").lower()}, headers=hdr)
    assert r.get_json()["ok"] is True


def test_unknown_badge_is_refused(appmod, client, monkeypatch):
    A = appmod
    monkeypatch.setattr(A.time, "sleep", lambda s: None)
    hdr = _csrf(client)
    r = client.post("/api/badge-login", json={"token": "NOTAREALBADGE1"}, headers=hdr)
    assert r.get_json()["ok"] is False
    with client.session_transaction() as s:
        assert "user" not in s


# ── 2. pack upload ────────────────────────────────────────────────────────────
def test_pack_upload_stores_video_in_r2_and_marks_packed(appmod, client, r2):
    A = appmod
    sid, trk = "PKG-" + uuid.uuid4().hex[:8], "9400222" + uuid.uuid4().hex[:8].upper()
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,tracking_code,status,import_label,platform) VALUES(?,?,'pending','Test Show','whatnot')",
              (sid, trk))
    c.commit(); c.close()
    hdr = _login_as(client, A, "worker1", "worker", station="S3")
    video = EBML + b"\x00" * 2048
    r = client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                    data={"tracking": trk, "station": "S3", "duration": "41.5",
                          "video": (io.BytesIO(video), "rec.webm"),
                          "photo": (io.BytesIO(b"\xff\xd8\xffJPEG"), "p.jpg")})
    assert r.get_json()["ok"] is True
    vkeys = [k for k in r2.objects if "/videos/" in k]
    assert len(vkeys) == 1 and ("S3_" + trk) in vkeys[0]
    assert r2.objects[vkeys[0]].startswith(EBML)          # stored as a playable webm
    assert any("/photos/" in k and trk in k for k in r2.objects)
    ship, _ = _shipment(A, sid)
    assert ship["status"] == "packed" and ship["packed_by"] == "worker1"


def test_pack_upload_rejects_bad_tracking(appmod, client, r2):
    A = appmod
    hdr = _login_as(client, A, "worker1", "worker")
    r = client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                    data={"tracking": "abc;DROP", "video": (io.BytesIO(EBML), "v.webm")})
    assert r.get_json()["ok"] is False and r2.objects == {}


def test_pack_upload_storage_failure_is_reported_not_swallowed(appmod, client, r2, monkeypatch):
    A = appmod
    def boom(**kw): raise RuntimeError("R2 down")
    monkeypatch.setattr(r2, "put_object", boom)
    hdr = _login_as(client, A, "worker1", "worker")
    r = client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                    data={"tracking": "9400333FAIL01", "video": (io.BytesIO(EBML + b"x"), "v.webm")})
    assert r.get_json()["ok"] is False       # the station must know the video was NOT saved


# ── 3. Whatnot import ─────────────────────────────────────────────────────────
def test_whatnot_import_makes_one_package_per_buyer(appmod, client):
    A = appmod
    hdr = _login_as(client, A, "cs1", "cs")
    tag, (pkgA, trkA), (pkgB, trkB), csv_bytes = _new_show(A)
    r = _import(client, hdr, csv_bytes, "Peach Whatnot " + tag)
    d = r.get_json()
    assert d["ok"] is True, d
    assert d["shipments_new"] == 2
    shipA, itemsA = _shipment(A, pkgA)
    shipB, itemsB = _shipment(A, pkgB)
    assert shipA["platform"] == "whatnot" and shipA["tracking_code"] == trkA
    assert sorted(i["product_name"] for i in itemsA) == ["Blush #3", "Lip Oil #12"]
    assert [i["product_name"] for i in itemsB] == ["Serum #7"]
    assert shipA["import_label"] == "Peach Whatnot " + tag


def test_whatnot_import_reads_price_column(appmod, client):
    A = appmod
    hdr = _login_as(client, A, "cs1", "cs")
    tag, (pkgA, _), _, csv_bytes = _new_show(A)
    assert _import(client, hdr, csv_bytes, "Price " + tag).get_json()["ok"] is True
    _, items = _shipment(A, pkgA)
    assert sorted(round(i["revenue"] or 0, 2) for i in items) == [9.0, 12.5]   # not $0


def test_same_whatnot_file_twice_is_blocked(appmod, client):
    A = appmod
    hdr = _login_as(client, A, "cs1", "cs")
    tag, _, _, csv_bytes = _new_show(A)
    assert _import(client, hdr, csv_bytes, "Dup " + tag).get_json()["ok"] is True
    d = _import(client, hdr, csv_bytes, "Dup " + tag).get_json()
    assert d["ok"] is False and d.get("duplicate") is True


def test_workers_cannot_import(appmod, client):
    A = appmod
    hdr = _login_as(client, A, "worker1", "worker")
    _, _, _, csv_bytes = _new_show(A)
    assert _import(client, hdr, csv_bytes, "Nope").status_code in (302, 401, 403)


# ── 4. CS lookup ──────────────────────────────────────────────────────────────
def test_cs_finds_video_by_tracking_and_it_opens(appmod, client, r2):
    A = appmod
    trk = "9400444" + uuid.uuid4().hex[:8].upper()
    hdr = _login_as(client, A, "worker1", "worker")
    client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                data={"tracking": trk, "station": "S2", "duration": "30",
                      "video": (io.BytesIO(EBML + b"v"), "v.webm")})
    _login_as(client, A, "cs1", "cs")
    d = client.get("/api/search/" + trk).get_json()
    assert len(d["videos"]) == 1
    v = d["videos"][0]
    assert v["station"] == "S2" and v["url"].startswith("/media/video/")
    assert d["log"][0]["worker"] == "worker1"              # who packed it
    assert d["log"][0]["duration_seconds"] == "30.0"
    r = client.get(v["url"])
    assert r.status_code == 302 and "r2.example" in r.headers["Location"]   # fresh signed link


def test_workers_cannot_search_videos(appmod, client):
    A = appmod
    _login_as(client, A, "worker1", "worker")
    assert client.get("/api/search/9400000000").status_code in (302, 401, 403)


# ── the whole day, end to end ─────────────────────────────────────────────────
def test_full_day_import_badge_pack_lookup(appmod, client, r2):
    A = appmod
    # morning: CS imports last night's Whatnot show
    hdr = _login_as(client, A, "cs1", "cs")
    tag, (pkgA, trkA), (pkgB, trkB), csv_bytes = _new_show(A)
    assert _import(client, hdr, csv_bytes, "Night Show " + tag).get_json()["ok"] is True
    client.get("/logout")
    # a packer badges in at station S4
    with client.session_transaction() as s:
        s.clear()
    hdr = _csrf(client)
    assert client.post("/api/badge-login", json={"token": _badge_of(A, "worker4")}, headers=hdr).get_json()["ok"]
    # packs buyer A's box (the scanner reads the label's tracking number)
    r = client.post("/api/upload", headers=hdr, content_type="multipart/form-data",
                    data={"tracking": trkA, "station": "S4", "duration": "52",
                          "video": (io.BytesIO(EBML + b"day"), "v.webm")})
    assert r.get_json()["ok"] is True
    shipA, _ = _shipment(A, pkgA)
    shipB, _ = _shipment(A, pkgB)
    assert shipA["status"] == "packed" and shipB["status"] != "packed"
    # afternoon: buyer A says an item was missing — CS pulls the video
    _login_as(client, A, "cs1", "cs")
    d = client.get("/api/search/" + trkA).get_json()
    assert len(d["videos"]) == 1 and d["videos"][0]["station"] == "S4"
    assert client.get(d["videos"][0]["url"]).status_code == 302
