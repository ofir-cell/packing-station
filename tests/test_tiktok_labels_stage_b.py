"""Combine & Labels, stage B: plan a show -> manager PIN -> background run that combines
what TikTok allows and creates each TikTok Shipping label -> one PDF.

FakeTikTok keeps state (which packages are shipped, how many times each call ran), so the
money-safety rules can be proven: one label per package ever, a crash mid-call is never
blindly retried, and nothing writes unless TIKTOK_FULFILL_WRITE is on and the PIN is right.
"""
import io, json, time, uuid

import bcrypt
import pytest

SHOP = "SHOP-LBL"


def _pdf_bytes():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO(); cv = canvas.Canvas(buf, pagesize=(288, 432)); cv.drawString(20, 200, "LABEL"); cv.showPage(); cv.save()
    return buf.getvalue()


class FakeTikTok:
    def __init__(self):
        self.groups = []                 # combinable groups [{id, order_ids}]
        self.shipped = {}                # package_id -> tracking
        self.calls = []                  # (method, path)
        self.ship_calls = {}             # package_id -> count
        self.fail_combine = False
        self.crash_ship_after_sending = set()   # pids: TikTok ships it, but our call "times out"
        self.ship_silently_lost = set()          # pids: our call "times out" and TikTok did NOT ship
        self.order_status = {}           # order_id -> TikTok status (default AWAITING_SHIPMENT = Processing)
        self.orders_down = False         # the order-status read fails

    def request(self, method, url, params=None, body=None, **kw):
        path = url.split("tiktokglobalshop.com", 1)[-1]
        self.calls.append((method, path))
        if path.startswith("/order/") and path.endswith("/orders"):
            if self.orders_down:
                raise ConnectionError("TikTok down")
            ids = (params or {}).get("ids", "").split(",")
            return {"code": 0, "data": {"orders": [{"id": i, "status": self.order_status.get(i, "AWAITING_SHIPMENT")} for i in ids if i]}}
        if "combinable_packages" in path:
            return {"code": 0, "data": {"combinable_packages": self.groups, "next_page_token": ""}}
        if path.endswith("/packages/combine"):
            if self.fail_combine:
                return {"code": 0, "data": {"errors": [{"code": 21011001, "message": "not combinable"}]}}
            g = body["combinable_packages"][0]
            return {"code": 0, "data": {"packages": [{"id": "CMB-" + g["id"], "order_ids": g["order_ids"]}]}}
        if path.endswith("/handover_time_slots"):
            return {"code": 0, "data": {"pickup_slots": [{"start_time": 1, "end_time": 2, "avaliable": True}]}}
        if path.endswith("/ship"):
            pid = path.split("/")[-2]
            self.ship_calls[pid] = self.ship_calls.get(pid, 0) + 1
            if pid in self.ship_silently_lost:
                raise TimeoutError("timed out")
            self.shipped[pid] = "9400TT" + pid[-8:]
            if pid in self.crash_ship_after_sending:
                raise TimeoutError("timed out after TikTok accepted it")
            return {"code": 0, "data": {}}
        if path.endswith("/shipping_documents"):
            pid = path.split("/")[-2]
            if pid not in self.shipped:
                return {"code": 21001, "message": "package not shipped"}
            return {"code": 0, "data": {"doc_url": "https://tt.example/labels/%s.pdf" % pid}}
        if "/packages/" in path:
            pid = path.rstrip("/").split("/")[-1]
            return {"code": 0, "data": {"tracking_number": self.shipped.get(pid, ""),
                                        "package_status": "PROCESSING" if pid in self.shipped else "TO_FULFILL"}}
        return {"code": 0, "data": {}}

    def writes(self):
        # fulfillment writes only (combine / ship): order *search* is a POST that is a read, and
        # other tests' background sync threads can hit this fake while a test runs
        return [c for c in self.calls if c[0] != "GET" and "/fulfillment/" in c[1]]


