"""Cycle-19 (stage B): the Match screen exposes the bundle controls."""
def test_match_has_bundle_ui(appmod, client):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=appmod.DEFAULT_ORG, name="M")
    client.set_cookie("csrf_token", "tok")
    h = client.get("/admin/match-live").get_data(as_text=True)
    for tok in ('id="kitBtn"', 'id="kitChips"', 'function kitAdd', '/api/live/kit/add', 'bundle'):
        assert tok in h, "missing " + tok
