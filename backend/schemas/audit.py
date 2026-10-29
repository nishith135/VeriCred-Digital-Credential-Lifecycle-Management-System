"""Pydantic schemas for System Audit Trail and Event Querying."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    """Structured representation of an immutable audit ledger entry."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str = Field(..., description="Unique event identifier (e.g., EVT-00000001)")
    event_type: str = Field(..., description="Action type: CREDENTIAL_ISSUED, CREDENTIAL_REVOKED, VERIFICATION_PERFORMED, EXCEPTION")
    actor_id: Optional[str] = Field(None, description="Identifier of the system actor or user initiating the action")
    target_entity_type: str = Field(..., description="Type of the target entity: Credential, CompletionRecord, CredentialRule")
    target_entity_id: str = Field(..., description="Identifier of the targeted entity (e.g., CRD-2026-000001)")
    occurred_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class AuditLogListResponse(BaseModel):
    """Paginated list of audit events."""

    total: int
    limit: int
    offset: int
    events: list[AuditEventResponse]
