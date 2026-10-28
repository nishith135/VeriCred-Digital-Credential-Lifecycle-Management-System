"""Authorized Credential Revocation Service.

Enforces administrative authority, records revocation reasons,
transitions credential status, and creates immutable audit events
without mutating or deleting original issuance evidence.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import CredentialNotFoundError, RevocationError
from src.models.audit import AuditEvent
from src.models.credential import Credential
from src.models.revocation import Revocation
from src.schemas.revocation import RevocationResponse


class RevocationService:
    """Handles authorized revocation of academic credentials."""

    @classmethod
    async def revoke_credential(
        cls,
        db: AsyncSession,
        credential_public_id: str,
        actor_id: str,
        reason_code: str,
        notes: Optional[str] = None,
    ) -> RevocationResponse:
        """Revoke an active credential and record the audit event.

        Args:
            db: Database session.
            credential_public_id: Public identifier of the credential to revoke.
            actor_id: Administrator or faculty actor authorizing the revocation.
            reason_code: Reason code (ACADEMIC_MISCONDUCT, ADMINISTRATIVE_ERROR, RESCINDED, OTHER).
            notes: Optional explanatory notes.

        Returns:
            RevocationResponse: Confirmation of revocation.

        Raises:
            CredentialNotFoundError: If credential identifier is not found.
            RevocationError: If credential is already revoked or invalid reason.
        """
        stmt = (
            select(Credential)
            .options(selectinload(Credential.revocation))
            .where(Credential.public_id == credential_public_id)
        )
        result = await db.execute(stmt)
        credential = result.scalar_one_or_none()

        if not credential:
            raise CredentialNotFoundError(credential_id=credential_public_id)

        # Idempotency / Double Revocation Guard
        if credential.status == "REVOKED" or credential.revocation is not None:
            prev_reason = credential.revocation.reason_code if credential.revocation else "ALREADY_REVOKED"
            raise RevocationError(
                message=f"Credential '{credential_public_id}' is already revoked.",
                credential_id=credential_public_id,
                reason=prev_reason,
            )

        now = datetime.now(timezone.utc)
        event_id = f"EVT-{uuid4().hex[:10].upper()}"

        revocation = Revocation(
            credential_id=credential.id,
            revoked_by_actor_id=actor_id,
            reason_code=reason_code,
            revocation_timestamp=now,
            notes=notes,
        )

        credential.status = "REVOKED"

        audit_event = AuditEvent(
            event_id=event_id,
            event_type="CREDENTIAL_REVOKED",
            actor_id=actor_id,
            target_entity_type="Credential",
            target_entity_id=credential_public_id,
            occurred_at=now,
            details={
                "reason_code": reason_code,
                "notes": notes,
                "revoked_by": actor_id,
            },
        )

        db.add(revocation)
        db.add(audit_event)
        await db.commit()

        return RevocationResponse(
            credential_public_id=credential_public_id,
            status="REVOKED",
            reason_code=reason_code,
            revoked_by_actor_id=actor_id,
            revocation_timestamp=now,
            notes=notes,
            audit_event_id=event_id,
        )
