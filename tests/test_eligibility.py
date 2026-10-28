"""Unit tests for Academic Eligibility Evaluation business rules and score boundary conditions."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import CompletionRecord
from backend.services.eligibility import EligibilityService


@pytest.mark.asyncio
async def test_eligibility_passing_boundary_80_percent(
    db_session: AsyncSession, sample_academic_setup
):
    """Verify that an exact 80.00% score is eligible for issuance."""
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("80.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    result = await EligibilityService.evaluate_eligibility(db_session, completion.id)
    assert result.is_eligible is True
    assert result.already_issued is False
    assert len(result.reasons) == 0


@pytest.mark.asyncio
async def test_eligibility_failing_boundary_79_99_percent(
    db_session: AsyncSession, sample_academic_setup
):
    """Verify that 79.99% score is strictly rejected as ineligible."""
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("79.99"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    result = await EligibilityService.evaluate_eligibility(db_session, completion.id)
    assert result.is_eligible is False
    assert any("below required passing threshold" in r for r in result.reasons)


@pytest.mark.asyncio
async def test_eligibility_rejected_if_status_not_completed(
    db_session: AsyncSession, sample_academic_setup
):
    """Verify that high score (95%) is rejected if status is not COMPLETED."""
    course, learner, rule = sample_academic_setup
    now = datetime.now(timezone.utc)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("95.00"),
        status="IN_PROGRESS",
        completion_timestamp=now,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    result = await EligibilityService.evaluate_eligibility(db_session, completion.id)
    assert result.is_eligible is False
    assert any("does not satisfy required 'COMPLETED' status" in r for r in result.reasons)


@pytest.mark.asyncio
async def test_eligibility_rejected_if_outside_rule_date_window(
    db_session: AsyncSession, sample_academic_setup
):
    """Verify rejection when completion timestamp falls outside active rule window."""
    course, learner, rule = sample_academic_setup
    expired_date = rule.effective_from - timedelta(days=10)

    completion = CompletionRecord(
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("90.00"),
        status="COMPLETED",
        completion_timestamp=expired_date,
    )
    db_session.add(completion)
    await db_session.commit()
    await db_session.refresh(completion)

    result = await EligibilityService.evaluate_eligibility(db_session, completion.id)
    assert result.is_eligible is False
    assert any("falls outside the effective rule window" in r for r in result.reasons)
