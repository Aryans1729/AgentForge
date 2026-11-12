"""Builders for valid, deterministic synthetic entities. Override any field via kwargs.

Each test states only the field it is breaking; everything else is valid by construction.
All names and emails are synthetic (``example.test`` is a reserved, non-routable domain).
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from enterprisegym.db import AuditEvent, Claim, Customer, Document, Payment, Policy
from enterprisegym.domain.enums import (
    AccountStatus,
    ClaimStatus,
    DocumentType,
    IncidentType,
    PaymentStatus,
    PolicyStatus,
    PolicyType,
    VerificationStatus,
)

FIXED_TIME = datetime(2026, 3, 15, 9, 30, tzinfo=UTC)


def customer(**kw: Any) -> Customer:
    fields: dict[str, Any] = {
        "customer_id": "CUS-0001",
        "name": "Avery Testperson",
        "email": "avery@example.test",
        "account_status": AccountStatus.ACTIVE,
    }
    return Customer(**(fields | kw))


def policy(**kw: Any) -> Policy:
    fields: dict[str, Any] = {
        "policy_id": "POL-0001",
        "customer_id": "CUS-0001",
        "policy_type": PolicyType.AUTO,
        "coverage_amount_cents": 2_000_000,  # $20,000.00
        "deductible_cents": 50_000,  # $500.00
        "start_date": date(2026, 1, 1),
        "expiry_date": date(2026, 12, 31),
        "policy_status": PolicyStatus.ACTIVE,
        "coverage_conditions": {
            "covered_incidents": ["collision", "theft"],
            "required_documents": {"collision": ["police_report", "repair_estimate"]},
        },
    }
    return Policy(**(fields | kw))


def claim(**kw: Any) -> Claim:
    fields: dict[str, Any] = {
        "claim_id": "CLM-1001",
        "customer_id": "CUS-0001",
        "policy_id": "POL-0001",
        "incident_type": IncidentType.COLLISION,
        "incident_date": date(2026, 3, 10),
        "claim_amount_cents": 475_000,
        "claim_status": ClaimStatus.SUBMITTED,
        "assigned_adjuster": None,
    }
    return Claim(**(fields | kw))


def document(**kw: Any) -> Document:
    fields: dict[str, Any] = {
        "document_id": "DOC-0001",
        "claim_id": "CLM-1001",
        "document_type": DocumentType.POLICE_REPORT,
        "verification_status": VerificationStatus.PENDING,
        "uploaded_at": FIXED_TIME,
    }
    return Document(**(fields | kw))


def payment(**kw: Any) -> Payment:
    fields: dict[str, Any] = {
        "payment_id": "PAY-0001",
        "claim_id": "CLM-1001",
        "amount_cents": 425_000,
        "payment_status": PaymentStatus.ISSUED,
    }
    return Payment(**(fields | kw))


def audit_event(**kw: Any) -> AuditEvent:
    fields: dict[str, Any] = {
        "event_id": "EVT-0001",
        "actor": "agent",
        "action": "approve_claim",
        "resource_type": "claim",
        "resource_id": "CLM-1001",
        "timestamp": FIXED_TIME,
        "event_metadata": {"reason": "documents verified"},
    }
    return AuditEvent(**(fields | kw))


def seed_claim_graph(session: Session) -> None:
    """Customer → policy → claim: the minimal valid parent chain for child-entity tests."""
    session.add_all([customer(), policy(), claim()])
    session.flush()
