"""Workstream C (P0): per-tenant data isolation (one SQLite file set per org)."""
import os, uuid


def test_per_org_shipment_isolation(appmod):
    a = "ten-a-" + uuid.uuid4().hex[:6]; b = "ten-b-" + uuid.uuid4().hex[:6]
    for org in (a, b):
        os.makedirs(os.path.dirname(appmod.shipments_db_path(org)), exist_ok=True)
        appmod.sdb_init(org)
    assert appmod.shipments_db_path(a) != appmod.shipments_db_path(b)
    ca = appmod.sdb(a)
    ca.execute("INSERT INTO shipments(shipment_id,status,platform) VALUES('X-ISO','pending','tiktok')")
    ca.commit(); ca.close()
    cb = appmod.sdb(b)
    seen = cb.execute("SELECT COUNT(*) FROM shipments WHERE shipment_id='X-ISO'").fetchone()[0]
    cb.close()
    assert seen == 0, "org B must not see org A's shipment"
