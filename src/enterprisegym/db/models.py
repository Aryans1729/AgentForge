"""The six persistent entities of the simulated insurance company.

Conventions
-----------
* Primary keys are human-readable strings (``CUS-0001``, ``CLM-1001``) assigned by the seed
  loader or by a per-episode counter, never random UUIDs. Deterministic IDs make
  trajectories, verifier output and reruns comparable byte-for-byte.
* Money is stored as integer **cents** in columns suffixed ``_cents``. The unit lives in
  the name so nobody ever has to guess.
* The database enforces only *structural* truths that hold for every task (positive
  amounts, valid periods, referential integrity). Workflow rules (status transitions,
  authority limits) live in the service layer; judgement-based policies (duplicate
  detection, audit notes) are checked by the hidden verifier. See ARCHITECTURE.md D1.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enterprisegym.db.base import Base, UTCDateTime, str_enum
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

ID = String(32)


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(ID, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    account_status: Mapped[AccountStatus] = mapped_column(str_enum(AccountStatus, "account_status"))

    policies: Mapped[list["Policy"]] = relationship(back_populates="customer")
    claims: Mapped[list["Claim"]] = relationship(back_populates="customer", overlaps="claims")

    __table_args__ = (
        CheckConstraint("length(name) > 0", name="name_not_empty"),
        CheckConstraint("email LIKE '%_@_%'", name="email_format"),
    )


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(ID, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    policy_type: Mapped[PolicyType] = mapped_column(str_enum(PolicyType, "policy_type"))
    coverage_amount_cents: Mapped[int] = mapped_column(BigInteger)
    deductible_cents: Mapped[int] = mapped_column(BigInteger)
    start_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date)
    policy_status: Mapped[PolicyStatus] = mapped_column(str_enum(PolicyStatus, "policy_status"))
    # Structure (covered incidents, exclusions, required documents) is validated by a
    # Pydantic model in the service layer (M2). JSON keeps the schema stable while
    # coverage rules evolve with the task dataset.
    coverage_conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    customer: Mapped[Customer] = relationship(back_populates="policies")
    claims: Mapped[list["Claim"]] = relationship(back_populates="policy", overlaps="claims")

    __table_args__ = (
        CheckConstraint("coverage_amount_cents > 0", name="coverage_positive"),
        CheckConstraint("deductible_cents >= 0", name="deductible_non_negative"),
        CheckConstraint(
            "deductible_cents < coverage_amount_cents", name="deductible_below_coverage"
        ),
        CheckConstraint("expiry_date > start_date", name="valid_period"),
        # Target of the composite FK on claims (see Claim.__table_args__).
        UniqueConstraint("policy_id", "customer_id"),
    )


class Claim(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(ID, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    policy_id: Mapped[str] = mapped_column(ID, index=True)
    incident_type: Mapped[IncidentType] = mapped_column(str_enum(IncidentType, "incident_type"))
    incident_date: Mapped[date] = mapped_column(Date)
    claim_amount_cents: Mapped[int] = mapped_column(BigInteger)
    claim_status: Mapped[ClaimStatus] = mapped_column(
        str_enum(ClaimStatus, "claim_status"), index=True
    )
    assigned_adjuster: Mapped[str | None] = mapped_column(String(64))

    customer: Mapped[Customer] = relationship(back_populates="claims", overlaps="claims")
    policy: Mapped[Policy] = relationship(
        back_populates="claims",
        foreign_keys=[policy_id, customer_id],
        overlaps="claims,customer",
    )
    documents: Mapped[list["Document"]] = relationship(back_populates="claim")
    payments: Mapped[list["Payment"]] = relationship(back_populates="claim")

    __table_args__ = (
        # Composite FK: a claim's policy must belong to the *same* customer. A plain FK on
        # policy_id would happily accept customer A claiming on customer B's policy.
        ForeignKeyConstraint(
            ["policy_id", "customer_id"], ["policies.policy_id", "policies.customer_id"]
        ),
        CheckConstraint("claim_amount_cents > 0", name="amount_positive"),
    )


class Document(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(ID, primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), index=True)
    document_type: Mapped[DocumentType] = mapped_column(str_enum(DocumentType, "document_type"))
    verification_status: Mapped[VerificationStatus] = mapped_column(
        str_enum(VerificationStatus, "verification_status")
    )
    # NULL means "requested but not yet uploaded". A missing document is modelled as a
    # row, so "which documents are missing?" is a query, not an inference.
    uploaded_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    claim: Mapped[Claim] = relationship(back_populates="documents")

    __table_args__ = (
        CheckConstraint(
            "(verification_status = 'requested' AND uploaded_at IS NULL)"
            " OR (verification_status <> 'requested' AND uploaded_at IS NOT NULL)",
            name="uploaded_at_matches_status",
        ),
    )


class Payment(Base):
    __tablename__ = "payments"

    payment_id: Mapped[str] = mapped_column(ID, primary_key=True)
    # Deliberately NOT unique: a claim may legitimately receive several payments
    # (instalments, supplements). Whether a second payment is a *duplicate* is a business
    # judgement, so it is graded by the verifier, not blocked by the schema.
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.claim_id"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    payment_status: Mapped[PaymentStatus] = mapped_column(str_enum(PaymentStatus, "payment_status"))

    claim: Mapped[Claim] = relationship(back_populates="payments")

    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)


class AuditEvent(Base):
    """Append-only log of who did what. Append-only is enforced in the service layer (M2).

    ``resource_id`` is intentionally not a foreign key: one table audits five resource
    types (polymorphic reference). The trade-off is that the DB cannot prove the resource
    exists; the verifier checks that instead.
    """

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(ID, primary_key=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str] = mapped_column(ID)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    # "metadata" is reserved on SQLAlchemy declarative classes (it is the table registry),
    # so the Python attribute is renamed while the column keeps the specified name.
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    __table_args__ = (
        CheckConstraint("length(actor) > 0", name="actor_not_empty"),
        CheckConstraint("length(action) > 0", name="action_not_empty"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
    )
