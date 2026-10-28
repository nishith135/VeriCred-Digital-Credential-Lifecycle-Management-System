"""Academic Eligibility Evaluation Service.

Evaluates learner completion evidence against course credential rules,
enforcing minimum score thresholds, completion status requirements,
date effective windows, and duplicate issuance prevention.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.exceptions import DomainException
from backend.models.completion import CompletionRecord
from backend.schemas.credential import EligibilityEvaluationResult


class EligibilityService:
    """Evaluates student academic achievements against credential rules."""

    @staticmethod
    async def get_completion_with_relations(
        db: AsyncSession, completion_id: int
    ) -> Optional[CompletionRecord]:
        """Fetch a completion record with all related entities loaded."""
        stmt = (
            select(CompletionRecord)
            .options(
                selectinload(CompletionRecord.learner),
                selectinload(CompletionRecord.course),
                selectinload(CompletionRecord.rule),
                selectinload(CompletionRecord.credential),
            )
            .where(CompletionRecord.id == completion_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def evaluate_eligibility(
        cls, db: AsyncSession, completion_id: int
    ) -> EligibilityEvaluationResult:
        """Evaluate academic eligibility for credential issuance."""
        completion = await cls.get_completion_with_relations(db, completion_id)
        if not completion:
            raise DomainException(
                f"Completion record {completion_id} not found.",
                code="COMPLETION_NOT_FOUND",
                status_code=404,
                details={"completion_id": completion_id},
            )

        reasons: list[str] = []
        is_eligible = True
        already_issued = completion.credential is not None

        # 1. Duplicate Issuance Check
        if already_issued:
            is_eligible = False
            reasons.append("Credential has already been issued for this completion record.")

        # 2. Completion Status Check
        if completion.status != "COMPLETED":
            is_eligible = False
            reasons.append(
                f"Completion status '{completion.status}' does not satisfy required 'COMPLETED' status."
            )

        # 3. Minimum Passing Score Check
        min_required = completion.rule.min_score
        if completion.assessment_score < min_required:
            is_eligible = False
            reasons.append(
                f"Assessment score {completion.assessment_score:.2f}% is below required passing threshold {min_required:.2f}%."
            )

        # 4. Effective Date Window Check
        ts = completion.completion_timestamp
        rule = completion.rule
        if ts < rule.effective_from or ts > rule.effective_to:
            is_eligible = False
            reasons.append(
                f"Completion date {ts.isoformat()} falls outside the effective rule window ({rule.effective_from.isoformat()} to {rule.effective_to.isoformat()})."
            )

        return EligibilityEvaluationResult(
            is_eligible=is_eligible,
            completion_id=completion.id,
            learner_public_id=completion.learner.public_id,
            learner_name=completion.learner.full_name,
            course_public_id=completion.course.public_id,
            course_title=completion.course.title,
            assessment_score=completion.assessment_score,
            required_min_score=min_required,
            completion_status=completion.status,
            already_issued=already_issued,
            reasons=reasons,
        )
