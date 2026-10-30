"""Today dashboard (admin): repeat buyers = today's buyers who also bought before today."""
import uuid
from datetime import datetime, timedelta


def test_repeat_buyers_counts_todays_buyers_with_an_earlier_order(appmod, client):
    A = appmod; t = uuid.uuid4().hex[:6]
    today = datetime.now().strftime("%Y-%m-%d"); past = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    c = A.sdb(A.DEFAULT_ORG)
    before = None
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], name="admin", org=A.DEFAULT_ORG)
    before = client.get("/api/today").get_json()["money"]["repeat_buyers"]
    rows = [("R1" + t, "ret_" + t, past), ("R2" + t, "ret_" + t, today), ("R3" + t, "ret_" + t, today),   # returning: counts once
            ("N1" + t, "new_" + t, today),                                                             # first-timer: no
            ("O1" + t, "old_" + t, past)]                                                              # not today: no
    c.executemany("INSERT INTO shipments(shipment_id,buyer_username,show_date,status) VALUES(?,?,?,'pending')", rows)
    c.commit(); c.close()
    assert client.get("/api/today").get_json()["money"]["repeat_buyers"] == before + 1


def test_buyer_index_exists(appmod):
    c = appmod.sdb(appmod.DEFAULT_ORG)
    names = {r[1] for r in c.execute("PRAGMA index_list(shipments)").fetchall()}
    c.close()
    assert "idx_ship_buyer" in names
