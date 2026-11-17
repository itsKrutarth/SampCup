import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Player
from app.services.errors import ServiceError
from app.services.players import import_players, parse_players
from tests.factories import HEADER, make_team, row, xlsx


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


def test_reimport_updates_by_misid_and_deactivates_missing_players(db: Session) -> None:
    import_players(db, xlsx([row(1, "Aarav"), row(2, "Dev"), row(3, "Jay")]))
    team = make_team(db)
    db.get(Player, team.players[0].id).mis_id = "4"
    db.commit()
    report = import_players(db, xlsx([row(1, "Aarav"), row(2, "Devan"), row(5, "Om")]))
    assert report == {
        "added": 1,
        "updated": 1,
        "unchanged": 1,
        "deactivated": 3,
        "possible_duplicates": [],
        "skipped": [],
        "teams_with_removed_players": [team.name],
    }
    report = import_players(db, xlsx([row(1, "Aarav"), row(2, "Devan"), row(3, "Jay")]))
    assert report["updated"] == 1  # Jay came back
    assert db.scalar(select(Player).where(Player.mis_id == "3")).active


def test_rows_with_problems_are_skipped_and_reported() -> None:
    content = xlsx([row(1, "Aarav"), row(1, "Again"), row(None, "NoId"), row(2, "")])
    players, skipped = parse_players(content)
    assert [p["mis_id"] for p in players] == ["1"]
    assert skipped == [
        {"row": 3, "reason": "MISID 1 repeated"},
        {"row": 4, "reason": "missing mis_id"},
        {"row": 5, "reason": "missing first_name"},
    ]


def test_same_names_in_one_center_are_flagged_not_merged(db: Session) -> None:
    report = import_players(db, xlsx([row(1, "Aarav", "Patel"), row(2, "aarav", "PATEL")]))
    assert report["added"] == 2
    assert report["possible_duplicates"] == ["Aarav Patel (North)"]


def test_csv_exports_work_too(db: Session) -> None:
    content = ("﻿" + ",".join(HEADER) + "\n" + "NE,Cup,North,Z,Aarav,Tester,Male,77,M\n").encode()
    assert import_players(db, content)["added"] == 1


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"\xff\xfe\x00bad", "Upload the .xlsx or .csv"),
        (b"PK\x03\x04 not really a workbook", "Could not read"),
        (b"Name,Email\nA,b\n", "Missing columns: mis_id, first_name, last_name, center"),
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
