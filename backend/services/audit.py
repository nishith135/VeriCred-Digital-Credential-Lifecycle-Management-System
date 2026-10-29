"""Centralized Immutable Audit Logging Service.

Provides append-only recording of all lifecycle events and multi-criteria
filtering and sequential replay of the system event ledger.
"""

from datetime import datetime, timezone
from typing import Any, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit import AuditEvent
from backend.services.ids import AUDIT_EVENT_SEQUENCE, format_audit_event_id, next_sequence_value


class AuditService:
    """Manages append-only recording and querying of lifecycle audit events."""

    @staticmethod
    async def generate_event_id(db: AsyncSession) -> str:
        """Allocate the next sequential audit event identifier (EVT-00000001)."""
        return format_audit_event_id(await next_sequence_value(db, AUDIT_EVENT_SEQUENCE))

    @classmethod
    async def log_event(
        cls,
        db: AsyncSession,
        event_type: str,
        target_entity_type: str,
        target_entity_id: str,
        actor_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> AuditEvent:
        """Record an append-only audit event in the database."""
        event = AuditEvent(
            event_id=await cls.generate_event_id(db),
            event_type=event_type,
            actor_id=actor_id,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            details=details or {},
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    @classmethod
    async def query_events(
        cls,
        db: AsyncSession,
        event_type: Optional[str] = None,
        actor_id: Optional[str] = None,
        target_entity_type: Optional[str] = None,
        target_entity_id: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[Sequence[AuditEvent], int]:
        """Query audit log events with multi-criteria filtering and pagination.

        Returns:
            Tuple[Sequence[AuditEvent], int]: (events, total_count)
        """
        stmt = select(AuditEvent)
        count_stmt = select(func.count(AuditEvent.id))

        if event_type:
            stmt = stmt.where(AuditEvent.event_type == event_type)
            count_stmt = count_stmt.where(AuditEvent.event_type == event_type)
        if actor_id:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
            count_stmt = count_stmt.where(AuditEvent.actor_id == actor_id)
        if target_entity_type:
            stmt = stmt.where(AuditEvent.target_entity_type == target_entity_type)
            count_stmt = count_stmt.where(AuditEvent.target_entity_type == target_entity_type)
        if target_entity_id:
            stmt = stmt.where(AuditEvent.target_entity_id == target_entity_id)
            count_stmt = count_stmt.where(AuditEvent.target_entity_id == target_entity_id)
        if from_date:
            stmt = stmt.where(AuditEvent.occurred_at >= from_date)
            count_stmt = count_stmt.where(AuditEvent.occurred_at >= from_date)
        if to_date:
            stmt = stmt.where(AuditEvent.occurred_at <= to_date)
            count_stmt = count_stmt.where(AuditEvent.occurred_at <= to_date)

        # Total count
        total = (await db.execute(count_stmt)).scalar() or 0

        # Paginated events ordered sequentially by occurrence
        stmt = stmt.order_by(AuditEvent.occurred_at.asc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        events = result.scalars().all()

        return events, total
