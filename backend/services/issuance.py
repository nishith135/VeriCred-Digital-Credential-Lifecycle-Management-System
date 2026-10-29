"""Atomic Credential Issuance Service.

Coordinates eligibility evaluation, canonical payload freezing,
SHA-256 hashing, Ed25519 asymmetric signing, database persistence,
and immutable audit event creation in a single atomic transaction.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import backend.core.database as db_module
from backend.core.exceptions import (
    DomainException,
    DuplicateIssuanceError,
    IneligibleIssuanceError,
)
from backend.core.security import compute_payload_hash, sign_payload_hash
from backend.models.audit import AuditEvent
from backend.models.credential import Credential
from backend.models.issuer import Issuer
from backend.schemas.credential import CredentialResponse
from backend.services.audit import AuditService
from backend.services.eligibility import EligibilityService
from backend.services.ids import CREDENTIAL_SEQUENCE, format_credential_id, next_sequence_value
from backend.services.payloads import build_credential_payload


class IssuanceService:
    """Handles secure, tamper-evident credential issuance."""

    @staticmethod
    async def generate_credential_public_id(db: AsyncSession, issued_at: datetime | None = None) -> str:
        """Allocate the next sequential credential identifier (CRD-2026-000001)."""
        number = await next_sequence_value(db, CREDENTIAL_SEQUENCE)
        return format_credential_id(number, issued_at)

    @classmethod
    async def issue_credential(
        cls,
        db: AsyncSession,
        completion_id: int,
        issuer_public_id: str,
        issuer_private_key_pem: str,
        actor_id: Optional[str] = None,
    ) -> CredentialResponse:
        """Atomically issue an academic credential for an eligible completion.

        Args:
            db: Database session.
            completion_id: Primary key of the completion record.
            issuer_public_id: Public ID of the issuing institution.
            issuer_private_key_pem: Issuer's Ed25519 private key (never stored in DB).
            actor_id: Optional ID of the administrator/user initiating issuance.

        Returns:
            CredentialResponse: Full representation of the issued credential.

        Raises:
            DuplicateIssuanceError: If a credential was already issued for this completion.
            IneligibleIssuanceError: If eligibility rules are not satisfied.
            DomainException: If issuer not found or inactive.
        """
        # 1. Eligibility evaluation
        evaluation = await EligibilityService.evaluate_eligibility(db, completion_id)
        if evaluation.already_issued:
            raise DuplicateIssuanceError(completion_id=str(completion_id))
        if not evaluation.is_eligible:
            await db.rollback()
            async with db_module.async_session_factory() as audit_db:
                await AuditService.log_event(
                    db=audit_db,
                    event_type="ELIGIBILITY_CHECK_FAILED",
                    target_entity_type="CompletionRecord",
                    target_entity_id=evaluation.completion_public_id or str(completion_id),
                    actor_id=actor_id or issuer_public_id,
                    details={
                        "completion_id": completion_id,
                        "completion_public_id": evaluation.completion_public_id,
                        "learner_public_id": evaluation.learner_public_id,
                        "course_public_id": evaluation.course_public_id,
                        "issuer_public_id": issuer_public_id,
                        "assessment_score": float(evaluation.assessment_score),
                        "required_min_score": float(evaluation.required_min_score),
                        "completion_status": evaluation.completion_status,
                        "failed_subchecks": evaluation.failed_subchecks,
                        "reasons": evaluation.reasons,
                    },
                )
            raise IneligibleIssuanceError(
                message=f"Learner is not eligible for credential issuance: {'; '.join(evaluation.reasons)}",
                details={
                    "reasons": evaluation.reasons,
                    "failed_subchecks": evaluation.failed_subchecks,
                    "completion_id": completion_id,
                },
            )

        # 2. Issuer lookup and validation
        stmt_issuer = select(Issuer).where(Issuer.public_id == issuer_public_id)
        res_issuer = await db.execute(stmt_issuer)
        issuer = res_issuer.scalar_one_or_none()
        if not issuer:
            raise DomainException(
                f"Issuer with ID '{issuer_public_id}' not found.",
                code="ISSUER_NOT_FOUND",
                status_code=404,
            )
        if issuer.status != "ACTIVE":
            raise DomainException(
                f"Issuer '{issuer.name}' is not in ACTIVE status (current: {issuer.status}).",
                code="ISSUER_INACTIVE",
                status_code=400,
            )

        # 3. Fetch completion details for frozen payload
        completion = await EligibilityService.get_completion_with_relations(db, completion_id)
        if not completion:
            raise DomainException("Completion record missing", code="COMPLETION_NOT_FOUND", status_code=404)

        # 4. Construct canonical snapshot payload
        issued_at = datetime.now(timezone.utc)
        credential_public_id = await cls.generate_credential_public_id(db, issued_at)

        payload_snapshot = build_credential_payload(
            credential_id=credential_public_id,
            issued_at=issued_at,
            completion_timestamp=completion.completion_timestamp,
            learner_id=completion.learner.public_id,
            learner_name=completion.learner.full_name,
            learner_email=completion.learner.email,
            course_code=completion.course.public_id,
            course_title=completion.course.title,
            assessment_score=completion.assessment_score,
            assessment_status=completion.status,
            issuer_id=issuer.public_id,
            issuer_name=issuer.name,
        )

        # 5. Compute cryptographic digest and signature
        payload_hash = compute_payload_hash(payload_snapshot)
        signature = sign_payload_hash(issuer_private_key_pem, payload_hash)

        # 6. Instantiate ORM models
        credential = Credential(
            public_id=credential_public_id,
            completion_id=completion.id,
            issuer_id=issuer.id,
            issued_at=issued_at,
            canonical_payload_hash=payload_hash,
            issuer_signature=signature,
            payload_snapshot=payload_snapshot,
            status="ACTIVE",
        )

        event_id = await AuditService.generate_event_id(db)
        audit_event = AuditEvent(
            event_id=event_id,
            event_type="CREDENTIAL_ISSUED",
            actor_id=actor_id or issuer_public_id,
            target_entity_type="Credential",
            target_entity_id=credential_public_id,
            occurred_at=issued_at,
            details={
                "completion_id": completion.id,
                "learner_id": completion.learner.public_id,
                "course_id": completion.course.public_id,
                "score": float(completion.assessment_score),
                "payload_hash": payload_hash,
            },
        )

        # 7. Atomic DB Commit
        try:
            db.add(credential)
            db.add(audit_event)
            await db.commit()
            await db.refresh(credential)
        except IntegrityError as exc:
            await db.rollback()
            raise DuplicateIssuanceError(completion_id=str(completion_id)) from exc
        except Exception:
            await db.rollback()
            raise

        return CredentialResponse.model_validate(credential)
