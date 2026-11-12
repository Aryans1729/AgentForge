"""Declarative base, constraint naming convention and portable column types."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Dialect, MetaData
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

# Deterministic constraint names. Alembic needs names to drop/alter constraints later, and
# stable names make IntegrityError messages identifiable in tests and error mapping (M2).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """A VARCHAR column + CHECK constraint holding the enum's *values*.

    Chosen over native Postgres ENUM types: identical behaviour on SQLite and Postgres,
    and adding a value later is a simple constraint change instead of ``ALTER TYPE``.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=32,
        values_callable=lambda e: [member.value for member in e],
    )


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware UTC datetimes on every backend.

    Postgres keeps timezones; SQLite silently drops them. Without this type, the same
    episode would produce aware datetimes on one backend and naive ones on the other,
    and comparing them raises ``TypeError``, a classic source of flaky graders.
    Naive datetimes are rejected on write so ambiguity never enters the DB.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"naive datetime not allowed: {value!r}")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:  # SQLite: stored as UTC, returned naive
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
