"""Mobile screens (/m/...): a separate front end over the same server.

They add routes and must never change what the desktop screens serve."""
import uuid


def _login(client, appmod, role, name="Ana Picker"):
    uname = "m-" + role
    with appmod.update_json(appmod.USERS_FILE) as users:      # the account must exist (session revocation)
        users[uname] = {"password": "x", "role": role, "name": name, "org": appmod.DEFAULT_ORG}
    with client.session_transaction() as s:
        s.update(user=uname, role=role, roles=[role], name=name, org=appmod.DEFAULT_ORG)
    client.set_cookie("csrf_token", "tok")
    client.csrf = {"X-CSRF-Token": "tok"}
    return client


def _ship(appmod, label, status="pending", started_by=None):
    sid = "m-" + uuid.uuid4().hex[:10]
    c = appmod.sdb(appmod.DEFAULT_ORG)
    c.execute("INSERT INTO shipments(shipment_id,status,import_batch,import_label,platform,pick_started_by) "
              "VALUES(?,?,'tiktok-api',?,'tiktok',?)", (sid, status, label, started_by))
    c.execute("INSERT INTO shipment_items(shipment_id,order_id,sku,product_name,quantity,picked) VALUES(?,?,'S1','Lip',1,0)",
              (sid, "O" + sid))
    c.commit(); c.close()
    return sid


def test_m_pick_requires_sign_in(client):
    r = client.get("/m/pick")
    assert r.status_code in (301, 302) and "/m/pick" not in r.headers["Location"]
    assert client.get("/m/api/pick/extras").status_code in (301, 302)


def test_m_pick_roles_match_desktop_pick(client, appmod):
    """Whoever can open /pick can open /m/pick, and nobody else."""
    for role in ("worker", "picker", "admin", "cs", "manager", "host"):
        c = _login(appmod.app.test_client(), appmod, role)
        assert c.get("/m/pick").status_code == c.get("/pick").status_code, role
    assert _login(appmod.app.test_client(), appmod, "host").get("/m/pick").status_code == 403


def test_m_pick_page_is_the_mobile_screen(client, appmod):
    c = _login(client, appmod, "worker", name="Ana <b>x</b> Picker")
    r = c.get("/m/pick")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "/m/static/pick.js?v=" in body and "/m/static/mobile.css?v=" in body
    assert 'class="m-avatar">AP<' in body                       # initials
    assert "Ana &lt;b&gt;x" in body and "Ana <b>x" not in body   # name is escaped
    assert "__" not in body.split("</head>")[0]                 # no unreplaced placeholders
    assert "X-CSRF-Token" in body                               # the app's CSRF shim was injected
    for f in ("mobile.css", "shell.css", "mobile.js", "pick.js"):
        assert client.get("/m/static/" + f).status_code == 200, f


def test_m_index_goes_to_pick(client, appmod):
    r = _login(client, appmod, "worker").get("/m/")
    assert r.status_code in (301, 302) and r.headers["Location"].endswith("/m/pick")


def test_extras_reports_pickers_and_issues_per_show(client, appmod):
    label = "Show " + uuid.uuid4().hex[:6]
    _ship(appmod, label, started_by="Maria Lopez")
    _ship(appmod, label, started_by="Maria Lopez")
    _ship(appmod, label)                                  # nobody on it
    _ship(appmod, label, status="issue")
    _ship(appmod, label, status="picked", started_by="Old Picker")   # finished orders don't count as "picking now"
    d = _login(client, appmod, "worker").get("/m/api/pick/extras").get_json()
    assert d["ok"] and d["me"] == "Ana Picker"
    assert d["shows"][label] == {"pickers": ["Maria Lopez"], "issues": 1}


def test_extras_is_read_only(client, appmod):
    label = "Show " + uuid.uuid4().hex[:6]
    sid = _ship(appmod, label)
    _login(client, appmod, "worker").get("/m/api/pick/extras")
    c = appmod.sdb(appmod.DEFAULT_ORG)
    row = c.execute("SELECT status, pick_started_by, picked_by FROM shipments WHERE shipment_id=?", (sid,)).fetchone()
    c.close()
    assert tuple(row) == ("pending", None, None)


def test_desktop_pick_page_is_untouched(client, appmod):
    """The mobile module must not alter the desktop Pick screen."""
    body = _login(client, appmod, "worker").get("/pick").get_data(as_text=True)
    assert "/m/static/" not in body and "m-screen" not in body
    assert "scanInput" in body                              # still the desktop template
