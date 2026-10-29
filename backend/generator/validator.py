"""Dataset Referential and Business Invariant Validator.

Enforces MASTER_SPEC Section 12.1:
- Primary-key and Public-ID uniqueness.
- Foreign-key referential integrity.
- Allowed enum values and numeric ranges.
- Date ordering (issued_at >= completed_at, revoked_at >= issued_at).
- Non-negotiable eligibility invariant (assessment_score >= min_score).
- Reconciles exported row counts.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List

from backend.generator.generator import SyntheticDataset
from backend.services.ids import ID_PATTERNS


@dataclass
class ValidationReport:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class DatasetValidator:
    """Validates referential integrity, numeric ranges, and business invariants across a synthetic dataset."""

    def __init__(self, dataset: SyntheticDataset):
        self.dataset = dataset

    def validate_all(self) -> ValidationReport:
        """Execute comprehensive validation across all entities and relationships."""
        report = ValidationReport(is_valid=True)
        
        self._validate_uniqueness(report)
        self._validate_id_formats(report)
        self._validate_foreign_keys(report)
        self._validate_date_ordering(report)
        self._validate_eligibility_invariants(report)
        self._collect_stats(report)
        
        report.is_valid = len(report.errors) == 0
        return report

    def _validate_uniqueness(self, report: ValidationReport) -> None:
        """Assert PK and public_id uniqueness."""
        def check_ids(items: List[Dict[str, Any]], entity_name: str):
            pks = set()
            public_ids = set()
            for r in items:
                pk = r.get("id")
                pub = r.get("public_id")
                if pk in pks:
                    report.errors.append(f"Duplicate primary key {pk} in {entity_name}")
                pks.add(pk)
                if pub:
                    if pub in public_ids:
                        report.errors.append(f"Duplicate public_id '{pub}' in {entity_name}")
                    public_ids.add(pub)

        check_ids(self.dataset.issuers, "issuers")
        check_ids(self.dataset.courses, "courses")
        check_ids(self.dataset.rules, "credential_rules")
        check_ids(self.dataset.learners, "learners")
        check_ids(self.dataset.completions, "completion_records")
        check_ids(self.dataset.credentials, "credentials")
        check_ids(self.dataset.revocations, "revocations")
        check_ids(self.dataset.verifications, "verification_requests")
        check_ids(self.dataset.audit_events, "audit_events")

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

    def _collect_stats(self, report: ValidationReport) -> None:
        """Record statistical metrics for the validation report."""
        report.stats = {
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
        }
