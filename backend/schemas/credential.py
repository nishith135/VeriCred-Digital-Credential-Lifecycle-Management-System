"""Pydantic schemas for Credential issuance and eligibility evaluation."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class EligibilityEvaluationRequest(BaseModel):
    """Request payload to evaluate eligibility for a completion record."""

    completion_id: int = Field(..., description="ID of the completion record to evaluate")


class EligibilityEvaluationResult(BaseModel):
    """Result of an academic eligibility check."""

    is_eligible: bool
    completion_id: int
    learner_public_id: str
    learner_name: str
    course_public_id: str
    course_title: str
    assessment_score: Decimal
    required_min_score: Decimal
    completion_status: str
    already_issued: bool
    reasons: list[str] = Field(default_factory=list)


class CredentialIssuanceRequest(BaseModel):
    """Request to atomically issue an authentic academic credential."""

    completion_id: int = Field(..., description="ID of the eligible completion record")
    issuer_public_id: str = Field(..., description="Public identifier of the issuing authority")
    actor_id: Optional[str] = Field(None, description="Identifier of the administrator or system actor executing issuance")


class CredentialResponse(BaseModel):
    """Full representation of an issued digital credential."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    completion_id: int
    issuer_id: int
    issued_at: datetime
    canonical_payload_hash: str
    issuer_signature: str
    payload_snapshot: dict[str, Any]
    status: str
    created_at: datetime


class IssuerCreate(BaseModel):
    """Schema for registering a new issuing authority."""

    name: str = Field(..., min_length=2, max_length=255)
    public_id: Optional[str] = None
    public_key_pem: Optional[str] = None


class IssuerResponse(BaseModel):
    """Schema for returning issuer details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    name: str
    public_key_pem: str
    status: str
    created_at: datetime


class LearnerCreate(BaseModel):
    """Schema for creating a learner."""

    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=5, max_length=255)
    public_id: Optional[str] = None


class LearnerResponse(BaseModel):
    """Schema for returning learner details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    full_name: str
    email: str
    status: str
    created_at: datetime


class CourseCreate(BaseModel):
    """Schema for registering a course."""

    title: str = Field(..., min_length=1, max_length=255)
    public_id: Optional[str] = None
    version: str = "1.0"


class CourseResponse(BaseModel):
    """Schema for returning course details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    title: str
    version: str
    status: str
    created_at: datetime


class CompletionRecordCreate(BaseModel):
    """Schema for submitting course completion evidence."""

    learner_id: int
    course_id: int
    rule_id: int
    assessment_score: Decimal = Field(..., ge=0.00, le=100.00)
    status: str = Field(default="COMPLETED")
    completion_timestamp: Optional[datetime] = None


class CompletionRecordResponse(BaseModel):
    """Schema for returning completion record details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    learner_id: int
    course_id: int
    rule_id: int
    assessment_score: Decimal
    status: str
    completion_timestamp: datetime
    created_at: datetime
