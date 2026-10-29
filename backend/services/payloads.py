"""Canonical credential payload builder.

The ONLY place that defines the structure of a credential payload. The
synthetic generator, the anomaly fixtures, and IssuanceService all call
`build_credential_payload`, and the canonical SHA-256 hash and Ed25519
signature are always computed over its output.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Union


def build_credential_payload(
    *,
    credential_id: str,
    issued_at: datetime,
    completion_timestamp: datetime,
    learner_id: str,
    learner_name: str,
    learner_email: str,
    course_code: str,
    course_title: str,
    assessment_score: Union[Decimal, float],
    assessment_status: str,
    issuer_id: str,
    issuer_name: str,
) -> dict[str, Any]:
    """Return the nested credential claims payload that gets hashed and signed."""
    return {
        "credential_id": credential_id,
        "course": {
            "code": course_code,
            "title": course_title,
        },
        "learner": {
            "id": learner_id,
            "name": learner_name,
            "email": learner_email,
        },
        "assessment": {
            "score": float(assessment_score),
            "status": assessment_status,
        },
        "issued_at": issued_at.isoformat(),
        "completion_timestamp": completion_timestamp.isoformat(),
        "issuer": {
            "id": issuer_id,
            "name": issuer_name,
        },
    }

