"""Pydantic schemas for Credential Revocation."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

RevocationReasonCode = Literal[
    "ACADEMIC_MISCONDUCT",
    "ADMINISTRATIVE_ERROR",
    "RESCINDED",
    "OTHER",
]


class RevocationRequest(BaseModel):
    """Administrative request to revoke an active credential."""

    credential_public_id: str = Field(..., description="Public ID of the credential to revoke")
    actor_id: str = Field(..., description="ID of the authorized administrator or faculty member")
    reason_code: RevocationReasonCode = Field(
        ...,
        description="Standardized reason code: ACADEMIC_MISCONDUCT, ADMINISTRATIVE_ERROR, RESCINDED, OTHER",
    )
    notes: Optional[str] = Field(None, description="Detailed explanatory notes or administrative record reference")


class RevocationResponse(BaseModel):
    """Result of an authorized revocation action."""

    credential_public_id: str
    status: str = Field("REVOKED")
    reason_code: str
    revoked_by_actor_id: str
    revocation_timestamp: datetime
    notes: Optional[str] = None
    audit_event_id: str
