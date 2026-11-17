import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app import cli
from app.core.config import get_settings
from app.models import Match, StaffUser, Team


@pytest.fixture
def cli_engine(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Engine:
    monkeypatch.setattr(cli, "get_engine", lambda: engine)
    return engine


def test_create_admin_reads_the_password_from_the_environment(
    cli_engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("SAMPCUP_ADMIN_PASSWORD", "a-long-password")
    cli.main(["create-admin", "Krutarth", "--name", "Owner"])
    assert "Created admin krutarth" in capsys.readouterr().out
    with Session(cli_engine) as db:
        assert db.scalar(select(StaffUser.role)) == "admin"


def test_seed_demo_fills_an_empty_database_once(
    cli_engine: Engine, capsys: pytest.CaptureFixture
) -> None:
    cli.main(["seed-demo", "--teams", "32"])
    assert "Seeded 32 demo teams" in capsys.readouterr().out
    with Session(cli_engine) as db:
        assert db.scalar(select(func.count()).select_from(Team)) == 32
        assert db.scalar(select(func.count()).select_from(Match)) == 128 + 17
    with pytest.raises(SystemExit, match="already has players"):
        cli.main(["seed-demo"])


def test_seed_demo_never_runs_in_production(
    cli_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/x")
    get_settings.cache_clear()
    try:
        with pytest.raises(SystemExit, match="never runs in production"):
            cli.main(["seed-demo"])
    finally:
        get_settings.cache_clear()
