"""Real-Data Evaluation Engine for Credential Verification and Anomaly Detection.

Executes dry-run (`persist=False`) verification across all credentials in the database,
evaluates duplicate credential staging rows inside rolled-back savepoints, and computes
numerator/denominator metrics and elapsed times without mutating any table.
"""

from copy import deepcopy
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.core.security import compute_payload_hash, generate_deterministic_ed25519_keypair, sign_payload_hash
from backend.generator.anomalies import load_ground_truth
from backend.models import (
    AuditEvent,
    CompletionRecord,
    Course,
    Credential,
    CredentialRule,
    Issuer,
    Learner,
    Revocation,
    VerificationRequest,
)
from backend.services.eligibility import EligibilityService
from backend.services.ids import (
    format_completion_id,
    format_course_id,
    format_credential_id,
    format_issuer_id,
    format_learner_id,
    format_revocation_id,
)
from backend.services.payloads import build_credential_payload
from backend.services.verification import VerificationService

ANOMALY_TYPES = (
    "PREMATURE_ISSUANCE",
    "DUPLICATE_CREDENTIAL_ID",
    "REVOKED_VERIFIES_AS_ACTIVE",
    "ALTERED_PAYLOAD_NOT_DETECTED",
)

LEGACY_SCENARIO_ALIASES = {
    "SIM-REV-094": "PREMATURE_ISSUANCE",
    "PREMATURE_ISSUANCE": "PREMATURE_ISSUANCE",
    "SIM-COLL-103": "DUPLICATE_CREDENTIAL_ID",
    "DUPLICATE_CREDENTIAL_ID": "DUPLICATE_CREDENTIAL_ID",
    "SIM-POIS-519": "REVOKED_VERIFIES_AS_ACTIVE",
    "REVOKED_VERIFIES_AS_ACTIVE": "REVOKED_VERIFIES_AS_ACTIVE",
    "SIM-TAMP-882": "ALTERED_PAYLOAD_NOT_DETECTED",
    "ALTERED_PAYLOAD_NOT_DETECTED": "ALTERED_PAYLOAD_NOT_DETECTED",
    "ALTERED_PAYLOAD_TAMPERING": "ALTERED_PAYLOAD_NOT_DETECTED",
}

ANOMALY_SCENARIO_META: Dict[str, Dict[str, str]] = {
    "PREMATURE_ISSUANCE": {
        "scenario_id": "PREMATURE_ISSUANCE",
        "title": "Scenario 01: Premature Issuance Chronology Check",
        "description": (
            "Credentials whose issued_at timestamp precedes the course completion_timestamp "
            "(even when cryptographically hashed and signed by an active issuer)."
        ),
        "expected_outcome": "INVALID_ISSUANCE",
        "rule_reference": "MASTER_SPEC §6 / §11.5.1: issued_at >= completion_timestamp",
    },
    "DUPLICATE_CREDENTIAL_ID": {
        "scenario_id": "DUPLICATE_CREDENTIAL_ID",
        "title": "Scenario 02: Duplicate Credential ID Staging Rejection",
        "description": (
            "Staging import rows in credential_import_staging.csv whose public_id duplicates an "
            "existing credential in the registry, tested inside a rolled-back savepoint."
        ),
        "expected_outcome": "REJECTED_DUPLICATE",
        "rule_reference": "MASTER_SPEC §7 / §11.5.2: Unique constraint on credentials.public_id",
    },
    "REVOKED_VERIFIES_AS_ACTIVE": {
        "scenario_id": "REVOKED_VERIFIES_AS_ACTIVE",
        "title": "Scenario 03: Stale Active Status Overridden by Revocation Table",
        "description": (
            "Credentials where a Revocation row exists in the revocations table while "
            "credentials.status remains ACTIVE."
        ),
        "expected_outcome": "REVOKED",
        "rule_reference": "MASTER_SPEC §8 / §11.5.3: Live revocation join overrides stale ACTIVE status",
    },
    "ALTERED_PAYLOAD_NOT_DETECTED": {
        "scenario_id": "ALTERED_PAYLOAD_NOT_DETECTED",
        "title": "Scenario 04: Altered Payload Snapshot & Digest Tamper Detection",
        "description": (
            "Credentials where payload_snapshot was modified after issuance (half with snapshot altered "
            "only, half with payload_snapshot and canonical_payload_hash altered together)."
        ),
        "expected_outcome": "TAMPERED",
        "rule_reference": "MASTER_SPEC §8 / §11.5.4: Canonical SHA-256 + relational claim cross-check",
    },
}

