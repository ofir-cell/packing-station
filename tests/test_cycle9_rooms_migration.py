"""Cycle-9 hotfix: tiktok_rooms missing-column migration.

Reproduces the exact Production failure — an OLD-schema tiktok_rooms table missing
label/start_ts/named — and proves _tt_rooms_ensure backfills them additively and that
order materialization (_tt_apply_order via the room-label path) then succeeds."""
import uuid


def _old_schema_rooms(c):
    """Simulate the pre-existing Production table: created before label/start_ts/named
    existed (only room_id + custom_name), which is what threw 'no such column: label'."""
    c.execute("DROP TABLE IF EXISTS tiktok_rooms")
    c.execute("CREATE TABLE tiktok_rooms(room_id TEXT PRIMARY KEY, custom_name TEXT)")
    c.execute("INSERT INTO tiktok_rooms(room_id,custom_name) VALUES('R-OLD','Hand Named')")
    c.commit()


def test_reproduce_then_migrate(appmod):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    _old_schema_rooms(c)
    # BEFORE: the production query fails exactly as logged
    import sqlite3, pytest
    with pytest.raises(sqlite3.OperationalError) as e:
        c.execute("SELECT label,named,start_ts,custom_name FROM tiktok_rooms WHERE room_id='R-OLD'").fetchone()
    assert "no such column: label" in str(e.value)
    # MIGRATE
    appmod._tt_rooms_ensure(c); c.commit()
    cols = {r[1] for r in c.execute("PRAGMA table_info(tiktok_rooms)").fetchall()}
    assert {"room_id", "label", "start_ts", "named", "custom_name"} <= cols
    # AFTER: the query works AND the hand-set custom_name row is preserved (no data loss)
    row = c.execute("SELECT label,named,start_ts,custom_name FROM tiktok_rooms WHERE room_id='R-OLD'").fetchone()
    assert row["custom_name"] == "Hand Named" and row["label"] is None
    c.close()


def test_apply_order_with_room_succeeds_after_migration(appmod):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    _old_schema_rooms(c)
    appmod._tt_rooms_ensure(c); c.commit()
    oid = "ORD-" + uuid.uuid4().hex[:6]
    pkg = "PKG-" + uuid.uuid4().hex[:6]
    order = {"id": oid, "status": "AWAITING_SHIPMENT",
             "packages": [{"id": pkg}],
             "line_items": [{"id": "L1", "seller_sku": "SK1", "sku_id": "SK1",
                             "product_name": "Lip Oil", "sale_price": "5",
                             "package_id": pkg, "live_room_id": "R-NEW"}],
             "recipient_address": {"full_address": "1 Main St", "postal_code": "19702"}}
    # Must NOT raise, and must create the shipment (materialization works again)
    appmod._tt_apply_order(c, order); c.commit()
    sh = c.execute("SELECT shipment_id,status,platform,import_label FROM shipments WHERE shipment_id=?", (pkg,)).fetchone()
    assert sh and sh["platform"] == "tiktok" and sh["import_label"]
    it = c.execute("SELECT sku,quantity FROM shipment_items WHERE shipment_id=?", (pkg,)).fetchone()
    assert it["sku"] == "SK1"
    c.close()


def test_migration_is_idempotent(appmod):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    appmod._tt_rooms_ensure(c); appmod._tt_rooms_ensure(c); c.commit()  # twice = no error
    cols = {r[1] for r in c.execute("PRAGMA table_info(tiktok_rooms)").fetchall()}
    assert {"label", "start_ts", "named", "custom_name"} <= cols
    c.close()
