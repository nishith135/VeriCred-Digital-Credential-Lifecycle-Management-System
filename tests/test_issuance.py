"""Integration tests for atomic credential issuance, audit logging, and duplicate prevention."""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import DuplicateIssuanceError, IneligibleIssuanceError
from backend.core.security import compute_payload_hash, verify_signature
from backend.models import AuditEvent, CompletionRecord
from backend.services.issuance import IssuanceService


@pytest.mark.asyncio
async def test_atomic_issuance_success_and_cryptographic_verification(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify end-to-end atomic issuance, SHA-256 payload integrity, and Ed25519 signature."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("88.50"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    # Issue credential
    cred_resp = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
        actor_id="REGISTRAR-SYSTEM",
    )

    assert cred_resp.id is not None
    assert cred_resp.public_id.startswith("CRED-")
    assert cred_resp.completion_id == completion.id
    assert cred_resp.status == "ACTIVE"

    # Verify SHA-256 integrity of snapshot
    recomputed_hash = compute_payload_hash(cred_resp.payload_snapshot)
    assert cred_resp.canonical_payload_hash == recomputed_hash

    # Verify Ed25519 asymmetric signature authenticity
    is_valid_sig = verify_signature(
        public_key_pem=issuer.public_key_pem,
        payload_hash=cred_resp.canonical_payload_hash,
        signature_b64=cred_resp.issuer_signature,
    )
    assert is_valid_sig is True

    # Verify AuditEvent persisted in same transaction
    stmt_audit = select(AuditEvent).where(
        AuditEvent.target_entity_id == cred_resp.public_id
    )
    audit = (await db_session.execute(stmt_audit)).scalar_one_or_none()
    assert audit is not None
    assert audit.event_type == "CREDENTIAL_ISSUED"
    assert audit.target_entity_type == "Credential"


@pytest.mark.asyncio
async def test_duplicate_issuance_strictly_prevented(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that issuing twice for the same completion is rejected with DuplicateIssuanceError."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("92.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    # First issuance succeeds
    await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
    )

    # Second issuance must raise DuplicateIssuanceError
    with pytest.raises(DuplicateIssuanceError):
        await IssuanceService.issue_credential(
            db=db_session,
            completion_id=completion.id,
            issuer_public_id=issuer.public_id,
            issuer_private_key_pem=issuer_priv_pem,
        )


@pytest.mark.asyncio
async def test_ineligible_issuance_raises_error(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that attempting to issue for score below 80% raises IneligibleIssuanceError."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    failing_completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("75.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(failing_completion)
    await db_session.commit()
    await db_session.refresh(failing_completion)

    with pytest.raises(IneligibleIssuanceError):
        await IssuanceService.issue_credential(
            db=db_session,
            completion_id=failing_completion.id,
            issuer_public_id=issuer.public_id,
            issuer_private_key_pem=issuer_priv_pem,
        )


@pytest.mark.asyncio
async def test_issuance_rest_api_endpoints(
    api_client: AsyncClient, db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Test REST API evaluate and issue endpoints."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("85.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    # 1. Test POST /api/v1/issuance/evaluate
    eval_resp = await api_client.post(
        "/api/v1/issuance/evaluate",
        json={"completion_id": completion.id},
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["is_eligible"] is True
    assert eval_data["already_issued"] is False

    # 2. Test POST /api/v1/issuance/issue
    issue_resp = await api_client.post(
        "/api/v1/issuance/issue",
        json={
            "completion_id": completion.id,
            "issuer_public_id": issuer.public_id,
            "actor_id": "API-ADMIN-01",
        },
        headers={"X-Issuer-Private-Key": issuer_priv_pem},
    )
    assert issue_resp.status_code == 201
    cred_data = issue_resp.json()
    assert cred_data["public_id"].startswith("CRED-")
    assert cred_data["completion_id"] == completion.id

    # 3. Test POST /api/v1/issuance/issue duplicate attempt -> 409 Conflict
    dup_resp = await api_client.post(
        "/api/v1/issuance/issue",
        json={
            "completion_id": completion.id,
            "issuer_public_id": issuer.public_id,
            "actor_id": "API-ADMIN-01",
        },
        headers={"X-Issuer-Private-Key": issuer_priv_pem},
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"] == "DUPLICATE_ISSUANCE_REJECTED"
