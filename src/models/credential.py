"""ORM model for Issued Digital Credentials."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.completion import CompletionRecord
    from src.models.issuer import Issuer
    from src.models.revocation import Revocation
    from src.models.verification import VerificationRequest


class Credential(Base):
    """Officially issued academic credential with cryptographic proofs.

    Invariants:
    - Unique completion_id ensures a completion can never receive more than one credential.
    - Canonical payload hash proves data integrity (tamper detection).
    - Issuer signature proves authenticity (origin).
    """

    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'REVOKED')",
            name="chk_cred_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )  # e.g., CRED-2026-00001
    completion_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("completion_records.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    issuer_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("issuers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    canonical_payload_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 hex
    issuer_signature: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Base64-encoded Ed25519 signature
    payload_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    completion: Mapped["CompletionRecord"] = relationship(
        "CompletionRecord", back_populates="credential"
    )
    issuer: Mapped["Issuer"] = relationship("Issuer", back_populates="credentials")
    revocation: Mapped[Optional["Revocation"]] = relationship(
        "Revocation", back_populates="credential", uselist=False
    )
    verification_requests: Mapped[list["VerificationRequest"]] = relationship(
        "VerificationRequest", back_populates="credential"
    )
