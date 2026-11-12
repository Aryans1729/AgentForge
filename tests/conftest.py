"""Shared fixtures. Every DB test runs once per backend: SQLite and PostgreSQL.

Postgres tests need ``EG_TEST_DATABASE_URL`` (see .env.example). Without it they are
*skipped* and shown as skipped. Set ``EG_REQUIRE_POSTGRES=1`` (CI) to turn the skip
into a failure so a missing database can never masquerade as a green run.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from enterprisegym.config import Settings
from enterprisegym.db import Base
from enterprisegym.db.session import make_engine

BACKENDS = ["sqlite", pytest.param("postgres", marks=pytest.mark.postgres)]


def _postgres_test_url() -> str:
    url = Settings().test_database_url
    if not url:
        message = "EG_TEST_DATABASE_URL not set (cp .env.example .env; docker compose up -d db)"
        if os.environ.get("EG_REQUIRE_POSTGRES") == "1":
            pytest.fail(message)
        pytest.skip(message)
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.fail(f"refusing to drop tables in non-test database {database!r}")
    return url


def _reset_postgres(engine: Engine) -> None:
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture(params=BACKENDS)
def empty_engine(request: pytest.FixtureRequest) -> Iterator[Engine]:
    """A connected engine with *no* tables, for each backend."""
    if request.param == "sqlite":
        engine = make_engine("sqlite+pysqlite:///:memory:")
        yield engine
        engine.dispose()
        return

    engine = make_engine(_postgres_test_url())
    _reset_postgres(engine)
    yield engine
    _reset_postgres(engine)
    engine.dispose()


@pytest.fixture
def engine(empty_engine: Engine) -> Engine:
    Base.metadata.create_all(empty_engine)
    return empty_engine


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s
