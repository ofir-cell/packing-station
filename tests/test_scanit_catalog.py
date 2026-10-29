"""Scanit on the ONE catalog: the host scans a product and sees name, MSRP, target price and
notes from `products` (the same catalog Live Mode / picking / inventory use). Missing notes
or MSRP are looked up once in the background (AI + web search, faked here) and cached."""
import json, types, uuid

import pytest


class FakeAI:
    def __init__(self, answer, web_fails=False):
        self.answer, self.web_fails, self.calls = answer, web_fails, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if self.web_fails and kw.get("tools"):
            raise RuntimeError("web search not enabled for this org")
        return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text="Here you go: " + json.dumps(self.answer))])


@pytest.fixture
def inline_threads(appmod, monkeypatch):
    """Run background lookups inline so the test sees the result."""
    class T:
        def __init__(self, target=None, args=(), kwargs=None, **kw): self.t, self.a, self.k = target, args, kwargs or {}
        def start(self): self.t(*self.a, **self.k)
    monkeypatch.setattr(appmod.threading, "Thread", T)


@pytest.fixture(autouse=True)
def host_user(appmod):
    """A real account with the host role (roles are read from the user store)."""
    with appmod.update_json(appmod.USERS_FILE) as users:
        base = dict(next(iter(users.values()))) if users else {}
        users["host1"] = dict(base, role="host", roles=["host"], name="host1")
    yield


def _as(client, A, user="admin", role="admin"):
    with client.session_transaction() as s:
        s.clear(); s.update(user=user, role=role, roles=[role], name=user, org=A.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _product(A, **kw):
    sku = kw.pop("sku", "SK" + uuid.uuid4().hex[:8])
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT INTO products(sku,name,barcode,on_hand,avg_cost,target_price,retail_price) VALUES(?,?,?,?,?,?,?)",
              (sku, kw.get("name", "Dior J'adore EDP 50ml"), kw.get("barcode", "33" + uuid.uuid4().hex[:10]),
               kw.get("on_hand", 7), 10, kw.get("target", 65), kw.get("msrp", 0)))
    for k in ("msrp_source", "product_notes", "notes_source", "info_status"):
        if k in kw: c.execute("UPDATE products SET %s=? WHERE sku=?" % k, (kw[k], sku))
    c.commit()
    r = dict(c.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()); c.close()
    return r


def _get(A, sku):
    c = A.sdb(A.DEFAULT_ORG); r = dict(c.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()); c.close()
    return r


FRAG = {"name": "Dior J'adore Eau de Parfum 50ml", "kind": "fragrance", "top": "Pear, Melon", "heart": "Jasmine, Rose",
        "base": "Vanilla, Musk", "points": [], "msrp": 140, "msrp_url": "https://www.dior.com/jadore", "source_url": "https://www.fragrantica.com/x"}


def test_host_scans_a_catalog_product_and_sees_name_prices_and_notes(appmod, client, monkeypatch):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", None)
    p = _product(A, msrp=140, msrp_source="manual", product_notes=json.dumps({"top": "Pear"}), notes_source="manual")
    d = client.get("/api/scanit/scan?code=" + p["barcode"]).get_json()
    v = d["product"]
    assert d["found"] and v["name"] == p["name"] and v["msrp"] == 140 and v["target_price"] == 65
    assert v["notes"] == {"top": "Pear"} and v["msrp_manual"] is True
    assert _get(A, p["sku"])["on_hand"] == 7                               # scanning never touches stock


def test_unknown_barcode_is_created_in_the_catalog_from_the_online_databases(appmod, client, monkeypatch):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", None)
    code = "8" + uuid.uuid4().int.__str__()[:11]
    monkeypatch.setattr(A, "_barcode_lookup_online", lambda c: {"code": c, "name": "Rare Beauty Blush Joy", "brand": "Rare Beauty",
                                                                "category": "Makeup", "image": "", "price": 19.5, "source": "UPCitemdb"})
    d = client.get("/api/scanit/scan?code=" + code).get_json()
    assert d["created"] is True and d["product"]["name"] == "Rare Beauty Blush Joy"
    assert d["product"]["msrp"] == 19.5 and d["product"]["msrp_source"] == "UPCitemdb"   # shown as a store-price estimate
    assert _get(A, code)["msrp_source"] == "db:UPCitemdb"


