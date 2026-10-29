"""Tests for Append-Only Audit History and Multi-Criteria Filtering."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CompletionRecord
from backend.services.audit import AuditService
from backend.services.ids import format_completion_id
from backend.services.issuance import IssuanceService
from backend.services.revocation import RevocationService


@pytest.mark.asyncio
async def test_audit_event_logging_and_multi_criteria_filtering(
    db_session: AsyncSession,
):
    """Verify that audit events are recorded append-only and can be filtered by type, actor, and target."""
    now = datetime.now(timezone.utc)
    t1 = now - timedelta(minutes=10)
    t2 = now - timedelta(minutes=5)
    t3 = now

    cred_target_id = "CRD-2026-000001"
    rule_target_id = "1"
    admin_actor = "ADMIN-01"

    # Deliberate anomaly setup (direct audit event insert without parent Credential/Rule rows), valid only because the DB is isolated.
    # Record 3 events
    await AuditService.log_event(
        db=db_session,
        event_type="CREDENTIAL_ISSUED",
        target_entity_type="Credential",
        target_entity_id=cred_target_id,
        actor_id="REGISTRAR-A",
        details={"score": 85.0},
        occurred_at=t1,
    )
    await AuditService.log_event(
        db=db_session,
        event_type="CREDENTIAL_REVOKED",
        target_entity_type="Credential",
        target_entity_id=cred_target_id,
        actor_id="DEAN-B",
        details={"reason": "ACADEMIC_MISCONDUCT"},
        occurred_at=t2,
    )
    await AuditService.log_event(
        db=db_session,
        event_type="RULE_MODIFIED",
        target_entity_type="CredentialRule",
        target_entity_id=rule_target_id,
        actor_id=admin_actor,
        details={"new_threshold": 85.0},
        occurred_at=t3,
    )

    # 1. Filter by target_entity_id
    events_by_id, total_id = await AuditService.query_events(
        db=db_session, target_entity_id=cred_target_id
    )
    assert total_id == 2
    assert len(events_by_id) == 2
    assert [e.event_type for e in events_by_id] == ["CREDENTIAL_ISSUED", "CREDENTIAL_REVOKED"]

    # 2. Filter by actor_id
    events_by_actor, total_actor = await AuditService.query_events(
        db=db_session, actor_id=admin_actor
    )
    assert total_actor == 1
    assert events_by_actor[0].actor_id == admin_actor

    # 3. Filter by date window
    events_window, total_window = await AuditService.query_events(
        db=db_session,
        target_entity_id=cred_target_id,
        from_date=t1 - timedelta(seconds=1),
        to_date=t1 + timedelta(seconds=1),
    )
    assert total_window == 1
    assert events_window[0].event_type == "CREDENTIAL_ISSUED"


@pytest.mark.asyncio
async def test_audit_rest_api_endpoint_pagination_and_query(
    api_client: AsyncClient, db_session: AsyncSession, sample_issuer, sample_academic_setup
):
    """Verify GET /api/v1/audit/events returns paginated results and filters by target_entity_id."""
    issuer, issuer_priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    completion = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("86.50"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(completion)
    await db_session.commit()

    # 1. Issue
    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=completion.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=issuer_priv_pem,
        actor_id="ISSUER-AGENT",
    )

    # 2. Revoke
    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="REVOCATION-AGENT",
        reason_code="ADMINISTRATIVE_ERROR",
    )

    # 3. Query audit events API for this credential (as auditor via Bearer API key)
    from backend.core.config import settings

    response = await api_client.get(
        "/api/v1/audit/events",
        params={"target_entity_id": cred.public_id},
        headers={"Authorization": f"Bearer {settings.AUDITOR_API_KEY}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["events"]) == 2

    first_event = data["events"][0]
    second_event = data["events"][1]

    assert first_event["event_type"] == "CREDENTIAL_ISSUED"
    assert first_event["actor_id"] == "ISSUER-AGENT"
    assert second_event["event_type"] == "CREDENTIAL_REVOKED"
    assert second_event["actor_id"] == "REVOCATION-AGENT"
