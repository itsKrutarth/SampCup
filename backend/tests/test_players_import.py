import pytest
from fastapi.testclient import TestClient

from app.models import Player
from app.services.errors import ServiceError
from app.services.players import NO_CENTER, email_key, import_players, parse_players
from app.store import Store
from tests.factories import HEADER, find, make_team, row, xlsx

# The registration system's newer export (2026-11-23): no MISID values, a BAPS ID and email.
NEW_HEADER = ["Created date (UTC)", "Card Name", "Customer Email", "BAPSId (metadata)"]
NEW_HEADER += ["LastName", "FirstName", "MISID", "Center"]


def new_row(first: str, last: str, center: str, baps: str = "", email: str = "") -> list:
    email = email or f"{first}.{last}@example.com".lower()
    return ["11/21/26 19:42", "", email, baps, last, first, None, center]


def upload(client: TestClient, headers: dict[str, str], content: bytes, name: str = "export.xlsx"):
    return client.post(
        "/api/admin/players/import", headers=headers, files={"file": (name, content)}
    )


def test_import_adds_players_from_the_registration_export(client: TestClient, admin: dict) -> None:
    content = xlsx(
        [row(123456, "Aarav"), row(234567.0, "Dev"), [None] * 9, row(345678, "Jay", center="South")]
    )
    report = upload(client, admin, content).json()
    assert report["added"] == 3 and report["skipped"] == []
    players = client.get("/api/admin/players", headers=admin).json()
    assert {p["mis_id"] for p in players} == {"123456", "234567", "345678"}
    assert players[0]["tshirt_size"] == "Large"


def test_reimport_matches_players_and_deactivates_missing_ones(store: Store) -> None:
    import_players(store, xlsx([row(1, "Aarav"), row(2, "Dev"), row(3, "Jay")]))
    team = make_team(store)
    report = import_players(store, xlsx([row(1, "Aarav"), row(2, "Devan"), row(5, "Om")]))
    assert {k: report[k] for k in ("added", "updated", "unchanged", "deactivated")} == {
        "added": 1,  # Om
        "updated": 1,  # Dev -> Devan: the same MISID, a corrected name
        "unchanged": 1,  # Aarav
        "deactivated": 3,  # Jay, and the two players of the test team
    }
    assert report["added_names"] == ["Om Tester (North)"]
    assert report["teams_with_removed_players"] == [team.name] and report["skipped"] == []
    assert find(store, Player, mis_id="2").first_name == "Devan"
    report = import_players(store, xlsx([row(1, "Aarav"), row(2, "Devan"), row(3, "Jay")]))
    assert report["updated"] == 1  # Jay came back
    assert find(store, Player, mis_id="3").active


def test_rows_with_problems_are_skipped_and_reported() -> None:
    content = xlsx(
        [row(1, "Aarav"), row(1, "Aarav"), row(None, "NoId"), row(2, ""), row(1, "Again")]
    )
    players, skipped = parse_players(content)
    assert [(p["first_name"], p["mis_id"]) for p in players] == [
        ("Aarav", "1"),
        ("NoId", ""),  # a MISID is optional now
        ("Again", "1"),  # a different name: kept (the MISID is then not used to match)
    ]
    assert skipped == [
        {"row": 3, "reason": "same person as row 2"},
        {"row": 5, "reason": "missing first_name"},
    ]


def test_the_newer_export_without_misids(store: Store) -> None:
    """The 2026-11-23 export: players known from the old export are recognised by name and
    center (or by name when their center changed), get their BAPS ID, and nobody is lost."""
    import_players(
        store,
        xlsx([row(11, "Aalay", "Shah", "Westborough"), row(12, "Neel", "Chauhan", "Toronto")]),
    )
    family = "family@example.com"
    rows = [
        new_row("Aalay", "Shah", "Westborough", "AL3838001"),
        new_row("Neel", "Chauhan", "Boston", "NC6219630"),  # moved center
        new_row("Jay", "Patel", "Boston", "JP0567001"),
        new_row("Jay", "Patel", "Boston", "JP1006001"),  # another Jay Patel at Boston
        new_row("Kush", "Patel", "", "KP1006002"),  # no center
        new_row("Ved", "Shah", "Hartford", "", family),
        new_row("Rudra", "Shah", "Hartford", "", family),  # a sibling: the same family email
        new_row("Ved", "Shah", "Hartford", "", family),  # Ved registered twice
    ]
    preview = import_players(store, xlsx(rows, NEW_HEADER), preview=True)
    assert preview["preview"] and preview["added"] == 5 and preview["updated"] == 2
    assert store.all(Player).__len__() == 2  # a preview saves nothing
    report = import_players(store, xlsx(rows, NEW_HEADER))
    assert (report["added"], report["updated"], report["deactivated"]) == (5, 2, 0)
    assert report["skipped"] == [{"row": 9, "reason": "same person as row 7"}]
    assert report["center_changes"] == ["Neel Chauhan: Toronto -> Boston"]
    assert report["no_center"] == ["Kush Patel"]
    players = {(p.first_name, p.baps_id): p for p in store.all(Player)}
    aalay = players[("Aalay", "AL3838001")]
    assert aalay.mis_id == "11" and aalay.center == "Westborough"  # empty cells erase nothing
    assert players[("Kush", "KP1006002")].center == NO_CENTER
    assert players[("Ved", "")].email_key == email_key(family) == players[("Rudra", "")].email_key
    assert all("@" not in str(vars(p)) for p in store.all(Player))  # no email address stored
    # two Jay Patels at Boston, neither with a login or team: paired in order on the next
    # import of a file that still has no IDs for them (nothing to mix up)
    assert sum(p.first_name == "Jay" for p in store.all(Player)) == 2
    # the same file again: everyone recognised, nothing changes
    again = import_players(store, xlsx(rows, NEW_HEADER))
    assert (again["added"], again["updated"], again["unchanged"]) == (0, 0, 7)


