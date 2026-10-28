"""ORM model for Third-Party Verification Requests."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.credential import Credential


class VerificationRequest(Base):
    """Immutable audit entry of an external verification query."""

    __tablename__ = "verification_requests"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('VALID', 'REVOKED', 'TAMPERED', 'NOT_FOUND', 'INVALID_ISSUANCE')",
            name="chk_verif_outcome",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )  # e.g., VRF-00001
    credential_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requested_identifier: Mapped[str] = mapped_column(
        String(128), nullable=False
    )
    verification_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # VALID, REVOKED, TAMPERED, NOT_FOUND, INVALID_ISSUANCE
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    integrity_check_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    issuer_authenticated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requester_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    credential: Mapped[Optional["Credential"]] = relationship(
        "Credential", back_populates="verification_requests"
    )
