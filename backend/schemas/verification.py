"""Pydantic schemas for Third-Party Multi-Factor Credential Verification."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class VerificationQueryRequest(BaseModel):
    """Public query to verify a credential by identifier and optional claims payload."""

    credential_public_id: str = Field(
        ...,
        description="Public credential identifier (e.g., CRD-2026-000001)",
        min_length=5,
        max_length=64,
    )
    payload_to_verify: Optional[dict[str, Any]] = Field(
        None,
        description="Optional full claims payload presented by the holder to detect payload tampering.",
    )


class VerificationFactorResult(BaseModel):
    """Detailed status breakdown of multi-factor verification checks."""

    record_found: bool = Field(..., description="Whether the credential identifier exists in the registry")
    payload_integrity_valid: bool = Field(..., description="Whether canonical SHA-256 digest matches payload")
    issuer_authenticated: bool = Field(..., description="Whether Ed25519 asymmetric signature verified")
    revocation_checked: bool = Field(..., description="Whether live revocation status was evaluated")
    is_revoked: bool = Field(..., description="Whether the credential has been revoked")


class VerificationResponse(BaseModel):
    """Result of third-party multi-factor verification."""

    verification_id: str = Field(..., description="Unique verification attempt audit ID (VER-2026-000001)")
    credential_public_id: str
    outcome: str = Field(..., description="VALID | REVOKED | TAMPERED | NOT_FOUND | INVALID_ISSUANCE")
    reason_code: str
    message: str
    timestamp: datetime
    factors: VerificationFactorResult
    credential_details: Optional[dict[str, Any]] = None
    revocation_details: Optional[dict[str, Any]] = None
