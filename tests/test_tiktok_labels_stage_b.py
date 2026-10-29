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

    def request(self, method, url, params=None, body=None, **kw):
        path = url.split("tiktokglobalshop.com", 1)[-1]
        self.calls.append((method, path))
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
        return [c for c in self.calls if c[0] != "GET"]


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
    def boom(c, new_pid, order_ids): raise RuntimeError("disk full")
    monkeypatch.setattr(A, "_tt_merge_into_package", boom)
    bid = _prepare(client, hdr, show["label"])["batch_id"]
    client.post("/api/tiktok/batch/%d/run" % bid, headers=hdr, json={"pin": "4321"})
    d = client.get("/api/tiktok/batch/%d" % bid).get_json()
    assert tt.ship_calls.get("CMB-G" + t) == 1                          # the package that exists on TikTok
    assert "PA1" + t not in tt.ship_calls and "PA2" + t not in tt.ship_calls   # never the old ones
    assert "disk full" in d["plan"]["combines"][0]["merge_error"]