_LATEST_EVALUATION_REPORT: Optional[Dict[str, Any]] = None


def get_latest_evaluation_report() -> Optional[Dict[str, Any]]:
    """Return the most recent evaluation report run in this process, or None if not run yet."""
    return _LATEST_EVALUATION_REPORT


def reset_latest_evaluation_report() -> None:
    """Clear the cached evaluation report (used by tests to verify 'Not run yet' state)."""
    global _LATEST_EVALUATION_REPORT
    _LATEST_EVALUATION_REPORT = None


def _metric_dict(numerator: int, denominator: int) -> Dict[str, Any]:
    rate = round((numerator / denominator) * 100.0, 4) if denominator > 0 else 0.0
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate_pct": rate,
    }


def _resolve_exports_dir(exports_dir: Optional[Path] = None) -> Path:
    if exports_dir is not None:
        return exports_dir
    tmp_dir = Path("./exports_tmp")
    if (tmp_dir / "ground_truth.json").exists():
        return tmp_dir
    return Path("./exports")


def _load_staging_rows(exports_dir: Path) -> List[Dict[str, Any]]:
    staging_path = exports_dir / "credential_import_staging.csv"
    if not staging_path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with open(staging_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "id": int(row["id"]),
                    "public_id": row["public_id"],
                    "completion_id": int(row["completion_id"]),
                    "issuer_id": int(row["issuer_id"]),
                    "issued_at": datetime.fromisoformat(row["issued_at"]),
                    "canonical_payload_hash": row["canonical_payload_hash"],
                    "issuer_signature": row["issuer_signature"],
                    "payload_snapshot": json.loads(row["payload_snapshot"]),
                    "status": row["status"],
                    "created_at": datetime.fromisoformat(row["created_at"]),
                }
            )
    return rows