@pytest.fixture
def tt(appmod, monkeypatch):
    A = appmod
    fake = FakeTikTok()
    monkeypatch.setattr(A, "_tt_request", fake.request)
    monkeypatch.setattr(A, "_tiktok_ready", lambda: True)
    monkeypatch.setattr(A, "_tt_valid_token", lambda org, sid: {"access_token": "t", "shop_cipher": "c"} if sid == SHOP else None)
    monkeypatch.setattr(A, "_tt_ensure_cipher", lambda org, sid, tok: tok)
    monkeypatch.setattr(A, "_fetch_label_bytes", lambda url, timeout=25: (_pdf_bytes(), "application/pdf"))
    # run batches inline so the test sees the result (production uses a background thread)
    monkeypatch.setattr(A, "_tt_start_batch_thread", lambda org, bid: A._tt_run_batch(org, bid))
    c = A.pdb()
    c.execute("INSERT OR REPLACE INTO tiktok_shops(org_id,shop_id,shop_name,active,granted_scopes) VALUES(?,?,?,1,'seller.fulfillment.basic')",
              (A.DEFAULT_ORG, SHOP, "Peach"))
    c.commit(); c.close()
    sc = A.sdb(A.DEFAULT_ORG)
    sc.execute("INSERT INTO settings(key,value) VALUES('manager_pin_hash',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (bcrypt.hashpw(b"4321", bcrypt.gensalt()).decode(),))
    sc.commit(); sc.close()
    yield fake
    c = A.pdb(); c.execute("DELETE FROM tiktok_shops WHERE shop_id=?", (SHOP,)); c.commit(); c.close()


@pytest.fixture
def write_on(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "TT_FULFILL_WRITE", True)


def _as(client, A, user="admin", role="admin"):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _order(A, oid, pkg, buyer, label):
    c = A.sdb(A.DEFAULT_ORG)
    A._tt_apply_order(c, {"id": oid, "status": "AWAITING_SHIPMENT", "buyer_nickname": buyer, "create_time": int(time.time()),
                          "packages": [{"id": pkg}], "recipient_address": {"full_address": "1 Main", "name": buyer},
                          "line_items": [{"id": "L", "seller_sku": oid[-3:], "sku_id": "x", "product_name": "Live PART 1",
                                          "sale_price": "5", "package_id": pkg}]}, label=label)
    c.commit(); c.close()
    p = A.pdb()
    p.execute("INSERT OR REPLACE INTO tiktok_orders(order_id,org_id,shop_id,status) VALUES(?,?,?,'AWAITING_SHIPMENT')", (oid, A.DEFAULT_ORG, SHOP))
    p.commit(); p.close()


@pytest.fixture
def show(appmod, tt):
    """Amy has 2 orders TikTok lets us combine; Bob has 1. A cancelled order and an order
    that already has tracking must never be touched."""
    A = appmod
    t = uuid.uuid4().hex[:6].upper()
    label = "Label Live " + t
    _order(A, "OA1" + t, "PA1" + t, "amy", label)
    _order(A, "OA2" + t, "PA2" + t, "amy", label)
    _order(A, "OB1" + t, "PB1" + t, "bob", label)
    _order(A, "OC1" + t, "PC1" + t, "cancelled_cara", label)
    _order(A, "OD1" + t, "PD1" + t, "dan_has_label", label)
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("UPDATE shipments SET status='cancelled' WHERE shipment_id=?", ("PC1" + t,))
    c.execute("UPDATE shipments SET tracking_code=? WHERE shipment_id=?", ("9400EXIST" + t, "PD1" + t))
    c.execute("UPDATE shipment_items SET picked=1 WHERE shipment_id=?", ("PA1" + t,))     # floor progress to keep
    c.commit(); c.close()
    tt.groups = [{"id": "G" + t, "order_ids": ["OA1" + t, "OA2" + t]}]
    return {"t": t, "label": label}


def _prepare(client, hdr, label):
    return client.post("/api/tiktok/batch/prepare", headers=hdr, json={"show": label}).get_json()


def _ship(A, sid):
    c = A.sdb(A.DEFAULT_ORG); r = c.execute("SELECT * FROM shipments WHERE shipment_id=?", (sid,)).fetchone(); c.close()
    return dict(r) if r else None


# ── planning ──────────────────────────────────────────────────────────────────
def test_plan_combines_what_tiktok_allows_and_skips_done_or_cancelled(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A)
    d = _prepare(client, hdr, show["label"])
    t = show["t"]
    assert d["ok"] and d["plan"]["packages_before"] == 3                  # A1, A2, B1 (not C1, D1)
    assert [cb["packages"] for cb in d["plan"]["combines"]] == [sorted(["PA1" + t, "PA2" + t])]
    assert d["plan"]["singles"] == ["PB1" + t] and d["plan"]["labels"] == 2
    assert tt.writes() == []                                               # planning never writes


def test_nothing_writes_while_turned_off(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    r = client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    assert r.status_code == 403 and tt.writes() == []


def test_wrong_pin_is_refused(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    r = client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "0000"})
    assert r.status_code == 401 and tt.writes() == []


# ── the run ───────────────────────────────────────────────────────────────────
def test_run_combines_labels_and_updates_our_packages(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    assert client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"}).get_json()["ok"]
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "done" and d["batch"]["done"] == 2 and d["batch"]["combined"] == 1
    new = "CMB-G" + t
    assert tt.ship_calls == {new: 1, "PB1" + t: 1}                        # one label per box
    # Amy's two orders are now ONE package in our app, floor progress kept, old rows gone
    c = A.sdb(A.DEFAULT_ORG)
    items = [dict(r) for r in c.execute("SELECT order_id, picked FROM shipment_items WHERE shipment_id=? ORDER BY order_id", (new,))]
    c.close()
    assert [(i["order_id"], i["picked"]) for i in items] == [("OA1" + t, 1), ("OA2" + t, 0)]
    assert _ship(A, "PA1" + t) is None and _ship(A, "PA2" + t) is None
    # tracking from TikTok is on our packages, so pickers can scan the new labels
    assert _ship(A, new)["tracking_code"].startswith("9400TT")
    assert _ship(A, "PB1" + t)["tracking_code"].startswith("9400TT")
    # untouched: the cancelled order and the one that already had a label
    assert _ship(A, "PC1" + t)["tracking_code"] in (None, "") and _ship(A, "PD1" + t)["tracking_code"] == "9400EXIST" + t
    assert not any(p in tt.ship_calls for p in ("PC1" + t, "PD1" + t))


def test_batch_pdf_has_every_label(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    r = client.get("/api/tiktok/batch/%d/labels?pdf=1" % bid)
    assert r.status_code == 200 and r.mimetype == "application/pdf"
    from pypdf import PdfReader
    assert len(PdfReader(io.BytesIO(r.data)).pages) == 2


def test_running_or_resuming_again_never_creates_a_second_label(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    before = dict(tt.ship_calls)
    assert client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"}).status_code == 409
    client.post("/api/tiktok/batch/%d/resume" % bid, headers=hdr, json={"pin": "4321"})
    bid2 = _prepare(client, hdr, show["label"])                            # a new batch for the same show
    assert bid2["ok"] is False                                             # nothing left to label
    assert tt.ship_calls == before
    # even if something calls the per-package job again directly, a labeled package is left alone
    for pid in list(tt.ship_calls):
        A._tt_label_one(A.DEFAULT_ORG, SHOP, pid, bid, A.TT_DEFAULT_BOX)
    assert tt.ship_calls == before


def test_crash_after_tiktok_accepted_is_recovered_without_shipping_again(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.crash_ship_after_sending.add("PB1" + t)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "needs_attention"
    assert [(j["package_id"], j["status"]) for j in d["problems"]] == [("PB1" + t, "uncertain")]
    client.post("/api/tiktok/batch/%d/resume" % bid, headers=hdr, json={"pin": "4321"})
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "done" and d["problems"] == []
    assert tt.ship_calls["PB1" + t] == 1                                   # read TikTok, did not ship twice


def test_uncertain_with_no_label_on_tiktok_waits_for_a_human(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.ship_silently_lost.add("PB1" + t)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    client.post("/api/tiktok/batch/%d/resume" % bid, headers=hdr, json={"pin": "4321"})
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    prob = [j for j in d["problems"] if j["package_id"] == "PB1" + t][0]
    assert prob["status"] == "uncertain" and "Seller Center" in prob["error"]
    assert tt.ship_calls["PB1" + t] == 1                                   # never retried blindly


def test_combine_refused_labels_packages_separately(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.fail_combine = True
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["done"] == 3 and d["batch"]["combined"] == 0
    assert "refused" in d["plan"]["combines"][0]["error"]
    assert set(tt.ship_calls) == {"PA1" + t, "PA2" + t, "PB1" + t}


# ── settings and access ───────────────────────────────────────────────────────
def test_standard_box_is_admin_only_and_validated(appmod, client, tt):
    A = appmod
    hdr = _as(client, A, "cs1", "cs")
    assert client.post("/api/tiktok/box", headers=hdr, json={"weight_lb": 1, "length_in": 9, "width_in": 6, "height_in": 3}).status_code in (302, 401, 403)
    hdr = _as(client, A)
    assert client.post("/api/tiktok/box", headers=hdr, json={"weight_lb": "x", "length_in": 9, "width_in": 6, "height_in": 3}).get_json()["ok"] is False
    assert client.post("/api/tiktok/box", headers=hdr, json={"weight_lb": 1.5, "length_in": 10, "width_in": 7, "height_in": 4}).get_json()["ok"]
    assert A._tt_box(A.DEFAULT_ORG)["weight_lb"] == 1.5


def test_workers_cannot_plan_or_run(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A, "worker1", "worker")
    assert client.post("/api/tiktok/batch/prepare", headers=hdr, json={"show": show["label"]}).status_code in (302, 401, 403)
    assert client.post("/api/tiktok/batch/1/run", headers=hdr, json={"pin": "4321"}).status_code in (302, 401, 403)


def test_if_our_db_update_fails_after_tiktok_combined_the_new_package_still_gets_its_label(appmod, client, tt, show, write_on, monkeypatch):
    A = appmod; hdr = _as(client, A); t = show["t"]
    def boom(*a, **k): raise RuntimeError("disk full")
    monkeypatch.setattr(A, "_tt_merge_into_package", boom)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert tt.ship_calls.get("CMB-G" + t) == 1                          # the package that exists on TikTok
    assert "PA1" + t not in tt.ship_calls and "PA2" + t not in tt.ship_calls   # never the old ones
    assert "disk full" in d["plan"]["combines"][0]["merge_error"]


# ── Pending → Processing: only orders TikTok already moved to Processing get a label ──
def test_order_still_pending_at_tiktok_waits_and_the_rest_go_ahead(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.order_status["OB1" + t] = "ON_HOLD"
    p = _prepare(client, hdr, show["label"])["plan"]
    assert p["singles"] == [] and len(p["combines"]) == 1               # Amy goes ahead, Bob waits
    assert [w["package"] for w in p["waiting"]] == ["PB1" + t] and p["waiting_count"] == 1
    assert p["status_fresh"] is True


def test_buyer_with_one_pending_order_is_held_whole_so_her_box_is_still_combined(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.order_status["OA2" + t] = "ON_HOLD"
    p = _prepare(client, hdr, show["label"])["plan"]
    assert p["combines"] == [] and p["singles"] == ["PB1" + t]
    assert sorted(w["package"] for w in p["waiting"]) == sorted(["PA1" + t, "PA2" + t])
    assert [w["pending"] for w in sorted(p["waiting"], key=lambda w: w["package"])] == [False, True]


def test_whole_live_still_pending_says_not_ready(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    for o in ("OA1", "OA2", "OB1"):
        tt.order_status[o + t] = "ON_HOLD"
    d = _prepare(client, hdr, show["label"])
    assert d["ok"] is False and "Pending" in d["error"] and d["plan"]["waiting_count"] == 3
    assert tt.writes() == []


def test_order_cancelled_after_planning_is_never_labeled(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    tt.order_status["OB1" + t] = "CANCELLED"                              # buyer cancels before approval
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    assert "PB1" + t not in tt.ship_calls
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["plan"]["skipped"] == ["PB1" + t] and d["batch"]["status"] == "done"


def test_tiktok_status_unreachable_uses_last_synced_status(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.orders_down = True
    c = A.pdb(); c.execute("UPDATE tiktok_orders SET status='ON_HOLD' WHERE order_id=?", ("OB1" + t,)); c.commit(); c.close()
    p = _prepare(client, hdr, show["label"])["plan"]
    assert p["status_fresh"] is False and [w["package"] for w in p["waiting"]] == ["PB1" + t]


def test_lives_list_shows_ready_and_pending_counts(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE shipments SET tt_status='ON_HOLD' WHERE shipment_id=?", ("PB1" + t,)); c.commit(); c.close()
    s = [x for x in client.get("/api/tiktok/label-shows").get_json()["shows"] if x["label"] == show["label"]][0]
    assert s["n"] == 3 and s["ready"] == 2 and s["pending"] == 1


# ── one live only, and every label kept under its live ───────────────────────
def test_tiktok_group_reaching_into_another_live_is_never_combined(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    _order(A, "OX1" + t, "PX1" + t, "amy", "Yesterday Live " + t)        # same buyer, a different live
    tt.groups = [{"id": "GX" + t, "order_ids": ["OA1" + t, "OX1" + t]}]
    p = _prepare(client, hdr, show["label"])["plan"]
    assert p["combines"] == []
    assert p["singles"] == sorted(["PA1" + t, "PA2" + t, "PB1" + t])     # PX1 (other live) not in this batch at all


def test_labels_are_saved_under_their_live_with_one_file_for_the_whole_live(appmod, client, tt, show, write_on):
    import os
    from pypdf import PdfReader
    A = appmod; hdr = _as(client, A); t = show["t"]
    folder = os.path.join(A._labels_dir(A.DEFAULT_ORG), "tiktok", A._tt_live_folder(show["label"]))
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    c = A.sdb(A.DEFAULT_ORG)
    files = [r["label_file"] for r in c.execute("SELECT label_file FROM tt_label_jobs WHERE batch_id=?", (bid,)).fetchall()]
    c.close()
    assert files and all(f.startswith("tiktok/%s/" % A._tt_live_folder(show["label"])) for f in files)
    assert len(PdfReader(os.path.join(folder, "ALL-labels.pdf")).pages) == 2
    assert os.path.exists(os.path.join(folder, "batch-%d.pdf" % bid))
    # an order of the same live arrives late -> second batch; the live file now has all 3
    _order(A, "OL1" + t, "PL1" + t, "lucy", show["label"])
    bid2 = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid2, headers=hdr, json={"pin": "4321"})
    assert len(PdfReader(os.path.join(folder, "ALL-labels.pdf")).pages) == 3
    r = client.get("/api/tiktok/live-labels?pdf=1&show=" + show["label"])
    assert r.status_code == 200 and len(PdfReader(io.BytesIO(r.data)).pages) == 3
    ls = client.get("/api/tiktok/label-shows").get_json()["labeled_shows"]
    assert [x["n"] for x in ls if x["label"] == show["label"]] == [3]
    # a different live's folder is untouched
    assert not os.path.exists(os.path.join(A._labels_dir(A.DEFAULT_ORG), "tiktok", A._tt_live_folder("Other " + t)))


# ── restarts, double clicks, two batches for one live ────────────────────────
def _set_batch(A, bid, status, hb_age_secs):
    from datetime import datetime, timedelta
    hb = (datetime.now() - timedelta(seconds=hb_age_secs)).isoformat(timespec="seconds")
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE tt_batches SET status=?, heartbeat=? WHERE id=?", (status, hb, bid)); c.commit(); c.close()


def test_resume_is_refused_while_the_batch_is_still_moving(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    _set_batch(A, bid, "running", 5)                                      # another worker is on it right now
    r = client.post("/api/tiktok/batch/%d/resume" % bid, headers=hdr, json={"pin": "4321"})
    assert r.status_code == 409 and tt.writes() == []
    assert client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]["stale"] is False


def test_batch_stuck_after_a_server_restart_can_be_resumed_and_finishes(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    _set_batch(A, bid, "running", A.TT_BATCH_STALE_SECS + 60)             # worker died mid-batch
    assert client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]["stale"] is True
    assert client.post("/api/tiktok/batch/%d/resume" % bid, headers=hdr, json={"pin": "4321"}).status_code == 200
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "done" and d["batch"]["done"] == 2
    assert all(n == 1 for n in tt.ship_calls.values())


def test_unexpected_crash_ends_as_needs_attention_not_stuck_running(appmod, client, tt, show, write_on, monkeypatch):
    A = appmod; hdr = _as(client, A)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    monkeypatch.setattr(A, "_tt_box", lambda org=None: 1 / 0)
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    b = client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]
    assert b["status"] == "needs_attention" and "Stopped unexpectedly" in b["note"]


def test_only_one_active_batch_per_live(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A)
    old = _prepare(client, hdr, show["label"])["batch_id"]               # opened, then the modal was closed
    new = _prepare(client, hdr, show["label"])["batch_id"]
    assert client.post("/api/tiktok/batch/%d/run" % old, headers=hdr, json={"pin": "4321"}).status_code == 409   # superseded
    _set_batch(A, new, "running", 5)
    d = _prepare(client, hdr, show["label"])
    assert d["ok"] is False and "still running" in d["error"]
    assert tt.writes() == []


def test_fresh_pending_status_shows_on_the_lives_list_and_labeled_groups_are_marked(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.order_status["OB1" + t] = "ON_HOLD"
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    s = [x for x in client.get("/api/tiktok/label-shows").get_json()["shows"] if x["label"] == show["label"]][0]
    assert s["pending"] == 1
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    g = [x for x in client.get("/api/tiktok/combinable").get_json()["groups"] if x["id"] == "G" + t][0]
    assert g["labeled"] is True


def test_two_workers_racing_on_one_package_buy_one_label(appmod, client, tt, show, write_on, monkeypatch):
    import threading
    A = appmod; t = show["t"]; pid = "PB1" + t
    c = A.sdb(A.DEFAULT_ORG); A._tt_labels_ensure(c)
    bid = c.execute("INSERT INTO tt_batches(show,status,plan) VALUES(?, 'running', '{}')", (show["label"],)).lastrowid
    c.commit(); c.close()
    orig = tt.request
    def slow(method, url, params=None, body=None, **kw):
        if url.endswith("/ship"): time.sleep(0.3)
        return orig(method, url, params, body, **kw)
    monkeypatch.setattr(A, "_tt_request", slow)
    th = [threading.Thread(target=A._tt_label_one, args=(A.DEFAULT_ORG, SHOP, pid, bid, A.TT_DEFAULT_BOX)) for _ in range(4)]
    for x in th: x.start()
    for x in th: x.join()
    assert tt.ship_calls[pid] == 1
    A._tt_label_one(A.DEFAULT_ORG, SHOP, pid, bid, A.TT_DEFAULT_BOX)       # a later resume settles it
    c = A.sdb(A.DEFAULT_ORG); st = c.execute("SELECT status FROM tt_label_jobs WHERE package_id=?", (pid,)).fetchone()[0]; c.close()
    assert st == "labeled" and tt.ship_calls[pid] == 1


# ── independent review findings, kept as regression tests ────────────────────
def _run(client, hdr, bid, ep="run"):
    return client.post("/api/tiktok/batch/%d/%s" % (bid, ep), headers=hdr, json={"pin": "4321"}).get_json()


def test_cancelled_while_tiktok_status_is_unreachable_buys_nothing(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    tt.order_status["OB1" + t] = "CANCELLED"; tt.orders_down = True
    _run(client, hdr, bid)
    assert tt.ship_calls == {}                                            # nothing bought blind
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "needs_attention"
    assert all("Could not confirm" in j["error"] for j in d["problems"])


def test_resume_days_later_rechecks_and_skips_an_order_cancelled_meanwhile(appmod, client, tt, show, write_on, monkeypatch):
    A = appmod; hdr = _as(client, A); t = show["t"]
    orig = tt.request; state = {"fail": True}
    def req(method, url, params=None, body=None, **kw):
        if url.endswith("PB1%s/ship" % t) and state["fail"]:
            return {"code": 429, "message": "rate limited"}
        return orig(method, url, params=params, body=body, **kw)
    monkeypatch.setattr(A, "_tt_request", req)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    _run(client, hdr, bid)
    state["fail"] = False; tt.order_status["OB1" + t] = "CANCELLED"
    _run(client, hdr, bid, "resume")
    assert "PB1" + t not in tt.ship_calls
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "done" and [j["package_id"] for j in d["skipped"]] == ["PB1" + t]


def test_package_recovered_in_a_new_batch_belongs_to_that_batch(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.crash_ship_after_sending.add("PB1" + t)
    _run(client, hdr, _prepare(client, hdr, show["label"])["batch_id"])
    bid2 = _prepare(client, hdr, show["label"])["batch_id"]               # new batch instead of Resume
    _run(client, hdr, bid2)
    b2 = client.get("/api/tiktok/batch/%d" % bid2).get_json()["batch"]
    assert b2["done"] == 1 and b2["status"] == "done"
    assert client.get("/api/tiktok/batch/%d/labels?pdf=1" % bid2).status_code == 200
    assert tt.ship_calls["PB1" + t] == 1


def test_merge_failure_is_flagged_retried_on_resume_and_old_ids_never_planned_again(appmod, client, tt, show, write_on, monkeypatch):
    A = appmod; hdr = _as(client, A); t = show["t"]
    real = A._tt_merge_into_package
    monkeypatch.setattr(A, "_tt_merge_into_package", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("database is locked")))
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    _run(client, hdr, bid)
    assert client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]["status"] == "needs_attention"
    tt.groups = []
    d2 = _prepare(client, hdr, show["label"])
    assert d2["ok"] is False or "PA1" + t not in d2["plan"]["singles"]  # dead TikTok ids are never offered again
    monkeypatch.setattr(A, "_tt_merge_into_package", real)
    _run(client, hdr, bid, "resume")
    assert client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]["status"] == "done"
    assert _ship(A, "CMB-G" + t)["tracking_code"] and _ship(A, "PA1" + t) is None
    assert tt.ship_calls["CMB-G" + t] == 1


def test_combine_that_timed_out_buys_nothing_until_tiktok_shows_what_happened(appmod, client, tt, show, write_on, monkeypatch):
    A = appmod; hdr = _as(client, A); t = show["t"]
    orig = tt.request; state = {"timeout": True}
    def req(method, url, params=None, body=None, **kw):
        if url.endswith("/packages/combine") and state["timeout"]:
            orig(method, url, params=params, body=body, **kw)            # TikTok DID combine
            raise TimeoutError("timed out")
        if url.endswith("/orders") and not state["timeout"]:            # order detail now shows the new package
            ids = (params or {}).get("ids", "").split(",")
            return {"code": 0, "data": {"orders": [{"id": i, "status": "AWAITING_SHIPMENT",
                    "packages": [{"id": "CMB-G" + t}] if i.startswith("OA") else [{"id": "PB1" + t}]} for i in ids]}}
        return orig(method, url, params=params, body=body, **kw)
    monkeypatch.setattr(A, "_tt_request", req)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    _run(client, hdr, bid)
    assert "PA1" + t not in tt.ship_calls and "PA2" + t not in tt.ship_calls and "CMB-G" + t not in tt.ship_calls
    assert client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]["status"] == "needs_attention"
    state["timeout"] = False
    _run(client, hdr, bid, "resume")
    assert tt.ship_calls.get("CMB-G" + t) == 1 and "PA1" + t not in tt.ship_calls
    assert client.get("/api/tiktok/batch/%d" % bid).get_json()["batch"]["status"] == "done"


def test_packed_box_is_never_reopened_by_a_combine(appmod, client, tt, show):
    A = appmod; hdr = _as(client, A); t = show["t"]
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE shipments SET status='packed' WHERE shipment_id=?", ("PA2" + t,)); c.commit(); c.close()
    p = _prepare(client, hdr, show["label"])["plan"]
    assert p["combines"] == [] and "PA2" + t in p["singles"]


def test_merged_box_takes_the_least_advanced_status(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE shipments SET status='picked' WHERE shipment_id=?", ("PA1" + t,)); c.commit(); c.close()
    _run(client, hdr, _prepare(client, hdr, show["label"])["batch_id"])
    assert _ship(A, "CMB-G" + t)["status"] == "pending"


def test_uncertain_package_can_be_released_only_with_the_pin(appmod, client, tt, show, write_on):
    A = appmod; hdr = _as(client, A); t = show["t"]
    tt.ship_silently_lost.add("PB1" + t)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    _run(client, hdr, bid); _run(client, hdr, bid, "resume")
    url = "/api/tiktok/label-job/PB1%s/release" % t
    assert client.post(url, headers=hdr, json={"pin": "0000"}).status_code == 401
    assert client.post(url, headers=hdr, json={"pin": "4321"}).get_json()["ok"]
    tt.ship_silently_lost.discard("PB1" + t)
    _run(client, hdr, bid, "resume")
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert d["batch"]["status"] == "done" and tt.ship_calls["PB1" + t] == 2   # second try only after a human checked
