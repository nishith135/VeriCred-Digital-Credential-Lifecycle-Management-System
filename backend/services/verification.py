"""Multi-Factor Third-Party Credential Verification Service.

Evaluates 5 independent integrity and lifecycle factors:
1. Existence: Identifier registered in official ledger.
2. Integrity: Canonical SHA-256 payload digest matches claims AND (when no external
   payload is presented) relational cross-check via `build_credential_payload` matches
   the stored `payload_snapshot` on all relational claim fields.
3. Authenticity: Asymmetric Ed25519 signature valid for issuer public key.
4. Eligibility / Chronology: Reuses `EligibilityService.evaluate_completion_rules` to
   verify `issued_at >= completion_timestamp`, `assessment_score >= rule.min_score`,
   `status == COMPLETED`, and rule effective window.
5. Revocation: Active status checked in real time against revocation ledger.

Precedence Rule:
NOT_FOUND -> TAMPERED -> INVALID_ISSUANCE -> REVOKED -> VALID.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.core.security import compute_payload_hash, verify_signature
from backend.models.audit import AuditEvent
from backend.models.completion import CompletionRecord
from backend.models.credential import Credential
from backend.models.verification import VerificationRequest
from backend.schemas.verification import (
    AnyVerificationResponse,
    PublicVerificationResponse,
    StaffVerificationResponse,
    VerificationFactorResult,
    VerificationResponse,
)
from backend.services.audit import AuditService
from backend.services.eligibility import EligibilityService
from backend.services.ids import VERIFICATION_SEQUENCE, format_verification_id, next_sequence_value
from backend.services.payloads import build_credential_payload

# Fields compared in the relational cross-check against `credential.payload_snapshot`.
# `issued_at` and `completion_timestamp` are excluded from JSON string comparison because
# `issued_at` is an issuance metadata timestamp (not derived from pre-issuance relational
# entities) and both timestamps are compared directly as `datetime` objects in the
# eligibility/chronology check.
RELATIONAL_CLAIM_KEYS = ("credential_id", "course", "learner", "assessment", "issuer")


class VerificationService:
    """Verifies academic credentials with multi-factor integrity and eligibility checks."""

    @staticmethod
    def select_response_for_role(
        response: StaffVerificationResponse,
        role: str,
    ) -> AnyVerificationResponse:
        """Return PublicVerificationResponse for `verifier` and StaffVerificationResponse for staff roles."""
        if role in ("registrar", "auditor"):
            return response
        return response.to_public_response()

    @classmethod
    async def verify_credential(
        cls,
        db: AsyncSession,
        credential_public_id: str,
        presented_payload: Optional[dict[str, Any]] = None,
        requester_ip: Optional[str] = None,
        actor_id: Optional[str] = None,
        persist: bool = True,
    ) -> StaffVerificationResponse:
        """Perform multi-factor verification and (when persist=True) atomically log VerificationRequest + AuditEvent."""
        now = datetime.now(timezone.utc)
        if persist:
            verification_number = await next_sequence_value(db, VERIFICATION_SEQUENCE)
            verification_id = format_verification_id(verification_number, now)
            event_id = await AuditService.generate_event_id(db)
        else:
            verification_id = format_verification_id(0, now)
            event_id = ""
        actor = actor_id or "PUBLIC-VERIFIER"

        # 1. Existence Check (eagerly loading issuer, revocation, completion, learner, course, rule in one JOIN)
        stmt = (
            select(Credential)
            .options(
                joinedload(Credential.issuer),
                joinedload(Credential.revocation),
                joinedload(Credential.completion).joinedload(CompletionRecord.learner),
                joinedload(Credential.completion).joinedload(CompletionRecord.course),
                joinedload(Credential.completion).joinedload(CompletionRecord.rule),
            )
            .where(Credential.public_id == credential_public_id)
        )
        result = await db.execute(stmt)
        credential = result.scalar_one_or_none()

        if not credential:
            if persist:
                verif_log = VerificationRequest(
                    public_id=verification_id,
                    credential_id=None,
                    requested_identifier=credential_public_id,
                    verification_timestamp=now,
                    outcome="NOT_FOUND",
                    reason_code="CREDENTIAL_NOT_FOUND",
                    integrity_check_passed=False,
                    issuer_authenticated=False,
                    requester_ip=requester_ip,
                )
                audit_event = AuditEvent(
                    event_id=event_id,
                    event_type="VERIFICATION_PERFORMED",
                    actor_id=actor,
                    target_entity_type="VerificationRequest",
                    target_entity_id=verification_id,
                    occurred_at=now,
                    details={
                        "requested_identifier": credential_public_id,
                        "credential_public_id": None,
                        "outcome": "NOT_FOUND",
                        "reason_code": "CREDENTIAL_NOT_FOUND",
                    },
                )
                db.add(verif_log)
                db.add(audit_event)
                await db.commit()

            return StaffVerificationResponse(
                verification_id=verification_id,
                credential_public_id=credential_public_id,
                outcome="NOT_FOUND",
                reason_code="CREDENTIAL_NOT_FOUND",
                message="No credential matching this identifier exists in the registry.",
                timestamp=now,
                factors=VerificationFactorResult(
                    record_found=False,
                    payload_hash_matches=False,
                    issuer_authenticated=False,
                    eligibility_valid=False,
                    revocation_checked=False,
                    is_revoked=False,
                    failed_subchecks=["CREDENTIAL_NOT_FOUND"],
                ),
            )

        failed_subchecks: list[str] = []

        # 2. Factor: Payload Integrity (SHA-256 Digest + Relational Cross-Check)
        payload_to_check = (
            presented_payload if presented_payload is not None else credential.payload_snapshot
        )
        computed_hash = compute_payload_hash(payload_to_check)
        hash_matches = computed_hash == credential.canonical_payload_hash
        if not hash_matches:
            failed_subchecks.append("PAYLOAD_DIGEST_MISMATCH")

        relational_matches = True
        comp = credential.completion
        if presented_payload is None and comp and comp.learner and comp.course and credential.issuer:
            rebuilt_payload = build_credential_payload(
                credential_id=credential.public_id,
                issued_at=credential.issued_at,
                completion_timestamp=comp.completion_timestamp,
                learner_id=comp.learner.public_id,
                learner_name=comp.learner.full_name,
                learner_email=comp.learner.email,
                course_code=comp.course.public_id,
                course_title=comp.course.title,
                assessment_score=comp.assessment_score,
                assessment_status=comp.status,
                issuer_id=credential.issuer.public_id,
                issuer_name=credential.issuer.name,
            )
            for key in RELATIONAL_CLAIM_KEYS:
                if credential.payload_snapshot.get(key) != rebuilt_payload.get(key):
                    relational_matches = False
                    break
            if not relational_matches:
                failed_subchecks.append("RELATIONAL_PAYLOAD_MISMATCH")

        payload_hash_matches = hash_matches and relational_matches

        # 3. Factor: Issuer Authenticity (Ed25519 Asymmetric Signature)
        issuer_authenticated = verify_signature(
            public_key_pem=credential.issuer.public_key_pem,
            payload_hash=credential.canonical_payload_hash,
            signature_b64=credential.issuer_signature,
        )
        if not issuer_authenticated:
            failed_subchecks.append("ISSUER_SIGNATURE_INVALID")

        # 4. Factor: Academic Eligibility & Issuance Chronology (shared with EligibilityService)
        eligibility_valid = True
        elig_failed_subchecks: list[str] = []
        elig_reasons: list[str] = []
        if comp is not None:
            eligibility_valid, elig_failed_subchecks, elig_reasons = (
                EligibilityService.evaluate_completion_rules(
                    completion=comp,
                    issued_at=credential.issued_at,
                    check_effective_window=True,
                )
            )
            failed_subchecks.extend(elig_failed_subchecks)

        # 5. Factor: Live Revocation Check
        is_revoked = (credential.status == "REVOKED") or (credential.revocation is not None)

        # Determine Outcome (Precedence: NOT_FOUND -> TAMPERED -> INVALID_ISSUANCE -> REVOKED -> VALID)
        if not payload_hash_matches:
            outcome = "TAMPERED"
            reason_code = (
                "PAYLOAD_DIGEST_MISMATCH" if not hash_matches else "RELATIONAL_PAYLOAD_MISMATCH"
            )
            message = (
                "Payload integrity violation detected: presented claims do not match cryptographic digest or relational records."
            )
        elif not issuer_authenticated:
            outcome = "INVALID_ISSUANCE"
            reason_code = "ISSUER_SIGNATURE_INVALID"
            message = "Issuer signature verification failed: authenticity could not be verified."
        elif not eligibility_valid:
            outcome = "INVALID_ISSUANCE"
            reason_code = elig_failed_subchecks[0]
            message = (
                f"Invalid issuance detected ({', '.join(elig_failed_subchecks)}): "
                f"{' '.join(elig_reasons)}"
            )
        elif is_revoked:
            outcome = "REVOKED"
            reason_code = (
                credential.revocation.reason_code
                if credential.revocation
                else "CREDENTIAL_REVOKED"
            )
            message = f"Credential has been officially revoked. Reason: {reason_code}."
        else:
            outcome = "VALID"
            reason_code = "VERIFICATION_SUCCESSFUL"
            message = "Credential is authentic, unmodified, and currently active."

        # Atomically persist VerificationRequest and VERIFICATION_PERFORMED AuditEvent when persist=True
        if persist:
            verif_log = VerificationRequest(
                public_id=verification_id,
                credential_id=credential.id,
                requested_identifier=credential_public_id,
                verification_timestamp=now,
                outcome=outcome,
                reason_code=reason_code,
                integrity_check_passed=payload_hash_matches,
                issuer_authenticated=issuer_authenticated,
                requester_ip=requester_ip,
            )
            audit_event = AuditEvent(
                event_id=event_id,
                event_type="VERIFICATION_PERFORMED",
                actor_id=actor,
                target_entity_type="VerificationRequest",
                target_entity_id=verification_id,
                occurred_at=now,
                details={
                    "requested_identifier": credential_public_id,
                    "credential_public_id": credential.public_id,
                    "outcome": outcome,
                    "reason_code": reason_code,
                    "failed_subchecks": failed_subchecks,
                },
            )
            db.add(verif_log)
            db.add(audit_event)
            await db.commit()

        cred_details = {
            "public_id": credential.public_id,
            "issuer_id": credential.issuer.public_id,
            "issuer_name": credential.issuer.name,
            "issued_at": credential.issued_at.isoformat(),
            "status": credential.status,
            "payload_snapshot": credential.payload_snapshot,
        }

        rev_details = None
        if credential.revocation:
            rev_details = {
                "public_id": credential.revocation.public_id,
                "reason_code": credential.revocation.reason_code,
                "revoked_by_actor_id": credential.revocation.revoked_by_actor_id,
                "revocation_timestamp": credential.revocation.revocation_timestamp.isoformat(),
                "notes": credential.revocation.notes,
            }

        return StaffVerificationResponse(
            verification_id=verification_id,
            credential_public_id=credential_public_id,
            outcome=outcome,
            reason_code=reason_code,
            message=message,
            timestamp=now,
            factors=VerificationFactorResult(
                record_found=True,
                payload_hash_matches=payload_hash_matches,
                issuer_authenticated=issuer_authenticated,
                eligibility_valid=eligibility_valid,
                revocation_checked=True,
                is_revoked=is_revoked,
                failed_subchecks=failed_subchecks,
            ),
            credential_details=cred_details,
            revocation_details=rev_details,
        )
