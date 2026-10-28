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
from typing import Any, Dict, List

from src.generator.generator import SyntheticDataset


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

    def export_all(self, anomaly_fixtures: List[Dict[str, Any]], ground_truth: List[Dict[str, Any]]) -> Dict[str, str]:
        """Run all export formats, write summary, and produce manifest.sha256.
        
        Returns:
            Dict mapping filename to SHA-256 checksum.
        """
        # 1. Export CSVs
        csv_files = self._export_csv()
        
        # 2. Export JSONs
        json_files = self._export_json(anomaly_fixtures, ground_truth)
        
        # 3. Export SQL Seed Script
        sql_files = self._export_sql()
        
        # 4. Export Summary Report
        summary_file = self._export_summary()
        
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

    def _export_csv(self) -> List[Path]:
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
        ]
        
        for filename, rows in tables:
            path = self.output_dir / filename
            if rows:
                headers = list(rows[0].keys())
                with open(path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for r in rows:
                        writer.writerow([_serialize_value(r.get(h)) for h in headers])
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    pass
            exported.append(path)
            
        return exported

    def _export_json(
        self,
        anomaly_fixtures: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
    ) -> List[Path]:
        """Export dataset and anomalies to normalized JSON files."""
        exported = []
        
        # Ground truth
        gt_path = self.output_dir / "ground_truth.json"
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(ground_truth, f, indent=2, ensure_ascii=False)
        exported.append(gt_path)
        
        # Anomaly fixtures
        fixtures_path = self.output_dir / "anomaly_fixtures.json"
        with open(fixtures_path, "w", encoding="utf-8") as f:
            json.dump(anomaly_fixtures, f, indent=2, ensure_ascii=False)
        exported.append(fixtures_path)
        
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
                "anomaly_fixtures": len(anomaly_fixtures),
                "ground_truth_records": len(ground_truth),
            },
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        exported.append(meta_path)
        
        return exported

    def _export_sql(self) -> List[Path]:
        """Export SQL script containing batch insert statements."""
        sql_path = self.output_dir / "seed_data.sql"
        with open(sql_path, "w", encoding="utf-8") as f:
            f.write("-- Synthetic Seed Data Export\n")
            f.write(f"-- Seed: {self.dataset.seed}, Scale: {self.dataset.scale}\n")
            f.write("BEGIN;\n\n")
            
            # Issuers
            for row in self.dataset.issuers:
                pub_key_escaped = row["public_key_pem"].replace("'", "''")
                f.write(
                    f"INSERT INTO issuers (id, public_id, name, public_key_pem, status, created_at) "
                    f"VALUES ({row['id']}, '{row['public_id']}', '{row['name']}', '{pub_key_escaped}', "
                    f"'{row['status']}', '{row['created_at'].isoformat()}') ON CONFLICT (id) DO NOTHING;\n"
                )
                
            # Courses
            for row in self.dataset.courses:
                title_escaped = row["title"].replace("'", "''")
                f.write(
                    f"INSERT INTO courses (id, public_id, title, version, status, created_at) "
                    f"VALUES ({row['id']}, '{row['public_id']}', '{title_escaped}', '{row['version']}', "
                    f"'{row['status']}', '{row['created_at'].isoformat()}') ON CONFLICT (id) DO NOTHING;\n"
                )
                
            f.write("\nCOMMIT;\n")
            
        return [sql_path]

    def _export_summary(self) -> Path:
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
            },
        }
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        return summary_path
