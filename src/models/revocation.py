"""ORM model for Credential Revocations."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from src.models.credential import Credential


class Revocation(Base):
    """Historical record of an authorized credential revocation action."""

    __tablename__ = "revocations"
    __table_args__ = (
        CheckConstraint(
            "reason_code IN ('ACADEMIC_MISCONDUCT', 'ADMINISTRATIVE_ERROR', 'RESCINDED', 'OTHER')",
            name="chk_revocation_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credentials.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    revoked_by_actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    revocation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    credential: Mapped["Credential"] = relationship(
        "Credential", back_populates="revocation"
    )
