"""REST API endpoints for Querying Immutable System Audit Events."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session
from backend.schemas.audit import AuditEventResponse, AuditLogListResponse
from backend.services.audit import AuditService

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


@router.get(
    "/events",
    response_model=AuditLogListResponse,
    summary="Query System Audit Ledger",
    description="Query append-only system audit events with multi-criteria filtering by event type, entity ID, actor, or date range.",
)
async def query_audit_events(
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. CREDENTIAL_ISSUED, CREDENTIAL_REVOKED)"),
    actor_id: Optional[str] = Query(None, description="Filter by initiating actor identifier"),
    target_entity_type: Optional[str] = Query(None, description="Filter by entity type (Credential, CompletionRecord)"),
    target_entity_id: Optional[str] = Query(None, description="Filter by exact entity ID (e.g., CRD-2026-000001)"),
    from_date: Optional[datetime] = Query(None, description="Filter events on or after this timestamp"),
    to_date: Optional[datetime] = Query(None, description="Filter events on or before this timestamp"),
    limit: int = Query(default=100, ge=1, le=1000, description="Page size limit"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db_session),
) -> AuditLogListResponse:
    """Retrieve filtered audit events."""
    events, total = await AuditService.query_events(
        db=db,
        event_type=event_type,
        actor_id=actor_id,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        total=total,
        limit=limit,
        offset=offset,
        events=[AuditEventResponse.model_validate(e) for e in events],
    )
