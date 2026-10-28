"""Backup V2 must cover all VOLUME-resident persistent data per org, not just the DBs."""
def test_targets_cover_volume_files(appmod, monkeypatch):
    monkeypatch.setattr(appmod, "list_org_ids", lambda: ["5sec", "acme"])
    names = {n for n, _ in appmod._backup_targets()}
    assert {"platform.db", "users.json", "stations.json"} <= names
    for org in ("5sec", "acme"):
        for fn in ("shipments.db", "giveaways.db", "packing_log.csv", "documents.json",
                   "announcements.json", "onboarding.json"):
            assert f"{org}/{fn}" in names, f"missing {org}/{fn}"
