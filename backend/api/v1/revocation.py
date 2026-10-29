"""REST API endpoints for Authorized Credential Revocation."""

from typing import Any
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session
from backend.core.rbac import require_role
from backend.models.audit import AuditEvent
from backend.schemas.revocation import RevocationRequest, RevocationResponse
from backend.services.revocation import RevocationService

router = APIRouter(prefix="/api/v1/revocation", tags=["Revocation"])


@router.post(
    "/revoke",
    response_model=RevocationResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Academic Credential",
    description="Authorized endpoint to revoke a credential with reason codes. Historical issuance data is preserved while status transitions to REVOKED.",
)
async def revoke_credential(
    request: RevocationRequest,
    actor: dict[str, str] = Depends(require_role("registrar")),
    db: AsyncSession = Depends(get_db_session),
) -> RevocationResponse:
    """Revoke an active credential."""
    return await RevocationService.revoke_credential(
        db=db,
        credential_public_id=request.credential_public_id,
        actor_id=actor["actor_id"],
        reason_code=request.reason_code,
        notes=request.notes,
    )


@router.get(
    "/audit/{credential_public_id}",
    summary="Get Credential Audit History",
    description="Retrieve all sequential, append-only audit ledger events for a credential.",
)
async def get_credential_audit_history(
    credential_public_id: str,
    _actor: dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve audit events for a credential."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.target_entity_id == credential_public_id)
        .order_by(AuditEvent.occurred_at.asc())
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [
        {
            "event_id": e.event_id,
            "event_type": e.event_type,
            "actor_id": e.actor_id,
            "occurred_at": e.occurred_at.isoformat(),
            "details": e.details,
        }
        for e in events
    ]
