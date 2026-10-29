"""ORM model for Academic Course Completion Records."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
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
    from backend.models.course import Course
    from backend.models.credential import Credential
    from backend.models.credential_rule import CredentialRule
    from backend.models.learner import Learner


class CompletionRecord(Base):
    """Evidence record of a learner attempting/completing a course curriculum."""

    __tablename__ = "completion_records"
    __table_args__ = (
        CheckConstraint(
            "assessment_score >= 0.00 AND assessment_score <= 100.00",
            name="chk_assessment_score",
        ),
        CheckConstraint(
            "status IN ('COMPLETED', 'IN_PROGRESS', 'FAILED')",
            name="chk_completion_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )  # e.g., CMP-LRN-000001-CRS-000001
    learner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("learners.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("credential_rules.id", ondelete="RESTRICT"), nullable=False
    )
    assessment_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    completion_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    learner: Mapped["Learner"] = relationship("Learner", back_populates="completion_records")
    course: Mapped["Course"] = relationship("Course", back_populates="completion_records")
    rule: Mapped["CredentialRule"] = relationship(
        "CredentialRule", back_populates="completion_records"
    )
    credential: Mapped[Optional["Credential"]] = relationship(
        "Credential", back_populates="completion", uselist=False
    )
