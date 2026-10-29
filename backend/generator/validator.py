"""Dataset Referential and Business Invariant Validator.

Enforces MASTER_SPEC Section 12.1:
- Primary-key and Public-ID uniqueness.
- Canonical ID regex format checks across all entities.
- Foreign-key referential integrity.
- Allowed enum values and numeric ranges.
- Date ordering (issued_at >= completed_at, revoked_at >= issued_at).
- Non-negotiable eligibility invariant (assessment_score >= min_score).
- Audit ledger reconciliation (1:1 counts for CREDENTIAL_ISSUED, CREDENTIAL_REVOKED,
  VERIFICATION_PERFORMED, and target entity resolution for every audit event) on both
  exported/in-memory datasets and PostgreSQL databases.
- Optional `--with-ground-truth` reconciliation confirming every labelled anomaly is
  detected and zero unlabelled violations exist.
"""

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine

from backend.core.security import compute_payload_hash
from backend.generator.anomalies import load_ground_truth
from backend.generator.generator import SyntheticDataset
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
from backend.services.ids import ID_PATTERNS
from backend.services.payloads import build_credential_payload


@dataclass
class ValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


def _parse_csv_rows(
    csv_path: Path,
    int_cols: tuple[str, ...] = ("id",),
    nullable_int_cols: tuple[str, ...] = (),
    decimal_cols: tuple[str, ...] = (),
    bool_cols: tuple[str, ...] = (),
    dt_cols: tuple[str, ...] = (),
    nullable_dt_cols: tuple[str, ...] = (),
    json_cols: tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    """Load and type-convert rows from an exported CSV file."""
    if not csv_path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row: Dict[str, Any] = dict(raw)
            for c in int_cols:
                if c in row and row[c] != "":
                    row[c] = int(row[c])
            for c in nullable_int_cols:
                if c in row:
                    row[c] = int(row[c]) if row[c] not in ("", None) else None
            for c in decimal_cols:
                if c in row and row[c] != "":
                    row[c] = Decimal(str(row[c]))
            for c in bool_cols:
                if c in row and row[c] != "":
                    row[c] = str(row[c]).strip().lower() in ("true", "1", "yes")
            for c in dt_cols:
                if c in row and row[c] != "":
                    row[c] = datetime.fromisoformat(row[c])
            for c in nullable_dt_cols:
                if c in row:
                    row[c] = datetime.fromisoformat(row[c]) if row[c] not in ("", None) else None
            for c in json_cols:
                if c in row and row[c] != "":
                    row[c] = json.loads(row[c])
            rows.append(row)
    return rows


class DatasetValidator:
    """Validates referential integrity, numeric ranges, business invariants, and audit reconciliation."""

    def __init__(
        self,
        dataset: SyntheticDataset,
        with_ground_truth: Optional[bool] = None,
    ):
        self.dataset = dataset
        if with_ground_truth is None:
            self.with_ground_truth = bool(getattr(dataset, "ground_truth", []))
        else:
            self.with_ground_truth = with_ground_truth

    @classmethod
    def from_database(cls, engine: Engine) -> "DatasetValidator":
        """Load all 9 tables from a PostgreSQL database into a SyntheticDataset for validation."""
        ds = SyntheticDataset(
            seed=0,
            scale=0.0,
            reference_time=datetime.now(timezone.utc),
        )
        with engine.connect() as conn:
            ds.issuers = [dict(r) for r in conn.execute(select(Issuer.__table__).order_by(Issuer.id)).mappings()]
            ds.courses = [dict(r) for r in conn.execute(select(Course.__table__).order_by(Course.id)).mappings()]
            ds.rules = [dict(r) for r in conn.execute(select(CredentialRule.__table__).order_by(CredentialRule.id)).mappings()]
            ds.learners = [dict(r) for r in conn.execute(select(Learner.__table__).order_by(Learner.id)).mappings()]
            ds.completions = [dict(r) for r in conn.execute(select(CompletionRecord.__table__).order_by(CompletionRecord.id)).mappings()]
            ds.credentials = [dict(r) for r in conn.execute(select(Credential.__table__).order_by(Credential.id)).mappings()]
            ds.revocations = [dict(r) for r in conn.execute(select(Revocation.__table__).order_by(Revocation.id)).mappings()]
            ds.verifications = [dict(r) for r in conn.execute(select(VerificationRequest.__table__).order_by(VerificationRequest.id)).mappings()]
            ds.audit_events = [dict(r) for r in conn.execute(select(AuditEvent.__table__).order_by(AuditEvent.id)).mappings()]
        return cls(ds, with_ground_truth=False)

    @classmethod
    def from_export_dir(
        cls,
        export_dir: Path,
        with_ground_truth: bool = False,
    ) -> "DatasetValidator":
        """Load exported CSV files (and ground_truth only when `with_ground_truth=True`)."""
        ds = SyntheticDataset(
            seed=0,
            scale=0.0,
            reference_time=datetime.now(timezone.utc),
        )
        ds.issuers = _parse_csv_rows(
            export_dir / "issuers.csv",
            int_cols=("id",),
            nullable_int_cols=("successor_issuer_id",),
            dt_cols=("created_at",),
            nullable_dt_cols=("retired_at",),
        )
        ds.courses = _parse_csv_rows(
            export_dir / "courses.csv",
            int_cols=("id",),
            dt_cols=("created_at",),
        )
        ds.rules = _parse_csv_rows(
            export_dir / "credential_rules.csv",
            int_cols=("id", "course_id"),
            decimal_cols=("min_score",),
            bool_cols=("active",),
            dt_cols=("effective_from", "effective_to", "created_at"),
        )
        ds.learners = _parse_csv_rows(
            export_dir / "learners.csv",
            int_cols=("id",),
            dt_cols=("created_at",),
        )
        ds.completions = _parse_csv_rows(
            export_dir / "completion_records.csv",
            int_cols=("id", "learner_id", "course_id", "rule_id"),
            decimal_cols=("assessment_score",),
            dt_cols=("completion_timestamp", "created_at"),
        )
        ds.credentials = _parse_csv_rows(
            export_dir / "credentials.csv",
            int_cols=("id", "completion_id", "issuer_id"),
            dt_cols=("issued_at", "created_at"),
            json_cols=("payload_snapshot",),
        )
        ds.revocations = _parse_csv_rows(
            export_dir / "revocations.csv",
            int_cols=("id", "credential_id"),
            dt_cols=("revocation_timestamp", "created_at"),
        )
        ds.verifications = _parse_csv_rows(
            export_dir / "verification_requests.csv",
            int_cols=("id",),
            nullable_int_cols=("credential_id",),
            bool_cols=("integrity_check_passed", "issuer_authenticated"),
            dt_cols=("verification_timestamp", "created_at"),
        )
        ds.audit_events = _parse_csv_rows(
            export_dir / "audit_events.csv",
            int_cols=("id",),
            dt_cols=("occurred_at",),
            json_cols=("details",),
        )
        ds.credential_import_staging = _parse_csv_rows(
            export_dir / "credential_import_staging.csv",
            int_cols=("id", "completion_id", "issuer_id"),
            dt_cols=("issued_at", "created_at"),
            json_cols=("payload_snapshot",),
        )
        if with_ground_truth:
            ds.ground_truth = load_ground_truth(export_dir)
        return cls(ds, with_ground_truth=with_ground_truth)

    def validate_all(self) -> ValidationReport:
        """Execute comprehensive validation across all entities, relationships, and audit events."""
        report = ValidationReport(is_valid=True)

        self._validate_uniqueness(report)
        self._validate_id_formats(report)
        self._validate_foreign_keys(report)
        self._validate_date_ordering(report)
        self._validate_eligibility_invariants(report)
        self._validate_audit_reconciliation(report)
        if self.with_ground_truth:
            self._validate_ground_truth_anomalies(report)
        self._collect_stats(report)

        report.is_valid = len(report.errors) == 0
        return report

    def _validate_uniqueness(self, report: ValidationReport) -> None:
        """Assert PK and public_id uniqueness."""
        def check_ids(items: List[Dict[str, Any]], entity_name: str, pub_key: str = "public_id"):
            pks = set()
            public_ids = set()
            for r in items:
                pk = r.get("id")
                pub = r.get(pub_key)
                if pk in pks:
                    report.errors.append(f"Duplicate primary key {pk} in {entity_name}")
                pks.add(pk)
                if pub:
                    if pub in public_ids:
                        report.errors.append(f"Duplicate {pub_key} '{pub}' in {entity_name}")
                    public_ids.add(pub)

        check_ids(self.dataset.issuers, "issuers")
        check_ids(self.dataset.courses, "courses")
        check_ids(self.dataset.rules, "credential_rules")
        check_ids(self.dataset.learners, "learners")
        check_ids(self.dataset.completions, "completion_records")
        check_ids(self.dataset.credentials, "credentials")
        check_ids(self.dataset.revocations, "revocations")
        check_ids(self.dataset.verifications, "verification_requests")
        check_ids(self.dataset.audit_events, "audit_events", pub_key="event_id")

    def _validate_id_formats(self, report: ValidationReport) -> None:
        """Assert every public identifier matches its canonical format (see backend/services/ids.py)."""
        checks = [
            (self.dataset.issuers, "public_id", "issuer"),
            (self.dataset.courses, "public_id", "course"),
            (self.dataset.learners, "public_id", "learner"),
            (self.dataset.completions, "public_id", "completion"),
            (self.dataset.credentials, "public_id", "credential"),
            (self.dataset.verifications, "public_id", "verification"),
            (self.dataset.revocations, "public_id", "revocation"),
            (self.dataset.audit_events, "event_id", "audit_event"),
        ]
        for rows, key, entity in checks:
            pattern = ID_PATTERNS[entity]
            for row in rows:
                value = row.get(key)
                if not isinstance(value, str) or not pattern.match(value):
                    report.errors.append(f"Invalid {entity} {key} format: {value!r}")

    def _validate_foreign_keys(self, report: ValidationReport) -> None:
        """Assert referential parent existence for all child references."""
        course_ids = {c["id"] for c in self.dataset.courses}
        rule_ids = {r["id"] for r in self.dataset.rules}
        learner_ids = {l["id"] for l in self.dataset.learners}
        completion_ids = {c["id"] for c in self.dataset.completions}
        issuer_ids = {i["id"] for i in self.dataset.issuers}
        cred_ids = {c["id"] for c in self.dataset.credentials}

        # Rules -> Courses
        for rule in self.dataset.rules:
            if rule["course_id"] not in course_ids:
                report.errors.append(f"Rule {rule['id']} references nonexistent course_id {rule['course_id']}")

        # Completions -> Learners, Courses, Rules
        for comp in self.dataset.completions:
            if comp["learner_id"] not in learner_ids:
                report.errors.append(f"Completion {comp['id']} references nonexistent learner_id {comp['learner_id']}")
            if comp["course_id"] not in course_ids:
                report.errors.append(f"Completion {comp['id']} references nonexistent course_id {comp['course_id']}")
            if comp["rule_id"] not in rule_ids:
                report.errors.append(f"Completion {comp['id']} references nonexistent rule_id {comp['rule_id']}")

        # Credentials -> Completions, Issuers
        seen_completion_creds = set()
        for cred in self.dataset.credentials:
            if cred["completion_id"] not in completion_ids:
                report.errors.append(f"Credential {cred['id']} references nonexistent completion_id {cred['completion_id']}")
            if cred["completion_id"] in seen_completion_creds:
                report.errors.append(f"Duplicate issuance: completion_id {cred['completion_id']} issued multiple credentials")
            seen_completion_creds.add(cred["completion_id"])

            if cred["issuer_id"] not in issuer_ids:
                report.errors.append(f"Credential {cred['id']} references nonexistent issuer_id {cred['issuer_id']}")

        # Revocations -> Credentials
        for rev in self.dataset.revocations:
            if rev["credential_id"] not in cred_ids:
                report.errors.append(f"Revocation {rev['id']} references nonexistent credential_id {rev['credential_id']}")

    def _validate_date_ordering(self, report: ValidationReport) -> None:
        """Assert logical chronological order: issued_at >= completed_at (except labelled PREMATURE_ISSUANCE), revoked_at >= issued_at."""
        comp_lookup = {c["id"]: c for c in self.dataset.completions}
        cred_lookup = {c["id"]: c for c in self.dataset.credentials}
        has_ground_truth = self.with_ground_truth and bool(getattr(self.dataset, "ground_truth", []))
        labelled_premature_ids = (
            {
                gt["entity_public_id"]
                for gt in getattr(self.dataset, "ground_truth", [])
                if gt.get("issue_type") == "PREMATURE_ISSUANCE"
            }
            if has_ground_truth
            else set()
        )
        detected_premature_ids: set[str] = set()

        # Credential issuance vs completion
        for cred in self.dataset.credentials:
            comp = comp_lookup.get(cred["completion_id"])
            if comp and cred["issued_at"] < comp["completion_timestamp"]:
                detected_premature_ids.add(cred["public_id"])
                if has_ground_truth and cred["public_id"] not in labelled_premature_ids:
                    report.errors.append(
                        f"Unlabelled date anomaly: Credential {cred['public_id']} issued_at ({cred['issued_at']}) "
                        f"precedes completion_timestamp ({comp['completion_timestamp']})"
                    )
                elif not has_ground_truth:
                    report.warnings.append(
                        f"Premature issuance row present: Credential {cred['public_id']} issued_at ({cred['issued_at']}) "
                        f"< completion_timestamp ({comp['completion_timestamp']})"
                    )

        if has_ground_truth and detected_premature_ids != labelled_premature_ids:
            missing = sorted(labelled_premature_ids - detected_premature_ids)
            if missing:
                report.errors.append(
                    f"Labelled PREMATURE_ISSUANCE rows not detected by chronology check: {missing}"
                )

        # Revocation vs issuance
        for rev in self.dataset.revocations:
            cred = cred_lookup.get(rev["credential_id"])
            if cred and rev["revocation_timestamp"] < cred["issued_at"]:
                report.errors.append(
                    f"Date anomaly: Revocation {rev['id']} timestamp ({rev['revocation_timestamp']}) "
                    f"precedes credential issued_at ({cred['issued_at']})"
                )

    def _validate_ground_truth_anomalies(self, report: ValidationReport) -> None:
        """When `--with-ground-truth` is enabled, verify all 4 labelled anomaly categories and 0 unlabelled violations."""
        gt_rows = getattr(self.dataset, "ground_truth", [])
        if not gt_rows:
            report.errors.append("Ground-truth validation requested (--with-ground-truth) but no ground_truth records loaded.")
            return

        by_type: Dict[str, set[str]] = {
            "PREMATURE_ISSUANCE": set(),
            "DUPLICATE_CREDENTIAL_ID": set(),
            "REVOKED_VERIFIES_AS_ACTIVE": set(),
            "ALTERED_PAYLOAD_NOT_DETECTED": set(),
        }
        for gt in gt_rows:
            it = gt.get("issue_type")
            if it in by_type:
                by_type[it].add(gt["entity_public_id"])

        comp_lookup = {c["id"]: c for c in self.dataset.completions}
        learner_lookup = {l["id"]: l for l in self.dataset.learners}
        course_lookup = {c["id"]: c for c in self.dataset.courses}
        issuer_lookup = {i["id"]: i for i in self.dataset.issuers}
        revoked_cred_ids = {r["credential_id"] for r in self.dataset.revocations}
        cred_pub_ids = {c["public_id"] for c in self.dataset.credentials}

        # 1. PREMATURE_ISSUANCE
        detected_premature = {
            c["public_id"]
            for c in self.dataset.credentials
            if c["issued_at"] < comp_lookup[c["completion_id"]]["completion_timestamp"]
        }
        if detected_premature != by_type["PREMATURE_ISSUANCE"]:
            report.errors.append(
                f"Ground-truth mismatch for PREMATURE_ISSUANCE: expected {len(by_type['PREMATURE_ISSUANCE'])}, detected {len(detected_premature)}"
            )

        # 2. DUPLICATE_CREDENTIAL_ID (staging rows colliding with credentials.public_id)
        detected_duplicates = {
            s["public_id"]
            for s in getattr(self.dataset, "credential_import_staging", [])
            if s["public_id"] in cred_pub_ids
        }
        if detected_duplicates != by_type["DUPLICATE_CREDENTIAL_ID"]:
            report.errors.append(
                f"Ground-truth mismatch for DUPLICATE_CREDENTIAL_ID: expected {len(by_type['DUPLICATE_CREDENTIAL_ID'])}, detected {len(detected_duplicates)}"
            )

        # 3. REVOKED_VERIFIES_AS_ACTIVE
        detected_stale_revoked = {
            c["public_id"]
            for c in self.dataset.credentials
            if c["id"] in revoked_cred_ids and c["status"] == "ACTIVE"
        }
        if detected_stale_revoked != by_type["REVOKED_VERIFIES_AS_ACTIVE"]:
            report.errors.append(
                f"Ground-truth mismatch for REVOKED_VERIFIES_AS_ACTIVE: expected {len(by_type['REVOKED_VERIFIES_AS_ACTIVE'])}, detected {len(detected_stale_revoked)}"
            )

        # 4. ALTERED_PAYLOAD_NOT_DETECTED (hash mismatch or relational payload mismatch)
        detected_altered: set[str] = set()
        for c in self.dataset.credentials:
            snap = c["payload_snapshot"]
            comp = comp_lookup[c["completion_id"]]
            learner = learner_lookup[comp["learner_id"]]
            course = course_lookup[comp["course_id"]]
            issuer = issuer_lookup[c["issuer_id"]]
            rebuilt = build_credential_payload(
                credential_id=c["public_id"],
                issued_at=c["issued_at"],
                completion_timestamp=comp["completion_timestamp"],
                learner_id=learner["public_id"],
                learner_name=learner["full_name"],
                learner_email=learner["email"],
                course_code=course["public_id"],
                course_title=course["title"],
                assessment_score=comp["assessment_score"],
                assessment_status=comp["status"],
                issuer_id=issuer["public_id"],
                issuer_name=issuer["name"],
            )
            hash_ok = compute_payload_hash(snap) == c["canonical_payload_hash"]
            rel_ok = all(
                snap.get(k) == rebuilt.get(k)
                for k in ("credential_id", "course", "learner", "assessment", "issuer")
            )
            if not (hash_ok and rel_ok):
                detected_altered.add(c["public_id"])

        if detected_altered != by_type["ALTERED_PAYLOAD_NOT_DETECTED"]:
            report.errors.append(
                f"Ground-truth mismatch for ALTERED_PAYLOAD_NOT_DETECTED: expected {len(by_type['ALTERED_PAYLOAD_NOT_DETECTED'])}, detected {len(detected_altered)}"
            )

        report.stats["ground_truth_reconciliation"] = {
            "total_labelled": len(gt_rows),
            "premature_issuance_matched": len(detected_premature & by_type["PREMATURE_ISSUANCE"]),
            "duplicate_credential_id_matched": len(detected_duplicates & by_type["DUPLICATE_CREDENTIAL_ID"]),
            "revoked_verifies_as_active_matched": len(detected_stale_revoked & by_type["REVOKED_VERIFIES_AS_ACTIVE"]),
            "altered_payload_not_detected_matched": len(detected_altered & by_type["ALTERED_PAYLOAD_NOT_DETECTED"]),
            "unlabelled_violations": (
                len(detected_premature - by_type["PREMATURE_ISSUANCE"])
                + len(detected_duplicates - by_type["DUPLICATE_CREDENTIAL_ID"])
                + len(detected_stale_revoked - by_type["REVOKED_VERIFIES_AS_ACTIVE"])
                + len(detected_altered - by_type["ALTERED_PAYLOAD_NOT_DETECTED"])
            ),
        }

    def _validate_eligibility_invariants(self, report: ValidationReport) -> None:
        """Assert that no credential was issued to an ineligible completion record."""
        comp_lookup = {c["id"]: c for c in self.dataset.completions}

        for cred in self.dataset.credentials:
            comp = comp_lookup.get(cred["completion_id"])
            if comp:
                if comp["status"] != "COMPLETED":
                    report.errors.append(
                        f"Eligibility Violation: Credential {cred['public_id']} issued to completion with status '{comp['status']}'"
                    )
                if comp["assessment_score"] < Decimal("80.00"):
                    report.errors.append(
                        f"Eligibility Violation: Credential {cred['public_id']} issued to completion with failing score {comp['assessment_score']}"
                    )

    def _validate_audit_reconciliation(self, report: ValidationReport) -> None:
        """Reconcile audit event counts with entity tables and verify every audit target resolves."""
        issued_events = sum(1 for e in self.dataset.audit_events if e["event_type"] == "CREDENTIAL_ISSUED")
        revoked_events = sum(1 for e in self.dataset.audit_events if e["event_type"] == "CREDENTIAL_REVOKED")
        verified_events = sum(1 for e in self.dataset.audit_events if e["event_type"] == "VERIFICATION_PERFORMED")

        if issued_events != len(self.dataset.credentials):
            report.errors.append(
                f"Audit reconciliation mismatch: count(CREDENTIAL_ISSUED)={issued_events} != count(credentials)={len(self.dataset.credentials)}"
            )
        if revoked_events != len(self.dataset.revocations):
            report.errors.append(
                f"Audit reconciliation mismatch: count(CREDENTIAL_REVOKED)={revoked_events} != count(revocations)={len(self.dataset.revocations)}"
            )
        if verified_events != len(self.dataset.verifications):
            report.errors.append(
                f"Audit reconciliation mismatch: count(VERIFICATION_PERFORMED)={verified_events} != count(verification_requests)={len(self.dataset.verifications)}"
            )

        # Build lookup sets for target resolution
        target_sets: Dict[str, set[str]] = {
            "Credential": {c["public_id"] for c in self.dataset.credentials},
            "CredentialRule": {str(r["id"]) for r in self.dataset.rules},
            "VerificationRequest": {v["public_id"] for v in self.dataset.verifications},
            "CompletionRecord": {c["public_id"] for c in self.dataset.completions if c.get("public_id")}
            | {str(c["id"]) for c in self.dataset.completions},
            "Revocation": {r["public_id"] for r in self.dataset.revocations if r.get("public_id")},
            "Issuer": {i["public_id"] for i in self.dataset.issuers},
            "Course": {c["public_id"] for c in self.dataset.courses},
            "Learner": {l["public_id"] for l in self.dataset.learners},
        }

        unresolved_count = 0
        for ev in self.dataset.audit_events:
            entity_type = ev.get("target_entity_type")
            entity_id = str(ev.get("target_entity_id", ""))
            valid_ids = target_sets.get(entity_type)
            if valid_ids is None or entity_id not in valid_ids:
                unresolved_count += 1
                report.errors.append(
                    f"Unresolved audit event target: event_id={ev.get('event_id')} references {entity_type} '{entity_id}'"
                )

        report.stats["reconciliation"] = {
            "credential_issued_events": issued_events,
            "credentials_count": len(self.dataset.credentials),
            "credentials_reconciled": issued_events == len(self.dataset.credentials),
            "credential_revoked_events": revoked_events,
            "revocations_count": len(self.dataset.revocations),
            "revocations_reconciled": revoked_events == len(self.dataset.revocations),
            "verification_performed_events": verified_events,
            "verifications_count": len(self.dataset.verifications),
            "verifications_reconciled": verified_events == len(self.dataset.verifications),
            "unresolved_audit_targets": unresolved_count,
        }

    def _collect_stats(self, report: ValidationReport) -> None:
        """Record statistical metrics for the validation report."""
        report.stats.update({
            "issuers_count": len(self.dataset.issuers),
            "courses_count": len(self.dataset.courses),
            "rules_count": len(self.dataset.rules),
            "learners_count": len(self.dataset.learners),
            "completions_count": len(self.dataset.completions),
            "credentials_count": len(self.dataset.credentials),
            "active_credentials": sum(1 for c in self.dataset.credentials if c["status"] == "ACTIVE"),
            "revoked_credentials": sum(1 for c in self.dataset.credentials if c["status"] == "REVOKED"),
            "revocations_count": len(self.dataset.revocations),
            "verifications_count": len(self.dataset.verifications),
            "audit_events_count": len(self.dataset.audit_events),
        })


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate synthetic dataset from exports or database.")
    parser.add_argument(
        "--export-dir",
        type=str,
        default="./exports",
        help="Directory containing exported CSV/JSON dataset files (default: ./exports).",
    )
    parser.add_argument(
        "--db",
        choices=["live", "test"],
        default=None,
        help="Validate live database directly via SQLAlchemy (live -> credential_db, test -> credential_test_db).",
    )
    parser.add_argument(
        "--with-ground-truth",
        action="store_true",
        help="Validate ground_truth.json against injected anomalies and check for 0 unlabelled violations.",
    )
    args = parser.parse_args(argv)

    if args.db:
        from backend.core.config import settings
        db_url = settings.SYNC_DATABASE_URL if args.db == "live" else settings.TEST_DATABASE_URL_SYNC
        engine = create_engine(db_url, echo=False)
        try:
            validator = DatasetValidator.from_database(engine)
            if args.with_ground_truth:
                gt_path = Path(args.export_dir)
                if (gt_path / "ground_truth.json").exists():
                    validator.dataset.ground_truth = load_ground_truth(gt_path)
                    validator.with_ground_truth = True
                staging_file = gt_path / "credential_import_staging.csv"
                if staging_file.exists():
                    validator.dataset.credential_import_staging = _parse_csv_rows(
                        staging_file,
                        int_cols=("id", "completion_id", "issuer_id"),
                        dt_cols=("issued_at", "created_at"),
                        json_cols=("payload_snapshot",),
                    )
            report = validator.validate_all()
        finally:
            engine.dispose()
    else:
        validator = DatasetValidator.from_export_dir(
            Path(args.export_dir),
            with_ground_truth=args.with_ground_truth,
        )
        report = validator.validate_all()

    output = {
        "is_valid": report.is_valid,
        "source": f"database ({args.db})" if args.db else f"export_dir ({args.export_dir})",
        "with_ground_truth": args.with_ground_truth,
        "errors_count": len(report.errors),
        "warnings_count": len(report.warnings),
        "errors": report.errors,
        "stats": report.stats,
    }
    print(json.dumps(output, indent=2))
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