def test_missing_notes_and_msrp_are_looked_up_once_with_sources(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    ai = FakeAI(FRAG); monkeypatch.setattr(A, "anthropic_client", ai)
    p = _product(A)
    client.get("/api/scanit/scan?code=" + p["barcode"])
    r = _get(A, p["sku"])
    assert json.loads(r["product_notes"]) == {"top": "Pear, Melon", "heart": "Jasmine, Rose", "base": "Vanilla, Musk"}
    assert r["notes_source"] == "https://www.fragrantica.com/x" and r["retail_price"] == 140 and r["msrp_source"] == "https://www.dior.com/jadore"
    assert r["info_status"] == "done" and ai.calls[0]["tools"][0]["type"].startswith("web_search")
    client.get("/api/scanit/scan?code=" + p["barcode"])
    assert len(ai.calls) == 1                                              # cached: never looked up again


def test_lookup_never_overwrites_what_the_team_typed(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG))
    p = _product(A, msrp=99, msrp_source="manual")
    client.get("/api/scanit/scan?code=" + p["barcode"])
    r = _get(A, p["sku"])
    assert r["retail_price"] == 99 and r["msrp_source"] == "manual"       # notes filled, MSRP kept
    assert json.loads(r["product_notes"])["top"] == "Pear, Melon"


def test_store_price_estimate_is_replaced_by_the_brand_msrp(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG))
    p = _product(A, msrp=89.99, msrp_source="db:UPCitemdb")
    client.get("/api/scanit/scan?code=" + p["barcode"])
    assert _get(A, p["sku"])["retail_price"] == 140


def test_without_web_search_everything_is_labelled_as_unchecked_ai(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG, web_fails=True))
    p = _product(A)
    v = client.get("/api/scanit/scan?code=" + p["barcode"]).get_json()["product"]
    assert v["notes_source"] == "ai-unchecked"
    assert v["msrp"] == 140 and v["msrp_source"] == "ai-estimate"           # never shown as a checked brand price


def test_failed_lookup_is_not_retried_on_every_scan(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    class Broken(FakeAI):
        def create(self, **kw): self.calls.append(kw); raise RuntimeError("down")
    ai = Broken({}); monkeypatch.setattr(A, "anthropic_client", ai)
    p = _product(A)
    client.get("/api/scanit/scan?code=" + p["barcode"])
    n = len(ai.calls)
    client.get("/api/scanit/scan?code=" + p["barcode"])
    assert _get(A, p["sku"])["info_status"] == "failed" and len(ai.calls) == n


def test_quick_edit_is_for_admins_and_is_kept_as_manual(appmod, client, monkeypatch, inline_threads):
    A = appmod
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG))
    p = _product(A)
    hdr = _as(client, A, "host1", "host")
    assert client.post("/api/scanit/item", headers=hdr, json={"sku": p["sku"], "msrp": 1}).status_code in (302, 401, 403)
    hdr = _as(client, A)
    assert client.post("/api/scanit/item", headers=hdr, json={"sku": p["sku"], "msrp": "abc"}).get_json()["ok"] is False
    d = client.post("/api/scanit/item", headers=hdr, json={"sku": p["sku"], "msrp": "150", "target_price": "70",
                                                           "notes": {"points": ["Buildable", "Dewy"]}}).get_json()
    assert d["ok"] and d["product"]["msrp"] == 150 and d["product"]["target_price"] == 70
    client.post("/api/scanit/item/lookup", headers=hdr, json={"sku": p["sku"]})             # forced lookup
    r = _get(A, p["sku"])
    assert r["retail_price"] == 150 and json.loads(r["product_notes"]) == {"points": ["Buildable", "Dewy"]}


