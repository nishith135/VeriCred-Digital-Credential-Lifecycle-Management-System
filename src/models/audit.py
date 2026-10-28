"""ORM model for Immutable System Audit Events."""

from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class AuditEvent(Base):
    """Append-only audit ledger recording lifecycle actions and security events."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )  # e.g., EVT-00001
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # CREDENTIAL_ISSUED, CREDENTIAL_REVOKED, VERIFICATION_PERFORMED, EXCEPTION
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_entity_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )  # Credential, CompletionRecord, CredentialRule
    target_entity_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
