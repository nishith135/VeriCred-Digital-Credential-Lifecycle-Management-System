"""Tests for Multi-Factor Third-Party Credential Verification.

Verifies:
- 4-factor evaluation (existence, payload integrity, issuer authenticity, revocation).
- Tamper detection when grades or claims are modified.
- Tampering strictly overriding revocation.
- Public REST API endpoint execution and verification request audit logging.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import compute_payload_hash, generate_ed25519_keypair, sign_payload_hash
from backend.models import AuditEvent, CompletionRecord, Credential, VerificationRequest
from backend.services.ids import format_completion_id, format_course_id, format_credential_id, format_learner_id
from backend.services.issuance import IssuanceService
from backend.services.payloads import build_credential_payload
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
        public_id=format_completion_id(learner.public_id, course.public_id),
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
    assert verif.factors.payload_hash_matches is True
    assert verif.factors.issuer_authenticated is True
    assert verif.factors.is_revoked is False


@pytest.mark.asyncio
async def test_verification_not_found_credential(db_session: AsyncSession):
    """Verify query for non-existent credential returns outcome NOT_FOUND."""
    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id="CRD-2026-999999",
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
        public_id=format_completion_id(learner.public_id, course.public_id),
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
    tampered_claims["assessment"] = {**cred.payload_snapshot["assessment"], "score": 99.00}

    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        presented_payload=tampered_claims,
    )

    assert verif.outcome == "TAMPERED"
    assert verif.reason_code == "PAYLOAD_DIGEST_MISMATCH"
    assert verif.factors.record_found is True
    assert verif.factors.payload_hash_matches is False


@pytest.mark.asyncio
async def test_tampering_strictly_overrides_revocation(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Invariant: If a credential was revoked, but holder ALSO altered claims, result MUST be TAMPERED."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
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
    tampered_claims["course"] = {**cred.payload_snapshot["course"], "title": "Hacked Doctorate in AI"}

    verif = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        presented_payload=tampered_claims,
    )

    # Must be TAMPERED, not merely REVOKED
    assert verif.outcome == "TAMPERED"
    assert verif.factors.payload_hash_matches is False
    assert verif.factors.is_revoked is True


@pytest.mark.asyncio
async def test_verification_detects_invalid_issuer_signature(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify that forged signature from unauthorized key returns INVALID_ISSUANCE."""
    issuer, _ = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
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
        public_id=format_completion_id(learner.public_id, course.public_id),
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


