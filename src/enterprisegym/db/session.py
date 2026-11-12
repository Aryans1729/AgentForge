"""Engine and session factories for SQLite and PostgreSQL."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from enterprisegym.config import get_settings


def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    # SQLite parses FOREIGN KEY clauses but ignores them unless this pragma is set on
    # *every* connection. Without it, an orphan claim inserts silently on SQLite and fails
    # on Postgres: exactly the dialect drift our dual-backend tests exist to catch.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    if url.startswith("sqlite"):
        kwargs: dict[str, Any] = {}
        if ":memory:" in url or url.rstrip("/").endswith("sqlite://"):
            # One shared connection, otherwise each new connection sees an empty database.
            kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
        engine = create_engine(url, **kwargs)
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
        return engine
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Unit of work: commit on success, roll back on any exception."""
    with factory() as session, session.begin():
        yield session
