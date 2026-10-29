"""Export engine for CSV, JSON, and SQL dump formats with SHA-256 manifest.

Enforces MASTER_SPEC Section 11.7:
- Deterministic sorted export ordering.
- Normalized serialization.
- SHA-256 manifest generation (`manifest.sha256`).
- Export reconciliation summary report (`summary.json`).
"""

import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.core.database import Base
from backend.generator.anomalies import GROUND_TRUTH_COLUMNS
from backend.generator.generator import SyntheticDataset
import backend.models  # noqa: F401 - ensure all 9 models are registered on Base.metadata


def _sql_literal(val: Any) -> str:
    """Format a Python value as a safe SQL literal for deterministic seed_data.sql output."""
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, datetime):
        return "'" + val.isoformat().replace("'", "''") + "'"
    if isinstance(val, dict):
        dumped = json.dumps(val, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
        return "'" + dumped.replace("'", "''") + "'"
    return "'" + str(val).replace("'", "''") + "'"


def _serialize_value(val: Any) -> Any:
    """Normalize values for CSV/JSON serialization."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, dict):
        return json.dumps(val, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return val


def compute_file_sha256(file_path: Path) -> str:
    """Compute the SHA-256 hexadecimal hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class DatasetExporter:
    """Exports a SyntheticDataset into CSV, JSON, and SQL files with a cryptographic manifest."""

    def __init__(self, dataset: SyntheticDataset, output_dir: Path):
        self.dataset = dataset
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self,
        ground_truth: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """Run all export formats, write summary, and produce manifest.sha256.
        
        Returns:
            Dict mapping filename to SHA-256 checksum.
        """
        gt_rows = ground_truth if ground_truth is not None else self.dataset.ground_truth

        # 1. Export CSVs (including credential_import_staging.csv and ground_truth.csv)
        csv_files = self._export_csv(gt_rows)
        
        # 2. Export JSONs
        json_files = self._export_json(gt_rows)
        
        # 3. Export SQL Seed Script
        sql_files = self._export_sql()
        
        # 4. Export Summary Report
        summary_file = self._export_summary(gt_rows)
        
        all_exported = csv_files + json_files + sql_files + [summary_file]
        
        # 5. Generate SHA-256 Manifest
        checksums = {}
        manifest_lines = []
        for file_path in sorted(all_exported, key=lambda p: p.name):
            sha = compute_file_sha256(file_path)
            checksums[file_path.name] = sha
            manifest_lines.append(f"{sha}  {file_path.name}\n")
            
        manifest_path = self.output_dir / "manifest.sha256"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.writelines(manifest_lines)
            
        return checksums

    TABLE_COLUMNS: Dict[str, List[str]] = {
        "issuers.csv": [
            "id",
            "public_id",
            "name",
            "public_key_pem",
            "status",
            "retired_at",
            "successor_issuer_id",
            "created_at",
        ],
        "courses.csv": [
            "id",
            "public_id",
            "title",
            "department",
            "level",
            "version",
            "status",
            "created_at",
        ],
        "credential_rules.csv": [
            "id",
            "course_id",
            "rule_version",
            "min_score",
            "required_completion_status",
            "effective_from",
            "effective_to",
            "active",
            "created_at",
        ],
        "learners.csv": ["id", "public_id", "full_name", "email", "status", "created_at"],
        "completion_records.csv": [
            "id",
            "public_id",
            "learner_id",
            "course_id",
            "rule_id",
            "assessment_score",
            "status",
            "completion_timestamp",
            "created_at",
        ],
        "credentials.csv": [
            "id",
            "public_id",
            "completion_id",
            "issuer_id",
            "issued_at",
            "canonical_payload_hash",
            "issuer_signature",
            "payload_snapshot",
            "status",
            "created_at",
        ],
        "revocations.csv": [
            "id",
            "public_id",
            "credential_id",
            "revoked_by_actor_id",
            "reason_code",
            "revocation_timestamp",
            "created_at",
        ],
        "verification_requests.csv": [
            "id",
            "public_id",
            "credential_id",
            "requested_identifier",
            "verification_timestamp",
            "outcome",
            "reason_code",
            "integrity_check_passed",
            "issuer_authenticated",
            "requester_ip",
            "created_at",
        ],
        "audit_events.csv": [
            "id",
            "event_id",
            "event_type",
            "target_entity_type",
            "target_entity_id",
            "actor_id",
            "details",
            "occurred_at",
        ],
        "credential_import_staging.csv": [
            "id",
            "public_id",
            "completion_id",
            "issuer_id",
            "issued_at",
            "canonical_payload_hash",
            "issuer_signature",
            "payload_snapshot",
            "status",
            "created_at",
        ],
        "ground_truth.csv": GROUND_TRUTH_COLUMNS,
    }

    def _export_csv(self, ground_truth: List[Dict[str, Any]]) -> List[Path]:
        """Export tabular records to individual CSV files."""
        exported = []
        tables = [
            ("issuers.csv", self.dataset.issuers),
            ("courses.csv", self.dataset.courses),
            ("credential_rules.csv", self.dataset.rules),
            ("learners.csv", self.dataset.learners),
            ("completion_records.csv", self.dataset.completions),
            ("credentials.csv", self.dataset.credentials),
            ("revocations.csv", self.dataset.revocations),
            ("verification_requests.csv", self.dataset.verifications),
            ("audit_events.csv", self.dataset.audit_events),
            ("credential_import_staging.csv", self.dataset.credential_import_staging),
        ]
        
        for filename, rows in tables:
            path = self.output_dir / filename
            headers = self.TABLE_COLUMNS.get(filename) or (list(rows[0].keys()) if rows else [])
            sorted_rows = sorted(rows, key=lambda r: r.get("id", 0))
            with open(path, "w", newline="", encoding="utf-8") as f:
                if headers:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for r in sorted_rows:
                        writer.writerow([_serialize_value(r.get(h)) for h in headers])
            exported.append(path)

        # Export ground_truth.csv
        gt_csv_path = self.output_dir / "ground_truth.csv"
        sorted_gt = sorted(ground_truth, key=lambda r: r.get("anomaly_id", ""))
        with open(gt_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(GROUND_TRUTH_COLUMNS)
            for r in sorted_gt:
                writer.writerow([_serialize_value(r.get(h)) for h in GROUND_TRUTH_COLUMNS])
        exported.append(gt_csv_path)
            
        return exported

    def _export_json(
        self,
        ground_truth: List[Dict[str, Any]],
    ) -> List[Path]:
        """Export ground truth and dataset metadata to normalized JSON files."""
        exported = []
        
        # Ground truth
        gt_path = self.output_dir / "ground_truth.json"
        sorted_gt = sorted(ground_truth, key=lambda r: r.get("anomaly_id", ""))
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(sorted_gt, f, indent=2, ensure_ascii=False)
        exported.append(gt_path)
        
        # High-level dataset summary
        meta_path = self.output_dir / "dataset_metadata.json"
        meta = {
            "seed": self.dataset.seed,
            "scale": self.dataset.scale,
            "reference_time": self.dataset.reference_time.isoformat(),
            "counts": {
                "issuers": len(self.dataset.issuers),
                "courses": len(self.dataset.courses),
                "rules": len(self.dataset.rules),
                "learners": len(self.dataset.learners),
                "completions": len(self.dataset.completions),
                "credentials": len(self.dataset.credentials),
                "revocations": len(self.dataset.revocations),
                "verifications": len(self.dataset.verifications),
                "audit_events": len(self.dataset.audit_events),
                "credential_import_staging": len(self.dataset.credential_import_staging),
                "ground_truth_records": len(sorted_gt),
            },
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        exported.append(meta_path)
        
        return exported

    def _export_sql(self) -> List[Path]:
        """Export SQL script containing DDL and INSERT statements for all 9 tables in FK order."""
        sql_path = self.output_dir / "seed_data.sql"
        pg_dialect = postgresql.dialect()

        table_specs: List[tuple[str, List[str], List[Dict[str, Any]]]] = [
            (
                "issuers",
                ["id", "public_id", "name", "public_key_pem", "status", "created_at"],
                sorted(self.dataset.issuers, key=lambda r: r["id"]),
            ),
            (
                "courses",
                ["id", "public_id", "title", "version", "status", "created_at"],
                sorted(self.dataset.courses, key=lambda r: r["id"]),
            ),
            (
                "credential_rules",
                [
                    "id",
                    "course_id",
                    "rule_version",
                    "min_score",
                    "required_completion_status",
                    "effective_from",
                    "effective_to",
                    "active",
                    "created_at",
                ],
                sorted(self.dataset.rules, key=lambda r: r["id"]),
            ),
            (
                "learners",
                ["id", "public_id", "full_name", "email", "status", "created_at"],
                sorted(self.dataset.learners, key=lambda r: r["id"]),
            ),
            (
                "completion_records",
                [
                    "id",
                    "public_id",
                    "learner_id",
                    "course_id",
                    "rule_id",
                    "assessment_score",
                    "status",
                    "completion_timestamp",
                    "created_at",
                ],
                sorted(self.dataset.completions, key=lambda r: r["id"]),
            ),
            (
                "credentials",
                [
                    "id",
                    "public_id",
                    "completion_id",
                    "issuer_id",
                    "issued_at",
                    "canonical_payload_hash",
                    "issuer_signature",
                    "payload_snapshot",
                    "status",
                    "created_at",
                ],
                sorted(self.dataset.credentials, key=lambda r: r["id"]),
            ),
            (
                "revocations",
                [
                    "id",
                    "public_id",
                    "credential_id",
                    "revoked_by_actor_id",
                    "reason_code",
                    "revocation_timestamp",
                    "notes",
                    "created_at",
                ],
                sorted(self.dataset.revocations, key=lambda r: r["id"]),
            ),
            (
                "verification_requests",
                [
                    "id",
                    "public_id",
                    "credential_id",
                    "requested_identifier",
                    "verification_timestamp",
                    "outcome",
                    "reason_code",
                    "integrity_check_passed",
                    "issuer_authenticated",
                    "requester_ip",
                    "created_at",
                ],
                sorted(self.dataset.verifications, key=lambda r: r["id"]),
            ),
            (
                "audit_events",
                [
                    "id",
                    "event_id",
                    "event_type",
                    "actor_id",
                    "target_entity_type",
                    "target_entity_id",
                    "occurred_at",
                    "details",
                    "created_at",
                ],
                sorted(self.dataset.audit_events, key=lambda r: r["id"]),
            ),
        ]

        with open(sql_path, "w", encoding="utf-8") as f:
            f.write("-- Synthetic Seed Data Export (All 9 Tables in FK Order)\n")
            f.write(f"-- Seed: {self.dataset.seed}, Scale: {self.dataset.scale}\n")
            f.write("BEGIN;\n\n")

            # Emit idempotent CREATE TABLE IF NOT EXISTS statements in FK dependency order
            for table in Base.metadata.sorted_tables:
                ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=pg_dialect)).strip()
                f.write(f"{ddl};\n\n")

            # Emit INSERT statements for all 9 tables in FK topological order
            for table_name, cols, rows in table_specs:
                f.write(f"-- Table: {table_name} ({len(rows)} rows)\n")
                col_list = ", ".join(cols)
                for row in rows:
                    vals = []
                    for c in cols:
                        if c == "created_at" and row.get("created_at") is None:
                            vals.append(_sql_literal(row.get("occurred_at")))
                        else:
                            vals.append(_sql_literal(row.get(c)))
                    val_list = ", ".join(vals)
                    f.write(
                        f"INSERT INTO {table_name} ({col_list}) VALUES ({val_list}) ON CONFLICT (id) DO NOTHING;\n"
                    )
                f.write("\n")

            f.write("COMMIT;\n")

        return [sql_path]

    def _export_summary(self, ground_truth: List[Dict[str, Any]]) -> Path:
        """Export summary report for audit reconciliation."""
        summary_path = self.output_dir / "summary.json"
        summary = {
            "generated_at": self.dataset.reference_time.isoformat(),
            "seed": self.dataset.seed,
            "scale": self.dataset.scale,
            "reference_time": self.dataset.reference_time.isoformat(),
            "row_counts": {
                "issuers": len(self.dataset.issuers),
                "courses": len(self.dataset.courses),
                "credential_rules": len(self.dataset.rules),
                "learners": len(self.dataset.learners),
                "completion_records": len(self.dataset.completions),
                "credentials": len(self.dataset.credentials),
                "revocations": len(self.dataset.revocations),
                "verification_requests": len(self.dataset.verifications),
                "audit_events": len(self.dataset.audit_events),
                "credential_import_staging": len(self.dataset.credential_import_staging),
                "ground_truth": len(ground_truth),
            },
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        return summary_path
