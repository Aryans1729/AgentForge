"""Alembic environment.

Connection resolution order:
1. ``config.attributes["connection"]``: an open connection passed in programmatically
   (tests use this so in-memory SQLite and the _test Postgres DB both work).
2. ``EG_DATABASE_URL`` via enterprisegym settings (CLI usage).
"""

from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy.engine import Connection

from enterprisegym.db import Base
from enterprisegym.db.base import UTCDateTime
from enterprisegym.db.session import make_engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | bool:
    """Render app-level TypeDecorators as their plain DB type in generated migrations.

    Migrations are frozen history: they must not import application types, or changing
    the app code would silently change what an old migration means.
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False  # default rendering


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_item=render_item,
        # SQLite cannot ALTER most constraints in place; batch mode recreates the table.
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine = make_engine()
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (SQL script) migrations are not supported; use online mode.")
run_migrations_online()