def test_old_scanit_products_move_into_the_catalog_once(appmod, client):
    A = appmod
    t = uuid.uuid4().hex[:6]
    p = _product(A, barcode="77" + t, msrp=0, target=0)                     # same barcode already in the catalog
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("DELETE FROM settings WHERE key='scanit_migrated'")
    c.execute("""INSERT INTO scanit_products(upc,brand,product_name,size,size_unit,msrp,msrp_url,target_price,notes_top,notes_heart,notes_base)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?)""", ("77" + t, "Dior", "J'adore", "50", "ml", 140, "https://dior.com", 65, "Pear", "Rose", "Musk"))
    c.execute("INSERT INTO scanit_products(upc,brand,product_name,msrp) VALUES(?,?,?,?)", ("66" + t, "Glow Recipe", "Toner", 35))
    c.commit(); c.close()
    assert A._scanit_migrate_to_catalog(A.DEFAULT_ORG) >= 2
    r = _get(A, p["sku"])
    assert r["retail_price"] == 140 and r["target_price"] == 65 and json.loads(r["product_notes"])["heart"] == "Rose"
    assert _get(A, "66" + t)["name"] == "Glow Recipe Toner" and _get(A, "66" + t)["retail_price"] == 35
    assert A._scanit_migrate_to_catalog(A.DEFAULT_ORG) == 0                 # only once


def test_inventory_edit_of_msrp_counts_as_typed_by_the_team(appmod, client):
    A = appmod; hdr = _as(client, A)
    p = _product(A, msrp_source="db:UPCitemdb", msrp=20)
    client.post("/api/products", headers=hdr, json={"sku": p["sku"], "name": p["name"], "barcode": p["barcode"], "retail_price": 42})
    assert _get(A, p["sku"])["msrp_source"] == "manual"


def test_screen_is_for_hosts_and_managers_and_in_the_menu(appmod, client):
    A = appmod
    _as(client, A, "host1", "host")
    r = client.get("/scanit")
    assert r.status_code == 200 and b'href="/scanit"' in r.data and b"Scan a product" in r.data
    _as(client, A, "worker1", "worker")
    assert client.get("/scanit").status_code in (302, 401, 403)
    assert client.get("/api/scanit/scan?code=1").status_code in (302, 401, 403)


def test_lookup_that_found_nothing_is_not_repeated_on_every_scan(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    ai = FakeAI({"name": "", "kind": "other", "top": "", "heart": "", "base": "", "points": [], "msrp": 0, "msrp_url": ""})
    monkeypatch.setattr(A, "anthropic_client", ai)
    p = _product(A)
    for _ in range(3):
        client.get("/api/scanit/scan?code=" + p["barcode"])
    assert len(ai.calls) == 1 and _get(A, p["sku"])["info_status"] == "done"


# ── value saved once on the product card ──────────────────────────────────────
NO_MSRP = dict(FRAG, msrp=0, msrp_url="", est_value=95)


def test_ai_value_is_saved_on_the_product_card_and_never_paid_for_again(appmod, client, monkeypatch, inline_threads):
    A = appmod; hdr = _as(client, A, "host1", "host")
    ai = FakeAI(NO_MSRP); monkeypatch.setattr(A, "anthropic_client", ai)
    p = _product(A)
    for _ in range(3):
        v = client.get("/api/scanit/scan?code=" + p["barcode"]).get_json()["product"]
    assert v["msrp"] == 95 and v["msrp_source"] == "ai-estimate" and len(ai.calls) == 1
    hdr = _as(client, A)
    res = client.get("/api/products?q=" + p["sku"]).get_json()
    card = [x for x in (res if isinstance(res, list) else res.get("products", res.get("items", []))) if x["sku"] == p["sku"]][0]
    assert card["retail_price"] == 95 and card["msrp_source"] == "ai-estimate" and json.loads(card["product_notes"])["top"]
    # saving the card without touching the price keeps it an AI estimate
    client.post("/api/products", headers=hdr, json={"sku": p["sku"], "name": p["name"], "barcode": p["barcode"], "retail_price": 95})
    assert _get(A, p["sku"])["msrp_source"] == "ai-estimate"


def test_brand_msrp_beats_an_ai_estimate_but_never_what_the_team_typed(appmod, client, monkeypatch, inline_threads):
    A = appmod; hdr = _as(client, A)
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG))
    est = _product(A, msrp=95, msrp_source="ai-estimate")
    typed = _product(A, msrp=120, msrp_source="manual")
    for p in (est, typed):
        client.post("/api/scanit/item/lookup", headers=hdr, json={"sku": p["sku"]})
    assert _get(A, est["sku"])["retail_price"] == 140 and _get(A, typed["sku"])["retail_price"] == 120
    monkeypatch.setattr(A, "anthropic_client", FakeAI(NO_MSRP))
    client.post("/api/scanit/item/lookup", headers=hdr, json={"sku": est["sku"]})
    assert _get(A, est["sku"])["retail_price"] == 140                     # an estimate never replaces the brand MSRP


