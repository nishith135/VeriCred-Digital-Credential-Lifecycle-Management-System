"""Academic Eligibility Evaluation Service.

Evaluates learner completion evidence against course credential rules,
enforcing minimum score thresholds, completion status requirements,
date effective windows, and duplicate issuance prevention.
"""

from datetime import datetime
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
    def evaluate_completion_rules(
        completion: CompletionRecord,
        issued_at: Optional[datetime] = None,
        check_effective_window: bool = True,
    ) -> tuple[bool, list[str], list[str]]:
        """Evaluate academic completion rules and optional issuance chronology.

        Shared by EligibilityService (pre-issuance) and VerificationService (post-issuance).

        Returns:
            (is_valid, failed_subchecks, reasons)
        """
        failed_subchecks: list[str] = []
        reasons: list[str] = []
        rule = completion.rule
        required_status = rule.required_completion_status if rule else "COMPLETED"
        min_required = rule.min_score if rule else None

        # 1. Chronological Check (when verifying an already-issued credential)
        if issued_at is not None and issued_at < completion.completion_timestamp:
            failed_subchecks.append("PREMATURE_ISSUANCE_TIMESTAMP")
            reasons.append(
                f"Credential issued_at ({issued_at.isoformat()}) precedes completion_timestamp ({completion.completion_timestamp.isoformat()})."
            )

        # 2. Completion Status Check
        if completion.status != required_status:
            failed_subchecks.append("INELIGIBLE_COMPLETION_STATUS")
            reasons.append(
                f"Completion status '{completion.status}' does not satisfy required '{required_status}' status."
            )

        # 3. Minimum Passing Score Check
        if min_required is not None and completion.assessment_score < min_required:
            failed_subchecks.append("BELOW_MIN_SCORE")
            reasons.append(
                f"Assessment score {completion.assessment_score:.2f}% is below required passing threshold {min_required:.2f}%."
            )

        # 4. Effective Date Window Check
        if check_effective_window and rule is not None:
            ts = completion.completion_timestamp
            if ts < rule.effective_from or ts > rule.effective_to:
                failed_subchecks.append("OUTSIDE_RULE_EFFECTIVE_WINDOW")
                reasons.append(
                    f"Completion date {ts.isoformat()} falls outside the effective rule window ({rule.effective_from.isoformat()} to {rule.effective_to.isoformat()})."
                )

        return (len(failed_subchecks) == 0, failed_subchecks, reasons)

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

        already_issued = completion.credential is not None
        rules_ok, failed_subchecks, reasons = cls.evaluate_completion_rules(
            completion=completion,
            issued_at=None,
            check_effective_window=True,
        )
        is_eligible = rules_ok and not already_issued

        # Duplicate Issuance Check
        if already_issued:
            failed_subchecks.insert(0, "DUPLICATE_ISSUANCE")
            reasons.insert(0, "Credential has already been issued for this completion record.")

        return EligibilityEvaluationResult(
            is_eligible=is_eligible,
            completion_id=completion.id,
            completion_public_id=completion.public_id,
            learner_public_id=completion.learner.public_id,
            learner_name=completion.learner.full_name,
            course_public_id=completion.course.public_id,
            course_title=completion.course.title,
            assessment_score=completion.assessment_score,
            required_min_score=completion.rule.min_score,
            completion_status=completion.status,
            already_issued=already_issued,
            failed_subchecks=failed_subchecks,
            reasons=reasons,
        )
