"""Command-line interface for synthetic data generation and export.

Usage:
    python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports
    python -m backend.generator.cli --seed 20261022 --scale 1.0 --load-db --truncate
"""

import argparse
from pathlib import Path
import sys
import time

from backend.generator.anomalies import generate_anomaly_fixtures
from backend.generator.db_loader import DatabaseLoader
from backend.generator.exporter import DatasetExporter
from backend.generator.generator import DEFAULT_SEED, DataGenerator
from backend.generator.validator import DatasetValidator


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic Synthetic Data Generator for Credential Lifecycle Management System"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"PRNG seed for deterministic output (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor (1.0 = 20k learners, 1k courses, 10k credentials, 5k verifications)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./exports",
        help="Target directory for CSV/JSON/SQL exports and manifest.sha256",
    )
    parser.add_argument(
        "--load-db",
        action="store_true",
        help="Bulk insert the generated dataset into the active PostgreSQL database",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate database tables before loading (requires --load-db)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip referential integrity validation",
    )

    args = parser.parse_args()
    output_path = Path(args.output_dir)

    print("================================================================================")
    print("  YottaFlex AI - Digital Credential Lifecycle Synthetic Data Generator")
    print("================================================================================")
    print(f"  Seed:       {args.seed}")
    print(f"  Scale:      {args.scale}")
    print(f"  Output Dir: {output_path.resolve()}")
    print(f"  Load DB:    {args.load_db}")
    print("--------------------------------------------------------------------------------")

    t_start = time.perf_counter()

    # 1. Generate Dataset
    print("[1/5] Generating topological records in-memory...")
    generator = DataGenerator(seed=args.seed, scale=args.scale)
    dataset = generator.generate()

    # 2. Generate 4 Mandatory Anomalies & Segregated Ground Truth
    print("[2/5] Generating 4 controlled anomaly fixtures and segregated ground truth...")
    fixtures, ground_truth = generate_anomaly_fixtures(seed=args.seed)

    # 3. Validate Referential Integrity & Invariants
    if not args.no_validate:
        print("[3/5] Validating database constraints and academic eligibility invariants...")
        validator = DatasetValidator(dataset)
        report = validator.validate_all()
        if not report.is_valid:
            print(f"ERROR: Dataset validation failed with {len(report.errors)} errors:")
            for err in report.errors[:10]:
                print(f"  - {err}")
            sys.exit(1)
        print("      Validation PASSED (0 errors, referential integrity intact).")
    else:
        print("[3/5] Skipping validation as requested.")

    # 4. Optional PostgreSQL Ingestion
    if args.load_db:
        print("[4/5] Ingesting dataset into PostgreSQL via SQLAlchemy Core batching...")
        loader = DatabaseLoader(dataset)
        load_res = loader.load_all(truncate_first=args.truncate)
        print(f"      Database ingestion complete in {load_res['duration_seconds']}s.")
    else:
        print("[4/5] Skipping DB load (use --load-db to insert into PostgreSQL).")

    # 5. Export Files & Checksum Manifest
    print("[5/5] Exporting CSV, JSON, SQL seed files and computing manifest.sha256...")
    exporter = DatasetExporter(dataset, output_path)
    checksums = exporter.export_all(fixtures, ground_truth)
    print(f"      Successfully exported {len(checksums)} files to {output_path}.")

    total_time = time.perf_counter() - t_start
    print("--------------------------------------------------------------------------------")
    print("  GENERATION COMPLETE")
    print(f"  Total Duration: {total_time:.2f}s (target < 60s)")
    print(f"  Learners:       {len(dataset.learners):,}")
    print(f"  Courses:        {len(dataset.courses):,}")
    print(f"  Completions:    {len(dataset.completions):,}")
    print(f"  Credentials:    {len(dataset.credentials):,}")
    print(f"  Revocations:    {len(dataset.revocations):,}")
    print(f"  Verifications:  {len(dataset.verifications):,}")
    print(f"  Audit Events:   {len(dataset.audit_events):,}")
    print(f"  Anomalies:      {len(fixtures)} fixtures (ground_truth.json)")
    print("================================================================================")


if __name__ == "__main__":
    main()
