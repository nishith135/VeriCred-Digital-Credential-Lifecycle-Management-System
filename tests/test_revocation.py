"""Tests for Authorized Credential Revocation with Live Reflection.

Verifies:
- Authorized revocation transitions status to REVOKED without deleting history.
- Creation of Revocation table record and AuditEvent log.
- Re-revocation guard (idempotency / RevocationError).
- Live reflection in verification service (VALID -> REVOKED).
- Sequential audit trail retrieval via REST API.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import CredentialNotFoundError, RevocationError
from backend.models import CompletionRecord, Revocation
from backend.services.ids import format_completion_id
from backend.services.issuance import IssuanceService
from backend.services.revocation import RevocationService
from backend.services.verification import VerificationService


@pytest.mark.asyncio
async def test_authorized_revocation_success_and_audit(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that revoking a credential creates a Revocation record, updates status, and logs audit event."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("84.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(completion)
    await db_session.commit()

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
    )

    # Revoke credential
    rev_resp = await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="REGISTRAR-CHAIR",
        reason_code="ADMINISTRATIVE_ERROR",
        notes="Awarded under duplicate course registration",
    )

    assert rev_resp.status == "REVOKED"
    assert rev_resp.reason_code == "ADMINISTRATIVE_ERROR"
    assert rev_resp.audit_event_id.startswith("EVT-")

    # Assert Revocation table contains historical record
    stmt = select(Revocation).where(Revocation.credential_id == cred.id)
    rev_record = (await db_session.execute(stmt)).scalar_one_or_none()
    assert rev_record is not None
    assert rev_record.reason_code == "ADMINISTRATIVE_ERROR"
    assert rev_record.revoked_by_actor_id == "REGISTRAR-CHAIR"


@pytest.mark.asyncio
async def test_double_revocation_raises_error(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that attempting to revoke an already revoked credential is rejected."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("93.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(completion)
    await db_session.commit()

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
    )

    # First revocation
    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="DEAN-OFFICE",
        reason_code="RESCINDED",
    )

    # Second revocation must raise RevocationError
    with pytest.raises(RevocationError):
        await RevocationService.revoke_credential(
            db=db_session,
            credential_public_id=cred.public_id,
            actor_id="DEAN-OFFICE",
            reason_code="RESCINDED",
        )


@pytest.mark.asyncio
async def test_revoking_nonexistent_credential_raises_error(db_session: AsyncSession):
    """Verify revoking non-existent credential raises CredentialNotFoundError."""
    with pytest.raises(CredentialNotFoundError):
        await RevocationService.revoke_credential(
            db=db_session,
            credential_public_id="CRD-2026-999999",
            actor_id="ADMIN",
            reason_code="OTHER",
        )


@pytest.mark.asyncio
async def test_live_revocation_reflection_in_verification_api(
    api_client: AsyncClient, db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Integration: Verify VALID -> Revoke via REST -> Verify immediately returns REVOKED -> Query Audit."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("88.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(completion)
    await db_session.commit()

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
    )

    # 1. Verification returns VALID prior to revocation
    v1_resp = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": cred.public_id},
    )
    assert v1_resp.status_code == 200
    assert v1_resp.json()["outcome"] == "VALID"

    from backend.core.config import settings

    registrar_headers = {"Authorization": f"Bearer {settings.REGISTRAR_API_KEY}"}

    # 2. Administrative Revocation via REST API
    rev_post = await api_client.post(
        "/api/v1/revocation/revoke",
        json={
            "credential_public_id": cred.public_id,
            "actor_id": "DISCIPLINARY-BOARD",
            "reason_code": "ACADEMIC_MISCONDUCT",
            "notes": "Falsification of lab data discovered upon retrospective review.",
        },
        headers=registrar_headers,
    )
    assert rev_post.status_code == 200
    assert rev_post.json()["status"] == "REVOKED"
    assert rev_post.json()["revoked_by_actor_id"] == "REGISTRAR-001"

    # 3. Subsequent verification immediately reflects REVOKED (public verifier response)
    v2_resp = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": cred.public_id},
    )
    assert v2_resp.status_code == 200
    v2_data = v2_resp.json()
    assert v2_data["outcome"] == "REVOKED"
    assert v2_data["reason_code"] == "ACADEMIC_MISCONDUCT"
    assert v2_data["factors"]["is_revoked"] is True
    assert v2_data["revoked_at"] is not None

    # 4. Audit History API returns full sequential event log
    audit_resp = await api_client.get(
        f"/api/v1/revocation/audit/{cred.public_id}",
        headers=registrar_headers,
    )
    assert audit_resp.status_code == 200
    events = audit_resp.json()
    event_types = [e["event_type"] for e in events]
    assert "CREDENTIAL_ISSUED" in event_types
    assert "CREDENTIAL_REVOKED" in event_types
