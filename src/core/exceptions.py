"""Core domain exceptions and structured HTTP error responses.

Defines custom exception classes representing non-negotiable business rule
violations and error response formatters for FastAPI.
"""

from typing import Any, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class DomainException(Exception):
    """Base domain exception with status code and error details."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_DOMAIN_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class DuplicateIssuanceError(DomainException):
    """Raised when an attempt is made to issue a credential for an already issued completion."""

    def __init__(
        self,
        message: str = "Credential has already been issued for this completion record.",
        completion_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            code="DUPLICATE_ISSUANCE_REJECTED",
            status_code=status.HTTP_409_CONFLICT,
            details={"completion_id": completion_id} if completion_id else {},
        )


class IneligibleIssuanceError(DomainException):
    """Raised when a learner completion does not satisfy minimum passing rules."""

    def __init__(
        self,
        message: str = "Completion does not satisfy minimum eligibility requirements.",
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        det = details or {}
        if reason:
            det["reason"] = reason
        super().__init__(
            message=message,
            code="ELIGIBILITY_REQUIREMENTS_NOT_MET",
            status_code=422,
            details=det,
        )


class CredentialNotFoundError(DomainException):
    """Raised when a requested credential cannot be found by identifier."""

    def __init__(
        self,
        message: str = "Credential not found.",
        credential_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            code="CREDENTIAL_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"credential_id": credential_id} if credential_id else {},
        )


class TamperedPayloadError(DomainException):
    """Raised when payload integrity check fails (canonical SHA-256 mismatch)."""

    def __init__(
        self,
        message: str = "Payload integrity check failed: digest mismatch detected.",
        expected_hash: Optional[str] = None,
        computed_hash: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            code="PAYLOAD_TAMPERING_DETECTED",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "expected_hash": expected_hash,
                "computed_hash": computed_hash,
            },
        )


class RevocationError(DomainException):
    """Raised when an invalid revocation operation is performed."""

    def __init__(
        self,
        message: str = "Credential revocation failed.",
        credential_id: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            code="REVOCATION_OPERATION_FAILED",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={
                "credential_id": credential_id,
                "reason": reason,
            },
        )


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    """Global FastAPI exception handler converting DomainException into structured JSON."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
        },
    )
