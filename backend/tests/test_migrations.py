from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.db.base import Base
from tests.conftest import TEST_DATABASE_URL

BACKEND = Path(__file__).resolve().parent.parent
REFERENCE = BACKEND.parent / "Tournament Resources" / "ranking.py"


def test_migrations_build_exactly_the_models(tmp_path: Path) -> None:
    url = TEST_DATABASE_URL or f"sqlite:///{tmp_path / 'migrate.db'}"
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    config.attributes["url"] = url
    command.upgrade(config, "head")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    command.downgrade(config, "base")
    engine.dispose()
    assert diff == []


@pytest.mark.skipif(not REFERENCE.exists(), reason="reference rules not in this checkout")
def test_ranking_is_the_reviewed_reference_copy() -> None:
    assert (BACKEND / "app" / "tournament" / "ranking.py").read_bytes() == REFERENCE.read_bytes()
