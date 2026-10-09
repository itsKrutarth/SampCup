from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = 'SampCup API'
    database_url: str = 'postgresql+psycopg://sampcup:sampcup@db:5432/sampcup'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

settings = Settings()
