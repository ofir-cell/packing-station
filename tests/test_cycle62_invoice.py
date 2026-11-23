"""Cycle-62: invoice import. A numeric supplier SKU is a manufacturer barcode — it must land in
BOTH the sku and the barcode column (so scanning it later finds the product), and the target /
retail (MSRP) prices can be set already at invoice upload."""
import uuid


def _admin(client, A):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def test_to_po_barcode_into_sku_and_barcode_plus_prices(appmod, client):
    A = appmod; hdr = _admin(client, A)
    code = "0" + uuid.uuid4().hex[:11]  # not numeric → make a real numeric barcode below
    code = "840" + str(uuid.uuid4().int)[:9]       # 12-digit numeric barcode
    r = client.post("/api/products/import-pdf/to-po", json={"items": [
        {"name": "Serum X", "supplier_sku": code, "qty": 6, "unit_cost": 3.5,
         "target_price": 12, "retail_price": 20}]}, headers=hdr).get_json()
    assert r["ok"] is True
    c = A.sdb(A.DEFAULT_ORG)
    p = c.execute("SELECT sku,barcode,target_price,retail_price,msrp_source FROM products WHERE sku=?", (code,)).fetchone()
    c.close()
    assert p["sku"] == code and p["barcode"] == code          # barcode in BOTH, not just sku
    assert round(p["target_price"], 2) == 12 and round(p["retail_price"], 2) == 20
    assert p["msrp_source"] == "manual"


def test_confirm_sets_barcode_and_prices(appmod, client):
    A = appmod; hdr = _admin(client, A)
    code = "841" + str(uuid.uuid4().int)[:9]
    r = client.post("/api/products/import-pdf/confirm", json={"mode": "add", "items": [
        {"name": "Lotion Y", "supplier_sku": code, "qty": 4, "unit_cost": 2,
         "target_price": 9, "retail_price": 15}]}, headers=hdr).get_json()
    assert r["ok"] is True
    c = A.sdb(A.DEFAULT_ORG)
    p = c.execute("SELECT barcode,target_price,retail_price FROM products WHERE sku=?", (code,)).fetchone()
    c.close()
    assert p["barcode"] == code and round(p["target_price"], 2) == 9 and round(p["retail_price"], 2) == 15


def test_non_numeric_sku_leaves_barcode_null(appmod, client):
    A = appmod; hdr = _admin(client, A)
    sku = "WIDGET-" + uuid.uuid4().hex[:5]
    client.post("/api/products/import-pdf/to-po", json={"items": [
        {"name": "Widget", "store_sku": sku, "qty": 1, "unit_cost": 1}]}, headers=hdr).get_json()
    c = A.sdb(A.DEFAULT_ORG)
    p = c.execute("SELECT barcode FROM products WHERE sku=?", (sku,)).fetchone()
    c.close()
    assert not p["barcode"]      # a non-barcode SKU doesn't get stuffed into the barcode column
