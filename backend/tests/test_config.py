import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.main import create_app


def test_development_needs_no_secret() -> None:
    assert Settings(app_env="development", _env_file=None).origin_secret is None


def test_production_refuses_to_run_without_the_cloudfront_secret() -> None:
    with pytest.raises(ValidationError, match="ORIGIN_SECRET"):
        Settings(app_env="production", _env_file=None)
    assert Settings(app_env="production", origin_secret="s", _env_file=None).app_env == "production"


def test_api_docs_are_hidden_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ORIGIN_SECRET", "s")
    get_settings.cache_clear()
    try:
        assert create_app().docs_url is None
    finally:
        get_settings.cache_clear()
