"""Multi-Factor Third-Party Credential Verification Service.

Evaluates 4 independent integrity factors:
1. Existence: Identifier registered in official ledger.
2. Integrity: Canonical SHA-256 payload digest matches claims (tamper detection).
3. Authenticity: Asymmetric Ed25519 signature valid for issuer public key.
4. Revocation: Active status checked in real time against revocation ledger.

Precedence Rule:
Tampering strictly overrides revocation and valid status. An altered payload
must always be flagged as TAMPERED.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.core.security import compute_payload_hash, verify_signature
from backend.models.credential import Credential
from backend.models.verification import VerificationRequest
from backend.schemas.verification import (
    VerificationFactorResult,
    VerificationResponse,
)
from backend.services.ids import VERIFICATION_SEQUENCE, format_verification_id, next_sequence_value


class VerificationService:
    """Verifies academic credentials with multi-factor integrity checks."""

    @classmethod
    async def verify_credential(
        cls,
        db: AsyncSession,
        credential_public_id: str,
        presented_payload: Optional[dict[str, Any]] = None,
        requester_ip: Optional[str] = None,
    ) -> VerificationResponse:
        """Perform multi-factor verification and audit log query attempt."""
        now = datetime.now(timezone.utc)
        verification_number = await next_sequence_value(db, VERIFICATION_SEQUENCE)
        verification_id = format_verification_id(verification_number, now)

        # 1. Existence Check
        stmt = (
            select(Credential)
            .options(
                selectinload(Credential.issuer),
                selectinload(Credential.revocation),
            )
            .where(Credential.public_id == credential_public_id)
        )
        result = await db.execute(stmt)
        credential = result.scalar_one_or_none()

        if not credential:
            # Audit missing query
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
            db.add(verif_log)
            await db.commit()

            return VerificationResponse(
                verification_id=verification_id,
                credential_public_id=credential_public_id,
                outcome="NOT_FOUND",
                reason_code="CREDENTIAL_NOT_FOUND",
                message="No credential matching this identifier exists in the registry.",
                timestamp=now,
                factors=VerificationFactorResult(
                    record_found=False,
                    payload_integrity_valid=False,
                    issuer_authenticated=False,
                    revocation_checked=False,
                    is_revoked=False,
                ),
            )

        # 2. Factor: Payload Integrity (Tamper Detection)
        # Check against presented payload if provided, or stored snapshot
        payload_to_check = presented_payload if presented_payload is not None else credential.payload_snapshot
        computed_hash = compute_payload_hash(payload_to_check)
        payload_integrity_valid = (computed_hash == credential.canonical_payload_hash)

        # 3. Factor: Issuer Authenticity (Ed25519 Asymmetric Signature)
        issuer_authenticated = verify_signature(
            public_key_pem=credential.issuer.public_key_pem,
            payload_hash=credential.canonical_payload_hash,
            signature_b64=credential.issuer_signature,
        )

        # 4. Factor: Live Revocation Check
        is_revoked = (credential.status == "REVOKED") or (credential.revocation is not None)

        # Determine Outcome (Tampering strictly overrides revocation and validity)
        if not payload_integrity_valid:
            outcome = "TAMPERED"
            reason_code = "PAYLOAD_DIGEST_MISMATCH"
            message = "Payload integrity violation detected: presented claims do not match cryptographic digest."
        elif not issuer_authenticated:
            outcome = "INVALID_ISSUANCE"
            reason_code = "ISSUER_SIGNATURE_INVALID"
            message = "Issuer signature verification failed: authenticity could not be verified."
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

        # Audit attempt in verification_requests
        verif_log = VerificationRequest(
            public_id=verification_id,
            credential_id=credential.id,
            requested_identifier=credential_public_id,
            verification_timestamp=now,
            outcome=outcome,
            reason_code=reason_code,
            integrity_check_passed=payload_integrity_valid,
            issuer_authenticated=issuer_authenticated,
            requester_ip=requester_ip,
        )
        db.add(verif_log)
        await db.commit()

        # Build detail structures
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

        return VerificationResponse(
            verification_id=verification_id,
            credential_public_id=credential_public_id,
            outcome=outcome,
            reason_code=reason_code,
            message=message,
            timestamp=now,
            factors=VerificationFactorResult(
                record_found=True,
                payload_integrity_valid=payload_integrity_valid,
                issuer_authenticated=issuer_authenticated,
                revocation_checked=True,
                is_revoked=is_revoked,
            ),
            credential_details=cred_details,
            revocation_details=rev_details,
        )
