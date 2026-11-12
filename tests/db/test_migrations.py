"""Alembic migrations must produce exactly the schema the models describe.

Two schema paths exist (ARCHITECTURE.md D5): per-episode databases use
``metadata.create_all`` for speed; the long-lived Postgres DB uses Alembic. These tests
make sure the two can never drift apart.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import CheckConstraint, Engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from enterprisegym.db import Base
from factories import customer, policy

ROOT = Path(__file__).resolve().parents[2]


def _alembic(engine: Engine, *args: str) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False  # keep pytest's log capture intact
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        getattr(command, args[0])(cfg, *args[1:])


@pytest.fixture
def migrated(empty_engine: Engine) -> Iterator[Engine]:
    _alembic(empty_engine, "upgrade", "head")
    yield empty_engine


def test_upgrade_head_has_no_drift_from_models(migrated: Engine) -> None:
    with migrated.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], (
        f"models and migrations disagree; run `alembic revision --autogenerate`: {diff}"
    )


def test_check_constraints_match_models(migrated: Engine) -> None:
    """compare_metadata ignores CHECK constraints, and most of our rules are CHECKs.

    Compare constraint names table by table (including enum CHECKs) instead.
    """
    insp = inspect(migrated)
    for table in Base.metadata.sorted_tables:
        expected = {
            str(c.name) for c in table.constraints if isinstance(c, CheckConstraint) and c.name
        }
        actual = {c["name"] for c in insp.get_check_constraints(table.name)}
        assert actual == expected, (
            f"{table.name}: missing={expected - actual} extra={actual - expected}"
        )


def test_migrated_schema_enforces_constraints(migrated: Engine) -> None:
    with Session(migrated) as s:
        s.add_all([customer(), policy(deductible_cents=2_000_000)])  # deductible == coverage
        with pytest.raises(IntegrityError):
            s.flush()


def test_downgrade_to_base_removes_all_tables(migrated: Engine) -> None:
    _alembic(migrated, "downgrade", "base")
    remaining = set(inspect(migrated).get_table_names()) - {"alembic_version"}
    assert remaining == set()
