"""Cycle-58: Whatnot Seller API — Phase 0 read-only connect + probe. No network here; we test the
pure helpers and that the probe refuses without a token and never leaks PII values."""


def test_wn_first_handles_array_and_envelopes(appmod):
    A = appmod
    assert A._wn_first([{"id": 1}, {"id": 2}])["id"] == 1
    assert A._wn_first({"data": [{"id": 9}]})["id"] == 9
    assert A._wn_first({"orders": [{"id": 7}]})["id"] == 7
    assert A._wn_first([]) is None
    assert A._wn_first({"data": []}) is None


def test_field_report_presence_only_never_value(appmod):
    A = appmod
    obj = {"buyer": {"name": "Jane Doe", "address": "123 Secret St"}, "order_id": "O1", "note": None}
    rep = A._wn_field_report(obj, ["buyer", "note", "missing_field"])
    assert rep == {"buyer": "present", "note": "null", "missing_field": "missing"}
    # the report must never carry the actual PII value
    import json
    assert "Jane Doe" not in json.dumps(rep) and "Secret" not in json.dumps(rep)


def test_probe_refuses_without_token(appmod, client, monkeypatch):
    A = appmod
    monkeypatch.delenv("WHATNOT_API_TOKEN", raising=False)
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    r = client.get("/api/whatnot/probe").get_json()
    assert r["ok"] is False and "WHATNOT_API_TOKEN" in r["error"]


def test_probe_is_admin_only(appmod, client, monkeypatch):
    A = appmod
    monkeypatch.setenv("WHATNOT_API_TOKEN", "wn_pat_tk_dummy")
    with client.session_transaction() as s:
        s.update(user="w1", role="worker", roles=["worker"], org=A.DEFAULT_ORG, name="W")
    assert client.get("/api/whatnot/probe").status_code in (401, 403)


def test_ready_flag_reads_env(appmod, monkeypatch):
    A = appmod
    monkeypatch.delenv("WHATNOT_API_TOKEN", raising=False)
    assert A._wn_ready() is False
    monkeypatch.setenv("WHATNOT_API_TOKEN", "wn_pat_tk_x")
    assert A._wn_ready() is True