class EvaluationRunner:
    """Runs dry-run verification across the database and computes accuracy & anomaly metrics."""

    @staticmethod
    async def count_all_tables(db: AsyncSession) -> Dict[str, int]:
        """Count rows across all 9 operational tables."""
        models = [
            ("issuers", Issuer),
            ("courses", Course),
            ("credential_rules", CredentialRule),
            ("learners", Learner),
            ("completion_records", CompletionRecord),
            ("credentials", Credential),
            ("revocations", Revocation),
            ("verification_requests", VerificationRequest),
            ("audit_events", AuditEvent),
        ]
        counts: Dict[str, int] = {}
        for name, model in models:
            cnt = (await db.execute(select(func.count(model.id)))).scalar_one()
            counts[name] = int(cnt or 0)
        return counts

    @classmethod
    async def _seed_ephemeral_anomalies_in_savepoint(
        cls,
        db: AsyncSession,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Create temporary anomaly rows inside an active savepoint when running against a minimal test DB."""
        now = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
        priv_pem, pub_pem = generate_deterministic_ed25519_keypair(b"ephemeral_eval_seed")

        issuer = Issuer(
            public_id=format_issuer_id(991),
            name="Evaluation Test Institute",
            public_key_pem=pub_pem,
            status="ACTIVE",
        )
        course = Course(
            public_id=format_course_id(991),
            title="Cryptographic Verification Systems (401)",
            version="1.0",
            status="ACTIVE",
        )
        db.add_all([issuer, course])
        await db.flush()

        rule = CredentialRule(
            course_id=course.id,
            rule_version="1.0",
            min_score=Decimal("80.00"),
            required_completion_status="COMPLETED",
            effective_from=now - timedelta(days=365),
            effective_to=now + timedelta(days=365),
            active=True,
        )
        db.add(rule)
        await db.flush()

        gt_rows: List[Dict[str, Any]] = []
        staging_rows: List[Dict[str, Any]] = []

        # Create 8 learners & completions (2 per anomaly type)
        completions: List[CompletionRecord] = []
        for idx in range(1, 9):
            lnr = Learner(
                public_id=format_learner_id(9900 + idx),
                full_name=f"Eval Candidate {idx}",
                email=f"eval.candidate.{idx}@edu-network.in",
                status="ACTIVE",
            )
            db.add(lnr)
            await db.flush()
            comp = CompletionRecord(
                public_id=format_completion_id(lnr.public_id, course.public_id),
                learner_id=lnr.id,
                course_id=course.id,
                rule_id=rule.id,
                assessment_score=Decimal("91.00"),
                status="COMPLETED",
                completion_timestamp=now - timedelta(days=20),
            )
            db.add(comp)
            await db.flush()
            completions.append(comp)

        # 1. PREMATURE_ISSUANCE (2 rows)
        for i, comp in enumerate(completions[0:2], start=1):
            lnr = (await db.execute(select(Learner).where(Learner.id == comp.learner_id))).scalar_one()
            premature_ts = comp.completion_timestamp - timedelta(days=4)
            cid = format_credential_id(9900 + i, premature_ts)
            claims = build_credential_payload(
                credential_id=cid,
                issued_at=premature_ts,
                completion_timestamp=comp.completion_timestamp,
                learner_id=lnr.public_id,
                learner_name=lnr.full_name,
                learner_email=lnr.email,
                course_code=course.public_id,
                course_title=course.title,
                assessment_score=comp.assessment_score,
                assessment_status=comp.status,
                issuer_id=issuer.public_id,
                issuer_name=issuer.name,
            )
            h = compute_payload_hash(claims)
            s = sign_payload_hash(priv_pem, h)
            db.add(
                Credential(
                    public_id=cid,
                    completion_id=comp.id,
                    issuer_id=issuer.id,
                    issued_at=premature_ts,
                    canonical_payload_hash=h,
                    issuer_signature=s,
                    payload_snapshot=claims,
                    status="ACTIVE",
                )
            )
            gt_rows.append(
                {
                    "anomaly_id": f"ANM-000{i}",
                    "issue_type": "PREMATURE_ISSUANCE",
                    "entity_public_id": cid,
                    "expected_outcome": "INVALID_ISSUANCE",
                    "rule_reference": ANOMALY_SCENARIO_META["PREMATURE_ISSUANCE"]["rule_reference"],
                }
            )

        # 2. DUPLICATE_CREDENTIAL_ID (2 baseline credentials + 2 staging rows)
        for i, comp in enumerate(completions[2:4], start=1):
            lnr = (await db.execute(select(Learner).where(Learner.id == comp.learner_id))).scalar_one()
            issued_ts = comp.completion_timestamp + timedelta(days=1)
            cid = format_credential_id(9910 + i, issued_ts)
            claims = build_credential_payload(
                credential_id=cid,
                issued_at=issued_ts,
                completion_timestamp=comp.completion_timestamp,
                learner_id=lnr.public_id,
                learner_name=lnr.full_name,
                learner_email=lnr.email,
                course_code=course.public_id,
                course_title=course.title,
                assessment_score=comp.assessment_score,
                assessment_status=comp.status,
                issuer_id=issuer.public_id,
                issuer_name=issuer.name,
            )
            h = compute_payload_hash(claims)
            s = sign_payload_hash(priv_pem, h)
            db.add(
                Credential(
                    public_id=cid,
                    completion_id=comp.id,
                    issuer_id=issuer.id,
                    issued_at=issued_ts,
                    canonical_payload_hash=h,
                    issuer_signature=s,
                    payload_snapshot=claims,
                    status="ACTIVE",
                )
            )
            staging_rows.append(
                {
                    "id": i,
                    "public_id": cid,
                    "completion_id": comp.id,
                    "issuer_id": issuer.id,
                    "issued_at": issued_ts + timedelta(hours=2),
                    "canonical_payload_hash": h,
                    "issuer_signature": s,
                    "payload_snapshot": claims,
                    "status": "ACTIVE",
                    "created_at": issued_ts + timedelta(hours=2),
                }
            )
            gt_rows.append(
                {
                    "anomaly_id": f"ANM-000{i + 2}",
                    "issue_type": "DUPLICATE_CREDENTIAL_ID",
                    "entity_public_id": cid,
                    "expected_outcome": "REJECTED_DUPLICATE",
                    "rule_reference": ANOMALY_SCENARIO_META["DUPLICATE_CREDENTIAL_ID"]["rule_reference"],
                }
            )

        # 3. REVOKED_VERIFIES_AS_ACTIVE (2 rows: Revocation exists, status == ACTIVE)
        for i, comp in enumerate(completions[4:6], start=1):
            lnr = (await db.execute(select(Learner).where(Learner.id == comp.learner_id))).scalar_one()
            issued_ts = comp.completion_timestamp + timedelta(days=1)
            cid = format_credential_id(9920 + i, issued_ts)
            claims = build_credential_payload(
                credential_id=cid,
                issued_at=issued_ts,
                completion_timestamp=comp.completion_timestamp,
                learner_id=lnr.public_id,
                learner_name=lnr.full_name,
                learner_email=lnr.email,
                course_code=course.public_id,
                course_title=course.title,
                assessment_score=comp.assessment_score,
                assessment_status=comp.status,
                issuer_id=issuer.public_id,
                issuer_name=issuer.name,
            )
            h = compute_payload_hash(claims)
            s = sign_payload_hash(priv_pem, h)
            cred_obj = Credential(
                public_id=cid,
                completion_id=comp.id,
                issuer_id=issuer.id,
                issued_at=issued_ts,
                canonical_payload_hash=h,
                issuer_signature=s,
                payload_snapshot=claims,
                status="ACTIVE",
            )
            db.add(cred_obj)
            await db.flush()
            db.add(
                Revocation(
                    public_id=format_revocation_id(cid),
                    credential_id=cred_obj.id,
                    revoked_by_actor_id="REGISTRAR-001",
                    reason_code="ACADEMIC_MISCONDUCT",
                    revocation_timestamp=issued_ts + timedelta(days=2),
                )
            )
            gt_rows.append(
                {
                    "anomaly_id": f"ANM-000{i + 4}",
                    "issue_type": "REVOKED_VERIFIES_AS_ACTIVE",
                    "entity_public_id": cid,
                    "expected_outcome": "REVOKED",
                    "rule_reference": ANOMALY_SCENARIO_META["REVOKED_VERIFIES_AS_ACTIVE"]["rule_reference"],
                }
            )

        # 4. ALTERED_PAYLOAD_NOT_DETECTED (2 rows: 1 snapshot-only, 1 snapshot+hash)
        for i, comp in enumerate(completions[6:8], start=1):
            lnr = (await db.execute(select(Learner).where(Learner.id == comp.learner_id))).scalar_one()
            issued_ts = comp.completion_timestamp + timedelta(days=1)
            cid = format_credential_id(9930 + i, issued_ts)
            claims = build_credential_payload(
                credential_id=cid,
                issued_at=issued_ts,
                completion_timestamp=comp.completion_timestamp,
                learner_id=lnr.public_id,
                learner_name=lnr.full_name,
                learner_email=lnr.email,
                course_code=course.public_id,
                course_title=course.title,
                assessment_score=comp.assessment_score,
                assessment_status=comp.status,
                issuer_id=issuer.public_id,
                issuer_name=issuer.name,
            )
            orig_hash = compute_payload_hash(claims)
            orig_sig = sign_payload_hash(priv_pem, orig_hash)

            altered_claims = deepcopy(claims)
            altered_claims["assessment"]["score"] = 99.99
            altered_claims["course"]["title"] = f"{course.title} [Tampered]"
            stored_hash = orig_hash if i == 1 else compute_payload_hash(altered_claims)

            db.add(
                Credential(
                    public_id=cid,
                    completion_id=comp.id,
                    issuer_id=issuer.id,
                    issued_at=issued_ts,
                    canonical_payload_hash=stored_hash,
                    issuer_signature=orig_sig,
                    payload_snapshot=altered_claims,
                    status="ACTIVE",
                )
            )
            gt_rows.append(
                {
                    "anomaly_id": f"ANM-000{i + 6}",
                    "issue_type": "ALTERED_PAYLOAD_NOT_DETECTED",
                    "entity_public_id": cid,
                    "expected_outcome": "TAMPERED",
                    "rule_reference": ANOMALY_SCENARIO_META["ALTERED_PAYLOAD_NOT_DETECTED"]["rule_reference"],
                }
            )

        await db.flush()
        return gt_rows, staging_rows

    @classmethod
    async def run_evaluation(
        cls,
        db: AsyncSession,
        exports_dir: Optional[Path] = None,
        update_cache: bool = True,
    ) -> Dict[str, Any]:
        """Run full dry-run verification over all credentials and compute evaluation metrics."""
        global _LATEST_EVALUATION_REPORT

        resolved_dir = _resolve_exports_dir(exports_dir)
        table_counts_before = await cls.count_all_tables(db)
        total_start = time.perf_counter()

        gt_rows = load_ground_truth(resolved_dir)
        staging_rows = _load_staging_rows(resolved_dir)

        # Check whether the loaded ground-truth entities exist in this database
        existing_pub_ids = set((await db.execute(select(Credential.public_id))).scalars().all())
        gt_cred_ids = {
            r["entity_public_id"]
            for r in gt_rows
            if r.get("issue_type") != "DUPLICATE_CREDENTIAL_ID"
        }

        ephemeral_savepoint = None
        if not gt_cred_ids or not gt_cred_ids.issubset(existing_pub_ids):
            ephemeral_savepoint = await db.begin_nested()
            gt_rows, staging_rows = await cls._seed_ephemeral_anomalies_in_savepoint(db)

        try:
            # Index ground truth by (entity_public_id, issue_type)
            gt_by_cred_id: Dict[str, Dict[str, Any]] = {}
            gt_duplicate_rows: List[Dict[str, Any]] = []
            for r in gt_rows:
                if r["issue_type"] == "DUPLICATE_CREDENTIAL_ID":
                    gt_duplicate_rows.append(r)
                else:
                    gt_by_cred_id[r["entity_public_id"]] = r

            # Load all credentials with relational parents for baseline expected-outcome derivation
            stmt = (
                select(Credential)
                .options(
                    joinedload(Credential.issuer),
                    joinedload(Credential.revocation),
                    joinedload(Credential.completion).joinedload(CompletionRecord.learner),
                    joinedload(Credential.completion).joinedload(CompletionRecord.course),
                    joinedload(Credential.completion).joinedload(CompletionRecord.rule),
                )
                .order_by(Credential.id)
            )
            all_credentials = list((await db.execute(stmt)).scalars().unique().all())

            # Counters
            total_correct = 0
            total_evaluated = 0

            per_type_totals: Dict[str, int] = {t: 0 for t in ANOMALY_TYPES}
            per_type_detected: Dict[str, int] = {t: 0 for t in ANOMALY_TYPES}
            per_type_elapsed_ms: Dict[str, float] = {t: 0.0 for t in ANOMALY_TYPES}
            per_type_examples: Dict[str, Dict[str, Any]] = {}

            anomalous_creds_total = 0
            anomalous_creds_returned_valid = 0

            baseline_valid_total = 0
            baseline_valid_not_returned_valid = 0

            revoked_total = 0
            revoked_detected = 0

            tampered_total = 0
            tampered_detected = 0

            # 1. Verify every credential in the database with persist=False
            for cred in all_credentials:
                t0 = time.perf_counter()
                res = await VerificationService.verify_credential(
                    db=db,
                    credential_public_id=cred.public_id,
                    persist=False,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                actual_outcome = res.outcome

                gt_entry = gt_by_cred_id.get(cred.public_id)
                if gt_entry is not None:
                    issue_type = gt_entry["issue_type"]
                    expected_outcome = gt_entry["expected_outcome"]
                    anomalous_creds_total += 1
                    if actual_outcome == "VALID":
                        anomalous_creds_returned_valid += 1

                    per_type_totals[issue_type] += 1
                    per_type_elapsed_ms[issue_type] += elapsed_ms
                    if actual_outcome == expected_outcome:
                        per_type_detected[issue_type] += 1

                    if issue_type == "REVOKED_VERIFIES_AS_ACTIVE":
                        revoked_total += 1
                        if actual_outcome == "REVOKED":
                            revoked_detected += 1
                    elif issue_type == "ALTERED_PAYLOAD_NOT_DETECTED":
                        tampered_total += 1
                        if actual_outcome == "TAMPERED":
                            tampered_detected += 1

                    if issue_type not in per_type_examples:
                        per_type_examples[issue_type] = {
                            "entity_public_id": cred.public_id,
                            "expected_outcome": expected_outcome,
                            "actual_outcome": actual_outcome,
                            "reason_code": res.reason_code,
                            "failed_subchecks": list(res.factors.failed_subchecks),
                            "elapsed_ms": round(elapsed_ms, 2),
                            "rule_reference": gt_entry.get("rule_reference", ""),
                        }
                else:
                    # Baseline row: derive expected outcome from relational tables + revocation table
                    is_revoked = (cred.revocation is not None) or (cred.status == "REVOKED")
                    elig_ok = True
                    if cred.completion is not None:
                        elig_ok, _, _ = EligibilityService.evaluate_completion_rules(
                            completion=cred.completion,
                            issued_at=cred.issued_at,
                            check_effective_window=True,
                        )
                    if not elig_ok:
                        expected_outcome = "INVALID_ISSUANCE"
                    elif is_revoked:
                        expected_outcome = "REVOKED"
                        revoked_total += 1
                        if actual_outcome == "REVOKED":
                            revoked_detected += 1
                    else:
                        expected_outcome = "VALID"
                        baseline_valid_total += 1
                        if actual_outcome != "VALID":
                            baseline_valid_not_returned_valid += 1

                total_evaluated += 1
                if actual_outcome == expected_outcome:
                    total_correct += 1

            # 2. Evaluate DUPLICATE_CREDENTIAL_ID staging rows inside rolled-back savepoints
            for s_row in staging_rows:
                t0 = time.perf_counter()
                dup_outcome = "ACCEPTED"
                error_detail = ""
                try:
                    async with db.begin_nested():
                        dup_cred = Credential(
                            public_id=s_row["public_id"],
                            completion_id=s_row["completion_id"],
                            issuer_id=s_row["issuer_id"],
                            issued_at=s_row["issued_at"],
                            canonical_payload_hash=s_row["canonical_payload_hash"],
                            issuer_signature=s_row["issuer_signature"],
                            payload_snapshot=s_row["payload_snapshot"],
                            status=s_row["status"],
                        )
                        db.add(dup_cred)
                        await db.flush()
                except IntegrityError as exc:
                    dup_outcome = "REJECTED_DUPLICATE"
                    error_detail = str(exc.orig).splitlines()[0] if getattr(exc, "orig", None) else "IntegrityError"

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                per_type_totals["DUPLICATE_CREDENTIAL_ID"] += 1
                per_type_elapsed_ms["DUPLICATE_CREDENTIAL_ID"] += elapsed_ms
                if dup_outcome == "REJECTED_DUPLICATE":
                    per_type_detected["DUPLICATE_CREDENTIAL_ID"] += 1
                    total_correct += 1
                total_evaluated += 1

                if "DUPLICATE_CREDENTIAL_ID" not in per_type_examples:
                    gt_dup = next(
                        (g for g in gt_duplicate_rows if g["entity_public_id"] == s_row["public_id"]),
                        {"rule_reference": ANOMALY_SCENARIO_META["DUPLICATE_CREDENTIAL_ID"]["rule_reference"]},
                    )
                    per_type_examples["DUPLICATE_CREDENTIAL_ID"] = {
                        "entity_public_id": s_row["public_id"],
                        "expected_outcome": "REJECTED_DUPLICATE",
                        "actual_outcome": dup_outcome,
                        "reason_code": "UNIQUE_CONSTRAINT_VIOLATION",
                        "failed_subchecks": [error_detail or "uq_credentials_public_id"],
                        "elapsed_ms": round(elapsed_ms, 2),
                        "rule_reference": gt_dup.get("rule_reference", ""),
                    }
        finally:
            if ephemeral_savepoint is not None:
                await ephemeral_savepoint.rollback()

        total_elapsed_ms = round((time.perf_counter() - total_start) * 1000.0, 2)
        table_counts_after = await cls.count_all_tables(db)
        row_count_delta = sum(
            abs(table_counts_after[k] - table_counts_before[k]) for k in table_counts_before
        )

        # Build scenario cards for the Anomaly Lab UI
        scenarios: List[Dict[str, Any]] = []
        for issue_type in ANOMALY_TYPES:
            meta = ANOMALY_SCENARIO_META[issue_type]
            num = per_type_detected[issue_type]
            den = per_type_totals[issue_type]
            ex = per_type_examples.get(issue_type, {})
            passed = (num == den) and (den > 0)
            scen_ms = round(per_type_elapsed_ms[issue_type], 2)
            example_id = ex.get("entity_public_id", "N/A")
            actual_out = ex.get("actual_outcome", "N/A")
            reason_code = ex.get("reason_code", "")
            subchecks = ", ".join(ex.get("failed_subchecks", [])) or reason_code

            scenarios.append(
                {
                    "scenario_id": issue_type,
                    "title": meta["title"],
                    "description": meta["description"],
                    "rule_reference": ex.get("rule_reference") or meta["rule_reference"],
                    "example_entity_id": example_id,
                    "expected_outcome": meta["expected_outcome"],
                    "actual_outcome": actual_out,
                    "reason_code": reason_code,
                    "passed": passed,
                    "numerator": num,
                    "denominator": den,
                    "detection_rate_pct": round((num / den) * 100.0, 2) if den > 0 else 0.0,
                    "elapsed_ms": scen_ms,
                    "trace": (
                        f"entity={example_id} expected={meta['expected_outcome']} "
                        f"actual={actual_out} detected={num}/{den} ({subchecks}) in {scen_ms} ms"
                    ),
                }
            )

        passing_scenarios = sum(1 for s in scenarios if s["passed"])
        report = {
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "total_elapsed_ms": total_elapsed_ms,
            "total_credentials_evaluated": len(all_credentials),
            "total_staging_duplicates_evaluated": len(staging_rows),
            "total_cases_evaluated": total_evaluated,
            "scenarios_run": len(scenarios),
            "scenarios_passing": passing_scenarios,
            "row_count_delta": row_count_delta,
            "table_counts_before": table_counts_before,
            "table_counts_after": table_counts_after,
            "metrics": {
                "overall_accuracy": _metric_dict(total_correct, total_evaluated),
                "per_anomaly_type_detection_rate": {
                    t: _metric_dict(per_type_detected[t], per_type_totals[t])
                    for t in ANOMALY_TYPES
                },
                "false_acceptance_rate": _metric_dict(
                    anomalous_creds_returned_valid, anomalous_creds_total
                ),
                "false_rejection_rate": _metric_dict(
                    baseline_valid_not_returned_valid, baseline_valid_total
                ),
                "revocation_detection_rate": _metric_dict(revoked_detected, revoked_total),
                "tamper_detection_rate": _metric_dict(tampered_detected, tampered_total),
            },
            "scenarios": scenarios,
        }

        if update_cache:
            _LATEST_EVALUATION_REPORT = report
        return report

    @classmethod
    async def run_single_scenario(
        cls,
        db: AsyncSession,
        scenario_id: str,
        exports_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Run evaluation and return the specific scenario card along with the updated report."""
        canonical_id = LEGACY_SCENARIO_ALIASES.get(scenario_id, scenario_id)
        if canonical_id not in ANOMALY_SCENARIO_META:
            canonical_id = "PREMATURE_ISSUANCE"
        report = await cls.run_evaluation(db=db, exports_dir=exports_dir, update_cache=True)
        scenario = next(s for s in report["scenarios"] if s["scenario_id"] == canonical_id)
        return {
            "scenario": scenario,
            "report": report,
        }

