"""REST API endpoints for Third-Party Multi-Factor Credential Verification."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session
from backend.core.rate_limit import verify_rate_limiter
from backend.core.rbac import get_current_actor
from backend.schemas.verification import (
    AnyVerificationResponse,
    VerificationQueryRequest,
)
from backend.services.verification import VerificationService

router = APIRouter(prefix="/api/v1/verification", tags=["Verification"])


@router.post(
    "/verify",
    response_model=AnyVerificationResponse,
    response_model_exclude_none=True,
    summary="Public Credential Verification",
    description="Endpoint verifying credential existence, payload tamper integrity, issuer signature authenticity, eligibility, and live revocation status. Redacts PII for public verifier role.",
)
async def verify_credential(
    query: VerificationQueryRequest,
    request: Request,
    actor: dict[str, str] = Depends(get_current_actor),
    _rate_limit: None = Depends(verify_rate_limiter),
    db: AsyncSession = Depends(get_db_session),
) -> AnyVerificationResponse:
    """Verify an academic credential and return role-appropriate response."""
    client_ip = request.client.host if request.client else None
    staff_resp = await VerificationService.verify_credential(
        db=db,
        credential_public_id=query.credential_public_id,
        presented_payload=query.payload_to_verify,
        requester_ip=client_ip,
        actor_id=actor["actor_id"],
    )
    return VerificationService.select_response_for_role(staff_resp, actor["role"])
