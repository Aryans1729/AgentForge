"""The database must reject structurally invalid data on BOTH backends.

Why this matters for evaluation: the verifier (M6) trusts the final DB state. If invalid
state could exist at all (a negative payment, a claim on someone else's policy), the
verifier would have to defend against it everywhere. Constraints shrink the space of
states the verifier must reason about.
"""

from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from enterprisegym.db import Claim, Payment
from enterprisegym.domain.enums import VerificationStatus
from factories import (
    FIXED_TIME,
    claim,
    customer,
    document,
    payment,
    policy,
    seed_claim_graph,
)


def assert_rejected(session: Session, *objs: object) -> None:
    session.add_all(objs)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# --- Customer ---------------------------------------------------------------------------


def test_duplicate_email_rejected(session: Session) -> None:
    session.add(customer())
    session.flush()
    assert_rejected(session, customer(customer_id="CUS-0002"))


@pytest.mark.parametrize("email", ["no-at-sign.example.test", "@example.test", "avery@"])
def test_malformed_email_rejected(session: Session, email: str) -> None:
    assert_rejected(session, customer(email=email))


def test_empty_name_rejected(session: Session) -> None:
    assert_rejected(session, customer(name=""))


# --- Policy -----------------------------------------------------------------------------


def test_policy_for_unknown_customer_rejected(session: Session) -> None:
    """Also proves SQLite foreign keys are switched on (they are off by default)."""
    assert_rejected(session, policy(customer_id="CUS-9999"))


@pytest.mark.parametrize("coverage", [0, -1])
def test_non_positive_coverage_rejected(session: Session, coverage: int) -> None:
    assert_rejected(session, customer(), policy(coverage_amount_cents=coverage, deductible_cents=0))


def test_negative_deductible_rejected(session: Session) -> None:
    assert_rejected(session, customer(), policy(deductible_cents=-1))


@pytest.mark.parametrize(
    ("deductible", "accepted"),
    [(1_999_999, True), (2_000_000, False), (2_000_001, False)],  # coverage is 2_000_000
)
def test_deductible_boundary(session: Session, deductible: int, accepted: bool) -> None:
    objs = (customer(), policy(deductible_cents=deductible))
    if accepted:
        session.add_all(objs)
        session.flush()
    else:
        assert_rejected(session, *objs)


@pytest.mark.parametrize(
    ("expiry", "accepted"),
    [(date(2026, 1, 2), True), (date(2026, 1, 1), False), (date(2025, 12, 31), False)],
)
def test_policy_period_boundary(session: Session, expiry: date, accepted: bool) -> None:
    objs = (customer(), policy(start_date=date(2026, 1, 1), expiry_date=expiry))
    if accepted:
        session.add_all(objs)
        session.flush()
    else:
        assert_rejected(session, *objs)


# --- Claim ------------------------------------------------------------------------------


def test_claim_on_another_customers_policy_rejected(session: Session) -> None:
    """The composite FK (policy_id, customer_id) blocks cross-customer claims.

    A single-column FK on policy_id would accept this row, letting a seeded task (or a
    buggy service) produce a claim whose customer and policy holder disagree.
    """
    session.add_all(
        [customer(), customer(customer_id="CUS-0002", email="blake@example.test"), policy()]
    )
    session.flush()
    assert_rejected(session, claim(customer_id="CUS-0002", policy_id="POL-0001"))


def test_claim_on_unknown_policy_rejected(session: Session) -> None:
    session.add(customer())
    session.flush()
    assert_rejected(session, claim(policy_id="POL-9999"))


@pytest.mark.parametrize("amount", [0, -100])
def test_non_positive_claim_amount_rejected(session: Session, amount: int) -> None:
    session.add_all([customer(), policy()])
    session.flush()
    assert_rejected(session, claim(claim_amount_cents=amount))


# --- Document ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "uploaded_at", "accepted"),
    [
        (VerificationStatus.REQUESTED, None, True),
        (VerificationStatus.REQUESTED, FIXED_TIME, False),  # requested docs aren't uploaded
        (VerificationStatus.PENDING, FIXED_TIME, True),
        (VerificationStatus.VERIFIED, None, False),  # cannot verify what was never uploaded
        (VerificationStatus.REJECTED, None, False),
    ],
)
def test_document_upload_state_consistency(
    session: Session, status: VerificationStatus, uploaded_at: object, accepted: bool
) -> None:
    seed_claim_graph(session)
    doc = document(verification_status=status, uploaded_at=uploaded_at)
    if accepted:
        session.add(doc)
        session.flush()
    else:
        assert_rejected(session, doc)


def test_document_for_unknown_claim_rejected(session: Session) -> None:
    assert_rejected(session, document(claim_id="CLM-9999"))


# --- Payment ----------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [0, -1])
def test_non_positive_payment_rejected(session: Session, amount: int) -> None:
    seed_claim_graph(session)
    assert_rejected(session, payment(amount_cents=amount))


def test_payment_for_unknown_claim_rejected(session: Session) -> None:
    assert_rejected(session, payment(claim_id="CLM-9999"))


def test_multiple_payments_per_claim_allowed_at_db_level(session: Session) -> None:
    """Documents a deliberate *non*-constraint.

    Two payments on one claim may be legitimate (instalments) or a duplicate-payment bug.
    Telling them apart needs business context, so the schema allows it and the hidden
    verifier judges it. If someone "fixes" this with a UNIQUE constraint, the
    duplicate-payment tasks become impossible to fail and this test breaks loudly.
    """
    seed_claim_graph(session)
    session.add_all([payment(), payment(payment_id="PAY-0002")])
    session.flush()
    assert session.query(Payment).filter_by(claim_id="CLM-1001").count() == 2


def test_claim_with_payments_cannot_be_deleted(session: Session) -> None:
    """Financial history is never cascaded away: FKs default to NO ACTION."""
    seed_claim_graph(session)
    session.add(payment())
    session.flush()
    with pytest.raises(IntegrityError):
        session.execute(text("DELETE FROM claims WHERE claim_id = 'CLM-1001'"))
    session.rollback()


# --- Enums: two layers of defence -------------------------------------------------------


def test_orm_rejects_unknown_enum_value(session: Session) -> None:
    session.add_all([customer(), policy(), claim(claim_status="teleported")])
    with pytest.raises(StatementError):
        session.flush()
    session.rollback()


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("customers", "account_status"),
        ("claims", "claim_status"),
        ("payments", "payment_status"),
    ],
)
def test_database_rejects_unknown_enum_value_via_raw_sql(
    session: Session, table: str, column: str
) -> None:
    """Even code that bypasses the ORM entirely cannot store an invalid status."""
    seed_claim_graph(session)
    session.add(payment())
    session.flush()
    with pytest.raises(IntegrityError):
        session.execute(text(f"UPDATE {table} SET {column} = 'teleported'"))
    session.rollback()


def test_valid_full_graph_persists(session: Session) -> None:
    seed_claim_graph(session)
    session.add_all([document(), payment()])
    session.commit()
    stored = session.get(Claim, "CLM-1001")
    assert stored is not None
    assert stored.claim_amount_cents == 475_000
