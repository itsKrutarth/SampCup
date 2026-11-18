from datetime import date

import boto3
import pytest

from app import cli
from app.core.config import get_settings
from app.models import Match, Player, StaffUser, Team
from app.services.tournament import get_tournament
from app.store import Store


@pytest.fixture
def cli_store(store: Store, monkeypatch: pytest.MonkeyPatch) -> Store:
    monkeypatch.setattr(cli, "get_table", lambda: store.table)
    return store


def test_create_admin_reads_the_password_from_the_environment(
    cli_store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("SAMPCUP_ADMIN_PASSWORD", "a-long-password")
    cli.main(["create-admin", "Krutarth", "--name", "Owner"])
    assert "Created admin krutarth" in capsys.readouterr().out
    assert cli_store.all(StaffUser)[0].role == "admin"


def test_create_judges_once_per_court(cli_store: Store, capsys: pytest.CaptureFixture) -> None:
    cli.main(["create-judges"])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 9 and lines[0].startswith("court-1  PIN ")
    assert sorted(u.court for u in cli_store.all(StaffUser)) == list(range(1, 10))
    cli.main(["create-judges"])
    assert capsys.readouterr().out == ""  # nobody is created twice


def test_seed_demo_fills_an_empty_table_once(
    cli_store: Store, capsys: pytest.CaptureFixture
) -> None:
    cli.main(["seed-demo", "--teams", "32"])
    assert "Seeded 32 demo teams" in capsys.readouterr().out
    assert len(cli_store.all(Team)) == 32
    assert len(cli_store.all(Match)) == 128 + 17
    with pytest.raises(SystemExit, match="already has players"):
        cli.main(["seed-demo"])


def test_reset_data_needs_yes_and_can_keep_staff(
    cli_store: Store, capsys: pytest.CaptureFixture
) -> None:
    cli.seed_demo(cli_store, 32)
    cli.create_judges(cli_store, 2)
    with pytest.raises(SystemExit, match="Add --yes"):
        cli.main(["reset-data"])
    cli.main(["reset-data", "--yes", "--keep-staff", "--event-date", "2026-12-06"])
    assert "Deleted" in capsys.readouterr().out
    assert cli_store.all(Player) == [] and cli_store.all(Match) == []
    assert len(cli_store.all(StaffUser)) == 2
    assert get_tournament(cli_store).event_date == date(2026, 12, 6)
    cli.main(["reset-data", "--yes"])
    assert cli_store.all(StaffUser) == []


def test_create_table_is_only_for_dynamodb_local(
    cli_store: Store, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    with pytest.raises(SystemExit, match="DynamoDB Local"):
        cli.main(["create-table"])
    monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
    monkeypatch.setenv("TABLE_NAME", "local-copy")
    monkeypatch.setattr(
        cli, "dynamodb_resource", lambda: boto3.resource("dynamodb", region_name="us-east-1")
    )
    get_settings.cache_clear()
    try:
        cli.main(["create-table"])
    finally:
        get_settings.cache_clear()
    assert "Created table local-copy" in capsys.readouterr().out
