from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DATABASE_URL = "postgresql+psycopg://sampcup:local-dev-only@localhost:5432/sampcup"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SampCup API"
    app_env: str = "development"
    database_url: str = LOCAL_DATABASE_URL

    @model_validator(mode="after")
    def production_needs_real_database(self) -> "Settings":
        if self.app_env == "production" and "local-dev-only" in self.database_url:
            raise ValueError("DATABASE_URL must be set to a real database in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