def test_an_import_that_would_switch_off_most_players_is_refused(store: Store) -> None:
    import_players(store, xlsx([row(i, f"Player{i}") for i in range(1, 9)]))
    wrong = xlsx([new_row("Someone", "Else", "Boston")], NEW_HEADER)
    with pytest.raises(ServiceError, match="would switch off 8 of the 8 active players"):
        import_players(store, wrong)
    assert all(p.active for p in store.all(Player)) and len(store.all(Player)) == 8
    with pytest.raises(ServiceError, match="No usable rows"):
        import_players(store, xlsx([new_row("", "", "Boston")], NEW_HEADER))
    # after an accident like 2026-11-23 (everyone switched off), the right file brings them back
    for player in (everyone := store.all(Player)):
        player.active = False
    store.save_many(everyone)
    report = import_players(store, xlsx([row(i, f"Player{i}") for i in range(1, 9)]))
    assert report["updated"] == 8 and all(p.active for p in store.all(Player))


def test_admins_set_a_players_center(
    client: TestClient, store: Store, admin: dict, judge: dict
) -> None:
    import_players(store, xlsx([new_row("Kush", "Patel", "")], NEW_HEADER))
    kush = store.all(Player)[0]
    assert kush.center == NO_CENTER
    url = f"/api/admin/players/{kush.id}"
    saved = client.patch(url, headers=admin, json={"center": "  Boston "})
    assert saved.status_code == 200 and saved.json()["center"] == "Boston"
    assert client.patch(url, headers=admin, json={"center": ""}).status_code == 422
    assert client.patch(url, headers=admin, json={"center": "   "}).status_code == 400
    assert (
        client.patch("/api/admin/players/999", headers=admin, json={"center": "X"}).status_code
        == 404
    )
    assert client.patch(url, headers=judge, json={"center": "X"}).status_code == 403
    listed = client.get("/api/admin/players", headers=admin).json()
    assert listed[0]["baps_id"] == "" and listed[0]["center"] == "Boston"


def test_same_names_in_one_center_are_flagged_not_merged(store: Store) -> None:
    report = import_players(store, xlsx([row(1, "Aarav", "Patel"), row(2, "aarav", "PATEL")]))
    assert report["added"] == 2
    assert report["possible_duplicates"] == ["Aarav Patel (North)"]


def test_csv_exports_work_too(store: Store) -> None:
    content = ("﻿" + ",".join(HEADER) + "\n" + "NE,Cup,North,Z,Aarav,Tester,Male,77,M\n").encode()
    assert import_players(store, content)["added"] == 1


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"\xff\xfe\x00bad", "Upload the .xlsx or .csv"),
        (b"PK\x03\x04 not really a workbook", "Could not read"),
        (b"Name,Email\nA,b\n", "Missing columns: first_name, last_name"),
        (b"x" * (5 * 1024 * 1024 + 1), "larger than 5 MB"),
    ],
)
def test_bad_files_are_refused(content: bytes, message: str) -> None:
    with pytest.raises(ServiceError, match=message):
        parse_players(content)


def test_import_endpoint_reports_errors_and_needs_an_admin(
    client: TestClient, admin: dict, judge: dict
) -> None:
    response = upload(client, admin, b"Name\nA\n", "x.csv")
    assert response.status_code == 400 and "Missing columns" in response.json()["detail"]
    assert upload(client, judge, b"").status_code == 403
    assert client.get("/api/admin/players").status_code == 401


def test_namesakes_at_one_center_are_paired_only_when_nothing_can_be_mixed_up(
    store: Store,
) -> None:
    import_players(
        store, xlsx([row(1, "Jay", "Patel", "Boston"), row(2, "Jay", "Patel", "Boston")])
    )
    rows = [new_row("Jay", "Patel", "Boston", "JP1"), new_row("Jay", "Patel", "Boston", "JP2")]
    report = import_players(store, xlsx(rows, NEW_HEADER))
    assert (report["added"], report["updated"], report["deactivated"]) == (0, 2, 0)
    assert sorted(p.baps_id for p in store.all(Player)) == ["JP1", "JP2"]
    # once one of them has a login, a file that cannot tell them apart changes neither
    for player in (both := store.all(Player)):
        player.baps_id = ""
    both[0].username = "jay1"
    store.save_many(both)
    report = import_players(store, xlsx(rows, NEW_HEADER), preview=True)
    assert report["added"] == 2 and report["deactivated"] == 2
