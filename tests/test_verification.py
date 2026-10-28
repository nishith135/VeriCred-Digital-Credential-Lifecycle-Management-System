"""Tests for Multi-Factor Third-Party Credential Verification.

Verifies:
- 4-factor evaluation (existence, payload integrity, issuer authenticity, revocation).
- Tamper detection when grades or claims are modified.
- Tampering strictly overriding revocation.
- Public REST API endpoint execution and verification request audit logging.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import generate_ed25519_keypair, sign_payload_hash
from backend.models import CompletionRecord, VerificationRequest
from backend.services.issuance import IssuanceService
from backend.services.revocation import RevocationService
from backend.services.verification import VerificationService


@pytest.mark.asyncio
async def test_verification_valid_active_credential(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify an authentic active credential returns outcome VALID."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("89.00"),
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

    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        requester_ip="192.168.1.50",
    )

    assert verif.outcome == "VALID"
    assert verif.reason_code == "VERIFICATION_SUCCESSFUL"
    assert verif.factors.record_found is True
    assert verif.factors.payload_integrity_valid is True
    assert verif.factors.issuer_authenticated is True
    assert verif.factors.is_revoked is False


@pytest.mark.asyncio
async def test_verification_not_found_credential(db_session: AsyncSession):
    """Verify query for non-existent credential returns outcome NOT_FOUND."""
    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id="CRED-NONEXISTENT-9999",
    )

    assert verif.outcome == "NOT_FOUND"
    assert verif.factors.record_found is False


@pytest.mark.asyncio
async def test_verification_detects_tampered_payload(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that tampering with claims (e.g. inflating score) returns TAMPERED."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("82.00"),
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

    # Holder presents altered claims (score boosted from 82.00 to 99.00)
    tampered_claims = dict(cred.payload_snapshot)
    tampered_claims["assessment_score"] = 99.00

    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        presented_payload=tampered_claims,
    )

    assert verif.outcome == "TAMPERED"
    assert verif.reason_code == "PAYLOAD_DIGEST_MISMATCH"
    assert verif.factors.record_found is True
    assert verif.factors.payload_integrity_valid is False


@pytest.mark.asyncio
async def test_tampering_strictly_overrides_revocation(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Invariant: If a credential was revoked, but holder ALSO altered claims, result MUST be TAMPERED."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("85.00"),
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

    # 1. Revoke the credential
    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="DEAN-ADMIN",
        reason_code="ACADEMIC_MISCONDUCT",
    )

    # 2. Present tampered claims against revoked credential
    tampered_claims = dict(cred.payload_snapshot)
    tampered_claims["course_title"] = "Hacked Doctorate in AI"

    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        presented_payload=tampered_claims,
    )

    # Must be TAMPERED, not merely REVOKED
    assert verif.outcome == "TAMPERED"
    assert verif.factors.payload_integrity_valid is False
    assert verif.factors.is_revoked is True


@pytest.mark.asyncio
async def test_verification_detects_invalid_issuer_signature(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that forged signature from unauthorized key returns INVALID_ISSUANCE."""
    issuer, _ = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("87.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(completion)
    await db_session.commit()

    # Sign with an unauthorized, alien keypair
    alien_priv_pem, _ = generate_ed25519_keypair()
    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=alien_priv_pem,  # key doesn't match issuer's public key
    )

    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=cred.public_id,
    )

    assert verif.outcome == "INVALID_ISSUANCE"
    assert verif.factors.issuer_authenticated is False


@pytest.mark.asyncio
async def test_public_verification_rest_endpoint(
    api_client: AsyncClient, db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify POST /api/v1/verification/verify logs request and returns structured response."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("91.00"),
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

    # Query public endpoint
    response = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": cred.public_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "VALID"
    assert data["factors"]["issuer_authenticated"] is True

    # Assert verification request was logged in database
    stmt = select(VerificationRequest).where(
        VerificationRequest.requested_identifier == cred.public_id
    )
    log = (await db_session.execute(stmt)).scalar_one_or_none()
    assert log is not None
    assert log.outcome == "VALID"
    assert log.integrity_check_passed is True
