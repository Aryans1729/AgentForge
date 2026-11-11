"""Runtime settings, read from environment variables (prefix ``EG_``) or a local ``.env``."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EG_", env_file=".env", extra="ignore")

    # Default: in-memory SQLite, so the package works with zero setup.
    # Postgres is used whenever EG_DATABASE_URL points at it (Docker, integration tests).
    database_url: str = "sqlite+pysqlite:///:memory:"

    # Separate database for the Postgres test suite. Tests drop and recreate tables, so
    # they refuse to run against a database whose name does not end in "_test".
    test_database_url: str | None = None


def get_settings() -> Settings:
    return Settings()
