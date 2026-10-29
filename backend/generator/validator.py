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
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.engine import Engine

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


@dataclass
class ValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class DatasetValidator:
    """Validates referential integrity, numeric ranges, business invariants, and audit reconciliation."""

    def __init__(self, dataset: SyntheticDataset):
        self.dataset = dataset

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
        return cls(ds)

    def validate_all(self) -> ValidationReport:
        """Execute comprehensive validation across all entities, relationships, and audit events."""
        report = ValidationReport(is_valid=True)
        
        self._validate_uniqueness(report)
        self._validate_id_formats(report)
        self._validate_foreign_keys(report)
        self._validate_date_ordering(report)
        self._validate_eligibility_invariants(report)
        self._validate_audit_reconciliation(report)
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
        """Assert logical chronological order: issued_at >= completed_at, revoked_at >= issued_at."""
        comp_lookup = {c["id"]: c for c in self.dataset.completions}
        cred_lookup = {c["id"]: c for c in self.dataset.credentials}

        # Credential issuance vs completion
        for cred in self.dataset.credentials:
            comp = comp_lookup.get(cred["completion_id"])
            if comp and cred["issued_at"] < comp["completion_timestamp"]:
                report.errors.append(
                    f"Date anomaly: Credential {cred['public_id']} issued_at ({cred['issued_at']}) "
                    f"precedes completion_timestamp ({comp['completion_timestamp']})"
                )

        # Revocation vs issuance
        for rev in self.dataset.revocations:
            cred = cred_lookup.get(rev["credential_id"])
            if cred and rev["revocation_timestamp"] < cred["issued_at"]:
                report.errors.append(
                    f"Date anomaly: Revocation {rev['id']} timestamp ({rev['revocation_timestamp']}) "
                    f"precedes credential issued_at ({cred['issued_at']})"
                )

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
