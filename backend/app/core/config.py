from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SampCup API"
    app_env: str = "development"
    table_name: str = "sampcup-local"
    aws_region: str = "us-east-1"
    # DynamoDB Local in development; unset on AWS.
    dynamodb_endpoint: str | None = None
    # Shared secret CloudFront adds to every request; the app refuses requests without it.
    origin_secret: str | None = None
    session_hours: int = 20

    @model_validator(mode="after")
    def production_is_locked_down(self) -> "Settings":
        if self.app_env == "production" and not self.origin_secret:
            raise ValueError("ORIGIN_SECRET must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
