"""ORM model for Learners (Students / Credential Recipients)."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.completion import CompletionRecord


class Learner(Base):
    """Student master record.

    Note: Invariant dictates that identity verification must never rely
    on person name alone; public_id and email are unique identifiers.
    """

    __tablename__ = "learners"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED')",
            name="chk_learner_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )  # e.g., LRN-10001
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
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
    completion_records: Mapped[list["CompletionRecord"]] = relationship(
        "CompletionRecord", back_populates="learner", cascade="all, delete-orphan"
    )
