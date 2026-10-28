"""ORM model for Academic Credential Rules and Eligibility Policies."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.completion import CompletionRecord
    from backend.models.course import Course


class CredentialRule(Base):
    """Academic policy rule governing criteria for credential issuance."""

    __tablename__ = "credential_rules"
    __table_args__ = (
        CheckConstraint(
            "effective_to > effective_from",
            name="chk_rule_dates",
        ),
        CheckConstraint(
            "min_score >= 0.00 AND min_score <= 100.00",
            name="chk_min_score",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rule_version: Mapped[str] = mapped_column(
        String(32), default="1.0", nullable=False
    )
    min_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("80.00"), nullable=False
    )
    required_completion_status: Mapped[str] = mapped_column(
        String(32), default="COMPLETED", nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    effective_to: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    course: Mapped["Course"] = relationship("Course", back_populates="credential_rules")
    completion_records: Mapped[list["CompletionRecord"]] = relationship(
        "CompletionRecord", back_populates="rule"
    )