def test_a_failing_product_is_tried_at_most_twice(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    class Broken(FakeAI):
        def create(self, **kw): self.calls.append(kw); raise RuntimeError("down")
    ai = Broken({}); monkeypatch.setattr(A, "anthropic_client", ai)
    p = _product(A)
    for _ in range(4):
        client.get("/api/scanit/scan?code=" + p["barcode"])
        c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE products SET info_checked_at='2000-01-01' WHERE sku=?", (p["sku"],)); c.commit(); c.close()
    assert _get(A, p["sku"])["info_attempts"] == 2                        # each attempt = 1 web + 1 fallback call


# ── independent review findings ───────────────────────────────────────────────
def test_a_lookup_whose_worker_died_is_retried_not_stuck_looking(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    ai = FakeAI(FRAG); monkeypatch.setattr(A, "anthropic_client", ai)
    p = _product(A, info_status="looking")
    c = A.sdb(A.DEFAULT_ORG); c.execute("UPDATE products SET info_checked_at='2000-01-01T00:00:00' WHERE sku=?", (p["sku"],)); c.commit(); c.close()
    client.get("/api/scanit/scan?code=" + p["barcode"])
    assert _get(A, p["sku"])["info_status"] == "done" and len(ai.calls) == 1


def test_a_crashing_lookup_ends_as_failed(appmod, client, monkeypatch, inline_threads):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG))
    monkeypatch.setattr(A, "_scanit_lookup_info_inner", lambda org, sku: 1 / 0)
    p = _product(A)
    client.get("/api/scanit/scan?code=" + p["barcode"])
    assert _get(A, p["sku"])["info_status"] == "failed"


def test_labels_qr_links_and_typing_never_create_catalog_products(appmod, client, monkeypatch):
    A = appmod; _as(client, A, "host1", "host")
    monkeypatch.setattr(A, "anthropic_client", None)
    monkeypatch.setattr(A, "_barcode_lookup_online", lambda c: None)
    for code in ("HTTPS://TIKTOK.COM/X", "9400111899223344556677", "hello123"):
        assert client.get("/api/scanit/scan?code=" + code).get_json()["found"] is False
    c = A.sdb(A.DEFAULT_ORG)
    assert not c.execute("SELECT 1 FROM products WHERE sku IN ('HTTPS://TIKTOK.COM/X','9400111899223344556677','hello123')").fetchone()
    c.close()


def test_old_unverified_prices_move_over_as_replaceable_not_as_team_entered(appmod, client, monkeypatch, inline_threads):
    A = appmod; t = uuid.uuid4().hex[:6]
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("DELETE FROM settings WHERE key='scanit_migrated'")
    c.execute("INSERT INTO scanit_products(upc,brand,product_name,msrp,verification_status) VALUES(?,?,?,?,?)", ("55" + t, "Dior", "Sauvage", 99, "check"))
    c.commit(); c.close()
    A._scanit_migrate_to_catalog(A.DEFAULT_ORG)
    assert _get(A, "55" + t)["msrp_source"] == "db:legacy"
    hdr = _as(client, A)
    monkeypatch.setattr(A, "anthropic_client", FakeAI(FRAG))
    client.post("/api/scanit/item/lookup", headers=hdr, json={"sku": "55" + t})
    assert _get(A, "55" + t)["retail_price"] == 140                         # the brand MSRP replaces it


def test_renaming_does_not_turn_ai_notes_into_team_notes(appmod, client):
    A = appmod; hdr = _as(client, A)
    p = _product(A, product_notes=json.dumps({"top": "Pear"}), notes_source="ai-unchecked")
    client.post("/api/scanit/item", headers=hdr, json={"sku": p["sku"], "name": "New name", "notes": {"top": "Pear"}})
    assert _get(A, p["sku"])["notes_source"] == "ai-unchecked"
