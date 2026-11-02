import pytest
from pydantic import ValidationError

from app.core.config import LOCAL_DATABASE_URL, Settings, get_settings
from app.db.session import get_db, get_engine
from app.main import create_app


def test_development_may_use_the_local_database() -> None:
    assert Settings(app_env="development", database_url=LOCAL_DATABASE_URL, _env_file=None)


def test_production_refuses_the_local_database() -> None:
    with pytest.raises(ValidationError, match="real database"):
        Settings(app_env="production", database_url=LOCAL_DATABASE_URL, _env_file=None)


def test_production_accepts_a_real_database() -> None:
    settings = Settings(
        app_env="production", database_url="postgresql+psycopg://u:p@db/x", _env_file=None
    )
    assert settings.app_env == "production"


def test_api_docs_are_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/x")
    get_settings.cache_clear()
    try:
        assert create_app().docs_url is None
    finally:
        get_settings.cache_clear()


def test_get_db_gives_a_closed_session_after_use(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        generator = get_db()
        session = next(generator)
        assert session.bind is get_engine()
        generator.close()
    finally:
        get_settings.cache_clear()
        get_engine.cache_clear()
