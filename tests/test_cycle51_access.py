"""Cycle-51: Access Management. Custom roles inherit a base security tier (so req_role still
enforces), and a per-screen DENY layer hides/blocks screens — never granting beyond the tier,
never blocking admin or core screens, and defaulting to today's behavior when nothing is set."""


def test_custom_role_resolves_to_base_tier(appmod):
    A = appmod
    A._access_save(A.DEFAULT_ORG, {"packer_lead": {"base": "manager", "label": "Packer Lead"}}, {})
    roles = A._effective_roles({"role": "packer_lead", "org": A.DEFAULT_ORG})
    assert "manager" in roles          # base tier present → req_role enforces at manager level
    assert "packer_lead" in roles      # raw custom name kept → drives the page-access layer
    assert A._role_base("packer_lead", A.DEFAULT_ORG) == "manager"
    assert A._role_base("cs", A.DEFAULT_ORG) == "cs"   # a base role maps to itself


def test_page_blocked_rules(appmod):
    A = appmod
    A._access_save(A.DEFAULT_ORG, {"packer_lead": {"base": "manager", "label": "PL"}},
                   {"packer_lead": ["profit", "shows"]})
    assert A._page_blocked("packer_lead", "profit", A.DEFAULT_ORG) is True    # explicitly blocked
    assert A._page_blocked("packer_lead", "pick", A.DEFAULT_ORG) is False     # manager default allows pick
    # admin is never blocked, even if somehow listed
    A._access_save(A.DEFAULT_ORG, {}, {"admin": ["profit"]})
    assert A._page_blocked("admin", "profit", A.DEFAULT_ORG) is False
    # always-pages (personal) are never blockable
    A._access_save(A.DEFAULT_ORG, {}, {"cs": ["me"]})
    assert A._page_blocked("cs", "me", A.DEFAULT_ORG) is False
    # cycle-76: a screen outside the role's default is blocked UNLESS granted
    A._access_save(A.DEFAULT_ORG, {}, {})
    assert A._page_blocked("worker", "profit", A.DEFAULT_ORG) is True         # not in worker default
    A._access_save(A.DEFAULT_ORG, {}, {}, {"worker": ["profit"]})             # grant it
    assert A._page_allowed("worker", "profit", A.DEFAULT_ORG) is True
    # a block beats a grant
    A._access_save(A.DEFAULT_ORG, {}, {"worker": ["profit"]}, {"worker": ["profit"]})
    assert A._page_allowed("worker", "profit", A.DEFAULT_ORG) is False


def test_blocked_page_returns_403(appmod, client):
    A = appmod
    # block a screen CS normally can open, so this proves the deny gate (not req_role)
    A._access_save(A.DEFAULT_ORG, {}, {"cs": ["shipments"]})
    with client.session_transaction() as s:
        s.update(user="cs1", role="cs", roles=["cs"], org=A.DEFAULT_ORG, name="C")
    assert client.get("/admin/shipments").status_code == 403       # blocked by the deny gate
    assert client.get("/customers").status_code != 403             # an allowed CS screen is not blocked


def test_create_and_delete_custom_role(appmod, client):
    A = appmod
    with client.session_transaction() as s:
        s.update(user="admin", role="admin", roles=["admin"], org=A.DEFAULT_ORG, name="Boss")
    client.set_cookie("csrf_token", "tok")
    hdr = {"X-CSRF-Token": "tok"}
    r = client.post("/api/access/role", json={"action": "create", "label": "Packer Lead", "base": "manager"},
                    headers=hdr).get_json()
    assert r["ok"] is True and r["base"] == "manager"
    key = r["key"]
    assert key in A._access(A.DEFAULT_ORG)["roles"]
    # a user can now be assigned the custom role
    with A.update_json(A.USERS_FILE) as uu:
        uu["pl1"] = {"password": "x", "role": key, "name": "Lead", "org": A.DEFAULT_ORG}
    assert A._role_base(key, A.DEFAULT_ORG) == "manager"
    r2 = client.post("/api/access/role", json={"action": "delete", "key": key}, headers=hdr).get_json()
    assert r2["ok"] is True and key not in A._access(A.DEFAULT_ORG)["roles"]


def test_access_survives_missing_file(appmod, tmp_path, monkeypatch):
    """The Access screen 500'd in production because _access crashed when access.json didn't exist
    yet. It must return an empty config instead, so the roles still render."""
    A = appmod
    monkeypatch.setattr(A, "ACCESS_FILE", str(tmp_path / "does_not_exist.json"))
    cfg = A._access(A.DEFAULT_ORG)
    assert cfg == {"roles": {}, "blocked": {}, "granted": {}}
    assert "worker" in A._all_role_keys(A.DEFAULT_ORG)   # base roles still list
