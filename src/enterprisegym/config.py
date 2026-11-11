"""Runtime settings, read from environment variables (prefix ``EG_``) or a local ``.env``."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EG_", env_file=".env", extra="ignore")

    # Default: in-memory SQLite, so the package works with zero setup.
    # Postgres is used whenever EG_DATABASE_URL points at it (Docker, integration tests).
    database_url: str = "sqlite+pysqlite:///:memory:"


def get_settings() -> Settings:
    return Settings()
