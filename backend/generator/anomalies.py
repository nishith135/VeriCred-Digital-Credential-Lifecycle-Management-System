"""Mandatory Anomaly Fixtures and Segregated Ground-Truth Generator.

Enforces MASTER_SPEC Section 11.5:
1. Credential issued before completion (INVALID_ISSUANCE).
2. Duplicate credential ID in malformed import fixture.
3. Revoked credential verifies as active in stale cache (REVOKED).
4. Altered payload hash undetected by naive check (TAMPERED).

Ground-truth labels are strictly segregated in a dedicated dataset and are never
consumed by operational verification logic.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import random

from backend.core.security import (
    compute_payload_hash,
    generate_deterministic_ed25519_keypair,
    sign_payload_hash,
)


@dataclass
class GroundTruthRecord:
    case_id: str
    issue_type: str
    target_identifier: str
    expected_outcome: str
    reason: str
    severity: str
    category: str
    fixture_details: Dict[str, Any]


def generate_anomaly_fixtures(
    seed: int = 20261022,
    base_reference_time: Optional[datetime] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate the four mandatory anomaly fixtures along with segregated ground-truth labels.
    
    Returns:
        (anomaly_fixtures, ground_truth_records)
    """
    rng = random.Random(seed)
    ref_time = base_reference_time or datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
    
    # Generate dedicated anomaly keypair deterministically: returns (private_pem, public_pem)
    anomaly_priv_pem, anomaly_pub_pem = generate_deterministic_ed25519_keypair(
        f"anomaly_seed_{seed}".encode("utf-8")
    )
    
    fixtures: List[Dict[str, Any]] = []
    ground_truth: List[GroundTruthRecord] = []
    
    # -------------------------------------------------------------------------
    # Anomaly 1: Credential issued before completion / Ineligible completion
    # -------------------------------------------------------------------------
    t_completed = ref_time - timedelta(days=5)
    t_premature_issued = ref_time - timedelta(days=10)  # 5 days before completion!
    
    claims_1 = {
        "credential_id": "CRED-ANOMALY-001",
        "course": {"code": "CS-ANOMALY-101", "title": "Advanced Algorithmic Integrity"},
        "learner": {"id": "LRN-ANOMALY-001", "name": "Alice Premature"},
        "assessment": {"score": 58.50, "status": "IN_PROGRESS"},  # Ineligible score and status
        "issued_at": t_premature_issued.isoformat(),
        "completion_timestamp": t_completed.isoformat(),
        "issuer": {"id": "ISS-ANOMALY-001", "name": "Acme Cyber Academy"},
    }
    hash_1 = compute_payload_hash(claims_1)
    sig_1 = sign_payload_hash(anomaly_priv_pem, hash_1)
    
    fixture_1 = {
        "case_id": "CASE-ANOMALY-001",
        "issue_type": "PREMATURE_ISSUANCE",
        "public_id": "CRED-ANOMALY-001",
        "completion_timestamp": t_completed.isoformat(),
        "issued_at": t_premature_issued.isoformat(),
        "assessment_score": 58.50,
        "completion_status": "IN_PROGRESS",
        "payload_hash": hash_1,
        "signature": sig_1,
        "payload_snapshot": claims_1,
        "issuer_public_key_pem": anomaly_pub_pem,
    }
    fixtures.append(fixture_1)
    ground_truth.append(
        GroundTruthRecord(
            case_id="CASE-ANOMALY-001",
            issue_type="PREMATURE_ISSUANCE",
            target_identifier="CRED-ANOMALY-001",
            expected_outcome="INVALID_ISSUANCE",
            reason="Issue timestamp precedes completion timestamp and assessment score (58.50%) is below 80.00% threshold.",
            severity="CRITICAL",
            category="ACADEMIC_INTEGRITY",
            fixture_details={"issued_at": t_premature_issued.isoformat(), "completed_at": t_completed.isoformat()},
        )
    )

    # -------------------------------------------------------------------------
    # Anomaly 2: Duplicate Credential ID in Malformed Import Dataset
    # -------------------------------------------------------------------------
    dup_id = "CRED-ANOMALY-DUP-002"
    claims_2a = {
        "credential_id": dup_id,
        "course": {"code": "MATH-201", "title": "Discrete Math"},
        "learner": {"id": "LRN-002A", "name": "Bob Original"},
        "assessment": {"score": 92.00, "status": "COMPLETED"},
        "issued_at": (ref_time - timedelta(days=20)).isoformat(),
        "issuer": {"id": "ISS-ANOMALY-001", "name": "Acme Cyber Academy"},
    }
    claims_2b = {
        "credential_id": dup_id,
        "course": {"code": "MATH-201", "title": "Discrete Math"},
        "learner": {"id": "LRN-002B", "name": "Charlie Duplicate"},
        "assessment": {"score": 88.00, "status": "COMPLETED"},
        "issued_at": (ref_time - timedelta(days=15)).isoformat(),
        "issuer": {"id": "ISS-ANOMALY-001", "name": "Acme Cyber Academy"},
    }
    
    hash_2a = compute_payload_hash(claims_2a)
    hash_2b = compute_payload_hash(claims_2b)
    fixture_2 = {
        "case_id": "CASE-ANOMALY-002",
        "issue_type": "DUPLICATE_CREDENTIAL_ID",
        "public_id": dup_id,
        "record_a": {
            "public_id": dup_id,
            "learner_name": "Bob Original",
            "payload_snapshot": claims_2a,
            "payload_hash": hash_2a,
            "signature": sign_payload_hash(anomaly_priv_pem, hash_2a),
        },
        "record_b": {
            "public_id": dup_id,
            "learner_name": "Charlie Duplicate",
            "payload_snapshot": claims_2b,
            "payload_hash": hash_2b,
            "signature": sign_payload_hash(anomaly_priv_pem, hash_2b),
        },
    }
    fixtures.append(fixture_2)
    ground_truth.append(
        GroundTruthRecord(
            case_id="CASE-ANOMALY-002",
            issue_type="DUPLICATE_CREDENTIAL_ID",
            target_identifier=dup_id,
            expected_outcome="REJECTED_DUPLICATE",
            reason="Two distinct completion records claim the identical public credential identifier in malformed batch.",
            severity="HIGH",
            category="DATA_INTEGRITY",
            fixture_details={"duplicate_id": dup_id, "competing_records": 2},
        )
    )

    # -------------------------------------------------------------------------
    # Anomaly 3: Revoked Credential Verifies as Active in Stale Cache
    # -------------------------------------------------------------------------
    cred_3_id = "CRED-ANOMALY-REV-003"
    t_revoked = ref_time - timedelta(days=3)
    claims_3 = {
        "credential_id": cred_3_id,
        "course": {"code": "SEC-301", "title": "Network Defense"},
        "learner": {"id": "LRN-003", "name": "David Revoked"},
        "assessment": {"score": 85.00, "status": "COMPLETED"},
        "issued_at": (ref_time - timedelta(days=30)).isoformat(),
        "issuer": {"id": "ISS-ANOMALY-001", "name": "Acme Cyber Academy"},
    }
    hash_3 = compute_payload_hash(claims_3)
    sig_3 = sign_payload_hash(anomaly_priv_pem, hash_3)
    
    fixture_3 = {
        "case_id": "CASE-ANOMALY-003",
        "issue_type": "REVOKED_VERIFIES_AS_ACTIVE",
        "public_id": cred_3_id,
        "revocation_record": {
            "revoked_at": t_revoked.isoformat(),
            "reason_code": "ACADEMIC_MISCONDUCT",
            "revoked_by": "DEAN-OFFICE",
        },
        "stale_cache_claim": "VALID",
        "payload_snapshot": claims_3,
        "payload_hash": hash_3,
        "signature": sig_3,
        "issuer_public_key_pem": anomaly_pub_pem,
    }
    fixtures.append(fixture_3)
    ground_truth.append(
        GroundTruthRecord(
            case_id="CASE-ANOMALY-003",
            issue_type="REVOKED_VERIFIES_AS_ACTIVE",
            target_identifier=cred_3_id,
            expected_outcome="REVOKED",
            reason="Persistent revocation record exists. Buggy or stale client cache erroneously presents status as ACTIVE.",
            severity="CRITICAL",
            category="LIFECYCLE_STATE",
            fixture_details={"stale_claim": "VALID", "actual_state": "REVOKED", "reason_code": "ACADEMIC_MISCONDUCT"},
        )
    )

    # -------------------------------------------------------------------------
    # Anomaly 4: Altered Payload Undetected by Naive String Comparison
    # -------------------------------------------------------------------------
    cred_4_id = "CRED-ANOMALY-TAMPER-004"
    claims_4_original = {
        "credential_id": cred_4_id,
        "course": {"code": "DATA-401", "title": "Data Engineering"},
        "learner": {"id": "LRN-004", "name": "Eve Tampered"},
        "assessment": {"score": 81.00, "grade": "B", "status": "COMPLETED"},
        "issued_at": (ref_time - timedelta(days=12)).isoformat(),
        "issuer": {"id": "ISS-ANOMALY-001", "name": "Acme Cyber Academy"},
    }
    hash_4_original = compute_payload_hash(claims_4_original)
    sig_4_original = sign_payload_hash(anomaly_priv_pem, hash_4_original)
    
    # Tampered payload has grade and score elevated, but retains original hash and signature
    claims_4_altered = dict(claims_4_original)
    claims_4_altered["assessment"] = {"score": 99.50, "grade": "A+", "status": "COMPLETED"}
    
    fixture_4 = {
        "case_id": "CASE-ANOMALY-004",
        "issue_type": "ALTERED_PAYLOAD_TAMPERING",
        "public_id": cred_4_id,
        "original_payload": claims_4_original,
        "tampered_payload": claims_4_altered,
        "signed_payload_hash": hash_4_original,
        "signature": sig_4_original,
        "issuer_public_key_pem": anomaly_pub_pem,
    }
    fixtures.append(fixture_4)
    ground_truth.append(
        GroundTruthRecord(
            case_id="CASE-ANOMALY-004",
            issue_type="ALTERED_PAYLOAD_TAMPERING",
            target_identifier=cred_4_id,
            expected_outcome="TAMPERED",
            reason="Payload attributes modified from score 81.00 (B) to 99.50 (A+). Naive text search matches ID, but canonical SHA-256 digest detects tampering.",
            severity="CRITICAL",
            category="CRYPTOGRAPHIC_INTEGRITY",
            fixture_details={"original_score": 81.0, "altered_score": 99.5},
        )
    )
    
    gt_dicts = [asdict(gt) for gt in ground_truth]
    return fixtures, gt_dicts


def save_ground_truth_dataset(ground_truth_records: List[Dict[str, Any]], output_path: Path) -> None:
    """Save the segregated ground truth records to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth_records, f, indent=2, ensure_ascii=False)
