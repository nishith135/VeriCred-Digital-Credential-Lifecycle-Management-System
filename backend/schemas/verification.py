"""Pydantic schemas for Third-Party Multi-Factor Credential Verification."""

from datetime import datetime
from typing import Any, Optional, Union
from pydantic import BaseModel, Field


def mask_holder_name(full_name: Optional[str]) -> Optional[str]:
    """Mask each token of a learner's name as FirstInitial + '****', e.g. 'A**** Q**** S****'."""
    if not full_name:
        return None
    tokens = [tok.strip(".,") for tok in full_name.split() if tok.strip(".,")]
    if not tokens:
        return None
    return " ".join(f"{tok[0]}****" for tok in tokens)


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
    payload_hash_matches: bool = Field(..., description="Whether canonical SHA-256 digest and relational cross-check match payload")
    issuer_authenticated: bool = Field(..., description="Whether Ed25519 asymmetric signature verified")
    eligibility_valid: bool = Field(
        default=True,
        description="Whether completion eligibility rules and issuance timestamp chronology are satisfied",
    )
    revocation_checked: bool = Field(..., description="Whether live revocation status was evaluated")
    is_revoked: bool = Field(..., description="Whether the credential has been revoked")
    failed_subchecks: list[str] = Field(
        default_factory=list,
        description="Specific sub-checks that failed during verification (e.g., PREMATURE_ISSUANCE_TIMESTAMP, BELOW_MIN_SCORE)",
    )


class PublicVerificationResponse(BaseModel):
    """Redacted public verification response for the Public Verifier role."""

    credential_public_id: str
    outcome: str = Field(..., description="VALID | REVOKED | TAMPERED | NOT_FOUND | INVALID_ISSUANCE")
    issuer_name: Optional[str] = None
    course_title: Optional[str] = None
    issued_at: Optional[str] = None
    holder_masked: Optional[str] = None
    factors: VerificationFactorResult
    revoked_at: Optional[str] = None
    reason_code: Optional[str] = None


class StaffVerificationResponse(BaseModel):
    """Full staff verification response for University Registrar and Compliance Auditor roles."""

    verification_id: str = Field(..., description="Unique verification attempt audit ID (VER-2026-000001)")
    credential_public_id: str
    outcome: str = Field(..., description="VALID | REVOKED | TAMPERED | NOT_FOUND | INVALID_ISSUANCE")
    reason_code: str
    message: str
    timestamp: datetime
    factors: VerificationFactorResult
    credential_details: Optional[dict[str, Any]] = None
    revocation_details: Optional[dict[str, Any]] = None

    def to_public_response(self) -> PublicVerificationResponse:
        """Convert full staff response to a PII-redacted PublicVerificationResponse."""
        issuer_name: Optional[str] = None
        course_title: Optional[str] = None
        issued_at: Optional[str] = None
        holder_masked: Optional[str] = None

        if self.credential_details:
            issuer_name = self.credential_details.get("issuer_name")
            issued_at = self.credential_details.get("issued_at")
            snap = self.credential_details.get("payload_snapshot") or {}
            course_info = snap.get("course") or {}
            learner_info = snap.get("learner") or {}
            course_title = course_info.get("title")
            holder_masked = mask_holder_name(learner_info.get("name"))

        revoked_at: Optional[str] = None
        rev_reason_code: Optional[str] = None
        if self.revocation_details:
            revoked_at = self.revocation_details.get("revocation_timestamp")
            rev_reason_code = self.revocation_details.get("reason_code")
        elif self.outcome == "REVOKED":
            rev_reason_code = self.reason_code

        return PublicVerificationResponse(
            credential_public_id=self.credential_public_id,
            outcome=self.outcome,
            issuer_name=issuer_name,
            course_title=course_title,
            issued_at=issued_at,
            holder_masked=holder_masked,
            factors=self.factors,
            revoked_at=revoked_at,
            reason_code=rev_reason_code,
        )


# Backward-compatible alias for internal callers
VerificationResponse = StaffVerificationResponse
AnyVerificationResponse = Union[PublicVerificationResponse, StaffVerificationResponse]
