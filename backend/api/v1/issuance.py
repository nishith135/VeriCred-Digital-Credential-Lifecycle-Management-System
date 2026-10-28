"""REST API endpoints for Academic Eligibility Evaluation and Credential Issuance."""

from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session
from backend.core.exceptions import DomainException
from backend.schemas.credential import (
    CredentialIssuanceRequest,
    CredentialResponse,
    EligibilityEvaluationRequest,
    EligibilityEvaluationResult,
)
from backend.services.eligibility import EligibilityService
from backend.services.issuance import IssuanceService

router = APIRouter(prefix="/api/v1/issuance", tags=["Issuance"])


@router.post(
    "/evaluate",
    response_model=EligibilityEvaluationResult,
    summary="Evaluate Academic Eligibility",
    description="Evaluates a learner completion record against active course credential rules without issuing a credential.",
)
async def evaluate_eligibility(
    request: EligibilityEvaluationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> EligibilityEvaluationResult:
    """Evaluate completion record for credential eligibility."""
    return await EligibilityService.evaluate_eligibility(db, request.completion_id)


@router.post(
    "/issue",
    response_model=CredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Atomically Issue Credential",
    description="Validates eligibility, builds canonical claims snapshot, computes SHA-256 digest and Ed25519 signature, and atomically commits the credential.",
)
async def issue_credential(
    request: CredentialIssuanceRequest,
    x_issuer_private_key: Optional[str] = Header(
        None,
        description="PEM-encoded Ed25519 private key used to sign the credential hash.",
    ),
    db: AsyncSession = Depends(get_db_session),
) -> CredentialResponse:
    """Atomically issue authentic credential."""
    if not x_issuer_private_key:
        raise DomainException(
            "Issuer private key must be supplied in X-Issuer-Private-Key header for cryptographic signing.",
            code="MISSING_ISSUER_KEY",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return await IssuanceService.issue_credential(
        db=db,
        completion_id=request.completion_id,
        issuer_public_id=request.issuer_public_id,
        issuer_private_key_pem=x_issuer_private_key,
        actor_id=request.actor_id,
    )
