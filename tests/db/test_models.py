"""Round-trip behaviour: relationships, JSON columns and timezone handling."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from enterprisegym.db import AuditEvent, Claim, Customer, Policy
from enterprisegym.domain.enums import ClaimStatus
from factories import FIXED_TIME, audit_event, document, payment, seed_claim_graph


def test_relationships_navigate_both_ways(engine: Engine) -> None:
    with Session(engine) as s:
        seed_claim_graph(s)
        s.add_all([document(), payment()])
        s.commit()

    with Session(engine) as s:  # fresh session: nothing served from the identity map
        cust = s.get(Customer, "CUS-0001")
        assert cust is not None
        assert [p.policy_id for p in cust.policies] == ["POL-0001"]
        assert [c.claim_id for c in cust.claims] == ["CLM-1001"]
        clm = s.get(Claim, "CLM-1001")
        assert clm is not None
        assert clm.policy.customer_id == clm.customer_id
        assert [d.document_id for d in clm.documents] == ["DOC-0001"]
        assert [p.amount_cents for p in clm.payments] == [425_000]


def test_enum_columns_round_trip_as_enum_members(engine: Engine) -> None:
    with Session(engine) as s:
        seed_claim_graph(s)
        s.commit()
    with Session(engine) as s:
        status = s.scalar(select(Claim.claim_status))
        assert status is ClaimStatus.SUBMITTED


def test_coverage_conditions_json_round_trip(engine: Engine) -> None:
    with Session(engine) as s:
        seed_claim_graph(s)
        s.commit()
    with Session(engine) as s:
        pol = s.get(Policy, "POL-0001")
        assert pol is not None
        assert pol.coverage_conditions["required_documents"]["collision"] == [
            "police_report",
            "repair_estimate",
        ]


def test_audit_metadata_column_keeps_spec_name(engine: Engine) -> None:
    assert "metadata" in AuditEvent.__table__.c
    with Session(engine) as s:
        s.add(audit_event())
        s.commit()
    with Session(engine) as s:
        evt = s.get(AuditEvent, "EVT-0001")
        assert evt is not None
        assert evt.event_metadata == {"reason": "documents verified"}


def test_timestamps_round_trip_as_aware_utc(engine: Engine) -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    with Session(engine) as s:
        s.add(audit_event(timestamp=datetime(2026, 3, 15, 15, 0, tzinfo=ist)))
        s.commit()
    with Session(engine) as s:
        evt = s.get(AuditEvent, "EVT-0001")
        assert evt is not None
        assert evt.timestamp == datetime(2026, 3, 15, 9, 30, tzinfo=UTC)
        assert evt.timestamp.tzinfo is UTC
        assert evt.timestamp == FIXED_TIME  # comparable with aware values, no TypeError


def test_naive_timestamps_rejected(session: Session) -> None:
    session.add(audit_event(timestamp=datetime(2026, 3, 15, 9, 30)))
    with pytest.raises(StatementError, match="naive datetime"):
        session.flush()
    session.rollback()
