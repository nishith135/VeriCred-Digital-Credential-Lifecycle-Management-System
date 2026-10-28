"""ORM model for Academic Courses and Curriculum Modules."""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base

if TYPE_CHECKING:
    from backend.models.completion import CompletionRecord
    from backend.models.credential_rule import CredentialRule


class Course(Base):
    """Academic course or curriculum subject definition."""

    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')",
            name="chk_course_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )  # e.g., CRS-10001
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    credential_rules: Mapped[list["CredentialRule"]] = relationship(
        "CredentialRule", back_populates="course", cascade="all, delete-orphan"
    )
    completion_records: Mapped[list["CompletionRecord"]] = relationship(
        "CompletionRecord", back_populates="course", cascade="all, delete-orphan"
    )
