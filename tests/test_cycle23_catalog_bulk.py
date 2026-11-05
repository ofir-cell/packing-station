"""Cycle-23: catalog bulk actions + soft-delete (archive) from the Inventory screen.

The warehouse accumulates hundreds of auto-created 'New product • <barcode>' stubs
from scanning unknown barcodes during lives. Admins select rows and bulk-archive
(hide, recoverable — never hard-deleted so stock history and live-match links survive),
bulk-set a category, or rename inline. Archived products drop out of the catalog list
but show under ?archived=1 and can be restored."""
import uuid


def _admin(client, A, role="admin"):
    uname = role + "_u"
    with A.update_json(A.USERS_FILE) as users:          # registered so session-revocation passes
        u = dict(users.get(uname) or {})
        u.update({"password": u.get("password", "x"), "role": role, "name": role.title(), "org": A.DEFAULT_ORG})
        users[uname] = u
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], org=A.DEFAULT_ORG, name=role.title())
    client.set_cookie("csrf_token", "tok")
    return {"X-CSRF-Token": "tok"}


def _prod(A, sku, name="New product", on_hand=0, cat="Needs review"):
    c = A.sdb(A.DEFAULT_ORG)
    c.execute("INSERT OR REPLACE INTO products(sku,name,barcode,on_hand,category) VALUES(?,?,?,?,?)",
              (sku, name, "BC" + sku, on_hand, cat))
    c.commit(); c.close()


def _catalog(client, archived=False):
    j = client.get("/api/products" + ("?archived=1" if archived else "")).get_json()
    return sorted(p["sku"] for p in j)


def test_archive_hides_from_catalog_and_restore_brings_back(appmod, client):
    A = appmod; hdr = _admin(client, A)
    a, b = "A" + uuid.uuid4().hex[:5], "B" + uuid.uuid4().hex[:5]
    _prod(A, a); _prod(A, b)
    assert a in _catalog(client) and b in _catalog(client)
    r = client.post("/api/products/bulk", json={"action": "archive", "skus": [a, b]}, headers=hdr).get_json()
    assert r["ok"] and r["changed"] == 2
    cat = _catalog(client)
    assert a not in cat and b not in cat                 # hidden from the normal catalog
    arch = _catalog(client, archived=True)
    assert a in arch and b in arch                        # visible under the archived view
    # restore one
    client.post("/api/products/bulk", json={"action": "restore", "skus": [a]}, headers=hdr)
    assert a in _catalog(client) and b not in _catalog(client)


def test_archive_keeps_the_row_and_its_history(appmod, client):
    """Archive is a soft-delete: the products row (and anything referencing it) stays."""
    A = appmod; hdr = _admin(client, A); sku = "K" + uuid.uuid4().hex[:5]
    _prod(A, sku, on_hand=7)
    client.post("/api/products/bulk", json={"action": "archive", "skus": [sku]}, headers=hdr)
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT archived,on_hand FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    assert row is not None and row["archived"] == 1 and row["on_hand"] == 7   # row + stock preserved


def test_bulk_set_category(appmod, client):
    A = appmod; hdr = _admin(client, A)
    a, b = "C" + uuid.uuid4().hex[:5], "D" + uuid.uuid4().hex[:5]
    _prod(A, a); _prod(A, b)
    r = client.post("/api/products/bulk", json={"action": "category", "skus": [a, b], "value": "Lip"}, headers=hdr).get_json()
    assert r["ok"] and r["changed"] == 2
    c = A.sdb(A.DEFAULT_ORG)
    cats = {x["sku"]: x["category"] for x in c.execute("SELECT sku,category FROM products WHERE sku IN (?,?)", (a, b)).fetchall()}
    c.close()
    assert cats[a] == "Lip" and cats[b] == "Lip"


def test_inline_rename_changes_only_name(appmod, client):
    A = appmod; hdr = _admin(client, A); sku = "R" + uuid.uuid4().hex[:5]
    _prod(A, sku, name="New product • 889", cat="Needs review")
    r = client.post("/api/products/bulk", json={"action": "rename", "names": {sku: "Gucci Lipstick 308"}}, headers=hdr).get_json()
    assert r["ok"] and r["changed"] == 1
    c = A.sdb(A.DEFAULT_ORG)
    row = c.execute("SELECT name,category,barcode FROM products WHERE sku=?", (sku,)).fetchone(); c.close()
    assert row["name"] == "Gucci Lipstick 308"
    assert row["category"] == "Needs review" and row["barcode"] == "BC" + sku   # untouched


def test_archive_is_admin_only(appmod, client):
    A = appmod; sku = "S" + uuid.uuid4().hex[:5]; _prod(A, sku)
    hdr = _admin(client, A, role="cs")
    assert client.post("/api/products/bulk", json={"action": "archive", "skus": [sku]}, headers=hdr).status_code == 403
    # but cs CAN recategorise / rename
    assert client.post("/api/products/bulk", json={"action": "category", "skus": [sku], "value": "X"}, headers=hdr).get_json()["ok"]