@pytest.mark.asyncio
async def test_all_five_verification_outcomes_create_request_and_audit_event(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Acceptance Check (a): One verification per outcome (VALID, REVOKED, TAMPERED, NOT_FOUND, INVALID_ISSUANCE)
    each creates exactly one VerificationRequest and one VERIFICATION_PERFORMED AuditEvent.
    """
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("90.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
    )

    # 1. VALID
    r_valid = await VerificationService.verify_credential(db_session, cred.public_id)
    assert r_valid.outcome == "VALID"

    # 2. TAMPERED (via presented_payload)
    bad_payload = dict(cred.payload_snapshot)
    bad_payload["assessment"] = {**cred.payload_snapshot["assessment"], "score": 99.99}
    r_tampered = await VerificationService.verify_credential(
        db_session, cred.public_id, presented_payload=bad_payload
    )
    assert r_tampered.outcome == "TAMPERED"

    # 3. REVOKED
    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="REGISTRAR-01",
        reason_code="ADMINISTRATIVE_ERROR",
    )
    r_revoked = await VerificationService.verify_credential(db_session, cred.public_id)
    assert r_revoked.outcome == "REVOKED"

    # 4. INVALID_ISSUANCE (premature issuance timestamp on completion)
    comp_obj = await db_session.get(CompletionRecord, completion.id)
    comp_obj.completion_timestamp = cred.issued_at + timedelta(days=3)
    await db_session.commit()
    r_invalid = await VerificationService.verify_credential(db_session, cred.public_id)
    assert r_invalid.outcome == "INVALID_ISSUANCE"

    # 5. NOT_FOUND
    r_not_found = await VerificationService.verify_credential(db_session, "CRD-2026-999999")
    assert r_not_found.outcome == "NOT_FOUND"

    # Verify 5 VerificationRequest rows and 5 VERIFICATION_PERFORMED AuditEvent rows
    verif_rows = (
        await db_session.execute(select(VerificationRequest).order_by(VerificationRequest.id))
    ).scalars().all()
    verif_events = (
        await db_session.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "VERIFICATION_PERFORMED")
            .order_by(AuditEvent.id)
        )
    ).scalars().all()

    assert len(verif_rows) == 5
    assert len(verif_events) == 5
    assert [v.outcome for v in verif_rows] == [
        "VALID",
        "TAMPERED",
        "REVOKED",
        "INVALID_ISSUANCE",
        "NOT_FOUND",
    ]
    for v_row, ev_row in zip(verif_rows, verif_events):
        assert ev_row.target_entity_type == "VerificationRequest"
        assert ev_row.target_entity_id == v_row.public_id
        assert ev_row.details["outcome"] == v_row.outcome
        assert ev_row.details["requested_identifier"] == v_row.requested_identifier


@pytest.mark.asyncio
async def test_verification_premature_issuance_and_below_min_score_return_invalid_issuance(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Acceptance Check (b): Premature issuance and below-min-score return INVALID_ISSUANCE with failing sub-check named."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    # Case 1: Premature issuance (issued_at < completion_timestamp)
    t_completed = now - timedelta(days=2)
    t_issued_early = now - timedelta(days=5)
    comp1 = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("90.00"),
        status="COMPLETED",
        completion_timestamp=t_completed,
    )
    db_session.add(comp1)
    await db_session.flush()

    cred1_id = format_credential_id(1, t_issued_early)
    snap1 = build_credential_payload(
        credential_id=cred1_id,
        issued_at=t_issued_early,
        completion_timestamp=t_completed,
        learner_id=learner.public_id,
        learner_name=learner.full_name,
        learner_email=learner.email,
        course_code=course.public_id,
        course_title=course.title,
        assessment_score=comp1.assessment_score,
        assessment_status=comp1.status,
        issuer_id=issuer.public_id,
        issuer_name=issuer.name,
    )
    h1 = compute_payload_hash(snap1)
    # Deliberate anomaly setup (direct ORM insert bypassing service guard), valid only because the DB is isolated.
    cred1 = Credential(
        public_id=cred1_id,
        completion_id=comp1.id,
        issuer_id=issuer.id,
        issued_at=t_issued_early,
        canonical_payload_hash=h1,
        issuer_signature=sign_payload_hash(issuer_priv_pem, h1),
        payload_snapshot=snap1,
        status="ACTIVE",
    )
    db_session.add(cred1)
    await db_session.commit()

    res_premature = await VerificationService.verify_credential(db_session, cred1_id)
    assert res_premature.outcome == "INVALID_ISSUANCE"
    assert res_premature.reason_code == "PREMATURE_ISSUANCE_TIMESTAMP"
    assert "PREMATURE_ISSUANCE_TIMESTAMP" in res_premature.factors.failed_subchecks

    # Case 2: Below minimum passing score (assessment_score < rule.min_score)
    comp1.completion_timestamp = t_issued_early - timedelta(days=1)
    comp1.assessment_score = Decimal("65.00")
    snap2 = build_credential_payload(
        credential_id=cred1_id,
        issued_at=t_issued_early,
        completion_timestamp=comp1.completion_timestamp,
        learner_id=learner.public_id,
        learner_name=learner.full_name,
        learner_email=learner.email,
        course_code=course.public_id,
        course_title=course.title,
        assessment_score=comp1.assessment_score,
        assessment_status=comp1.status,
        issuer_id=issuer.public_id,
        issuer_name=issuer.name,
    )
    h2 = compute_payload_hash(snap2)
    cred1.payload_snapshot = snap2
    cred1.canonical_payload_hash = h2
    cred1.issuer_signature = sign_payload_hash(issuer_priv_pem, h2)
    await db_session.commit()

    res_low_score = await VerificationService.verify_credential(db_session, cred1_id)
    assert res_low_score.outcome == "INVALID_ISSUANCE"
    assert res_low_score.reason_code == "BELOW_MIN_SCORE"
    assert "BELOW_MIN_SCORE" in res_low_score.factors.failed_subchecks


@pytest.mark.asyncio
async def test_relational_crosscheck_catches_consistent_db_payload_and_hash_tamper(
    db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Acceptance Check (c): Directly editing payload_snapshot AND canonical_payload_hash in the DB
    (a consistent-looking tamper) is caught by the relational cross-check as TAMPERED.
    """
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("83.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()

    cred_resp = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
    )

    # Directly mutate payload_snapshot AND canonical_payload_hash (and signature) in the DB
    # while leaving the relational completion_records.assessment_score at 83.00
    cred_row = await db_session.get(Credential, cred_resp.id)
    forged_snapshot = dict(cred_row.payload_snapshot)
    forged_snapshot["assessment"] = {**cred_row.payload_snapshot["assessment"], "score": 99.90}
    forged_hash = compute_payload_hash(forged_snapshot)
    cred_row.payload_snapshot = forged_snapshot
    cred_row.canonical_payload_hash = forged_hash
    cred_row.issuer_signature = sign_payload_hash(issuer_priv_pem, forged_hash)
    await db_session.commit()

    verif = await VerificationService.verify_credential(db_session, cred_resp.public_id)
    assert verif.outcome == "TAMPERED"
    assert verif.reason_code == "RELATIONAL_PAYLOAD_MISMATCH"
    assert "RELATIONAL_PAYLOAD_MISMATCH" in verif.factors.failed_subchecks
    assert verif.factors.payload_hash_matches is False
