"""Cycle-18: Live Match 'My section' — a worker can pick a start/end sticker range and
direction so several people split the table. Client-side feature; assert the controls and
the pool/advance helpers are present on the page."""


def _admin(client, appmod):
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=appmod.DEFAULT_ORG, name="Maya")
    client.set_cookie("csrf_token", "tok")
    return client


def test_match_screen_has_my_section_controls(appmod, client):
    _admin(client, appmod)
    h = client.get("/admin/match-live").get_data(as_text=True)
    assert h.count("</html>")  # full page rendered
    for tok in ('id="secFrom"', 'id="secTo"', 'id="secDir"', 'id="secApply"',
                'id="secClear"', "My section", "High &rarr; Low".replace("&rarr;", "→"),
                "function applyPool", "function secActive", "localStorage"):
        assert tok in h, "missing: " + tok
    # the range filter + direction sort must be wired into the queue render
    assert "pool=applyPool(pool)" in h
