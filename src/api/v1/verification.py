"""REST API endpoints for Third-Party Multi-Factor Credential Verification."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.schemas.verification import (
    VerificationQueryRequest,
    VerificationResponse,
)
from src.services.verification import VerificationService

router = APIRouter(prefix="/api/v1/verification", tags=["Verification"])


@router.post(
    "/verify",
    response_model=VerificationResponse,
    summary="Public Credential Verification",
    description="Unauthenticated endpoint verifying credential existence, payload tamper integrity, issuer signature authenticity, and live revocation status.",
)
async def verify_credential(
    query: VerificationQueryRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> VerificationResponse:
    """Publicly verify an academic credential."""
    client_ip = request.client.host if request.client else None
    return await VerificationService.verify_credential(
        db=db,
        credential_public_id=query.credential_public_id,
        presented_payload=query.payload_to_verify,
        requester_ip=client_ip,
    )
