"""Closed vocabularies of the insurance domain.

Stored as strings guarded by CHECK constraints (see ``db.base.str_enum``), so an invalid
value is rejected by the database even if code bypasses the ORM.
"""

from enum import StrEnum


class AccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class PolicyType(StrEnum):
    AUTO = "auto"
    HOME = "home"
    TRAVEL = "travel"


class PolicyStatus(StrEnum):
    """Administrative status. Expiry is *not* a status: it is derived from ``expiry_date`` and
    the simulated business date, so the two can never disagree."""

    ACTIVE = "active"
    LAPSED = "lapsed"  # premiums unpaid
    CANCELLED = "cancelled"


class IncidentType(StrEnum):
    COLLISION = "collision"
    THEFT = "theft"
    FIRE = "fire"
    WATER_DAMAGE = "water_damage"
    VANDALISM = "vandalism"
    NATURAL_DISASTER = "natural_disaster"
    MEDICAL = "medical"
    TRIP_CANCELLATION = "trip_cancellation"
    LOST_BAGGAGE = "lost_baggage"


class ClaimStatus(StrEnum):
    """Allowed transitions between these are enforced in the service layer (Milestone 2)."""

    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    PENDING_DOCUMENTS = "pending_documents"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    CLOSED = "closed"


class DocumentType(StrEnum):
    POLICE_REPORT = "police_report"
    REPAIR_ESTIMATE = "repair_estimate"
    PHOTO_EVIDENCE = "photo_evidence"
    PROOF_OF_OWNERSHIP = "proof_of_ownership"
    MEDICAL_REPORT = "medical_report"
    RECEIPT = "receipt"
    TRAVEL_ITINERARY = "travel_itinerary"
    FIRE_DEPARTMENT_REPORT = "fire_department_report"


class VerificationStatus(StrEnum):
    REQUESTED = "requested"  # asked for, not yet uploaded (uploaded_at is NULL)
    PENDING = "pending"  # uploaded, awaiting verification
    VERIFIED = "verified"
    REJECTED = "rejected"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    ISSUED = "issued"
    FAILED = "failed"
    REVERSED = "reversed"
