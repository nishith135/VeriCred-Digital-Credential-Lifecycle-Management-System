"""CLI runner for the credential verification & anomaly evaluation suite.

Usage:
    python -m backend.evaluation.run --db test --out ./exports_tmp
    python -m backend.evaluation.run --db live --out ./exports
"""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import settings
from backend.evaluation.evaluator import EvaluationRunner


async def _run_async(db_mode: str, out_dir: Path) -> dict:
    db_url = settings.TEST_DATABASE_URL if db_mode == "test" else settings.DATABASE_URL
    engine = create_async_engine(db_url, echo=False, future=True)
    factory = async_sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    try:
        async with factory() as session:
            report = await EvaluationRunner.run_evaluation(session, exports_dir=out_dir)
    finally:
        await engine.dispose()

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "evaluation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run dry-run credential verification evaluation and write evaluation_report.json"
    )
    parser.add_argument(
        "--db",
        choices=["test", "live"],
        default="test",
        help="Target database: 'test' (credential_test_db) or 'live' (credential_db)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="./exports",
        help="Directory containing ground_truth.json and target for evaluation_report.json",
    )
    args = parser.parse_args()
    out_path = Path(args.out)

    report = asyncio.run(_run_async(args.db, out_path))
    m = report["metrics"]
    per_type = m["per_anomaly_type_detection_rate"]

    print("================================================================================")
    print(f"  Evaluation Report ({args.db} database) -> {out_path / 'evaluation_report.json'}")
    print("================================================================================")
    print(f"  Total Elapsed Time:       {report['total_elapsed_ms']:.2f} ms")
    print(f"  Credentials Evaluated:    {report['total_credentials_evaluated']:,}")
    print(f"  Staging Duplicates:       {report['total_staging_duplicates_evaluated']:,}")
    print(f"  Row Count Delta (9 tbls): {report['row_count_delta']}")
    print("--------------------------------------------------------------------------------")
    print(f"  {'Metric':<40} | {'Num / Den':<15} | {'Rate':<10}")
    print("--------------------------------------------------------------------------------")

    rows = [
        ("Overall Accuracy", m["overall_accuracy"]),
        ("Detection: PREMATURE_ISSUANCE", per_type["PREMATURE_ISSUANCE"]),
        ("Detection: DUPLICATE_CREDENTIAL_ID", per_type["DUPLICATE_CREDENTIAL_ID"]),
        ("Detection: REVOKED_VERIFIES_AS_ACTIVE", per_type["REVOKED_VERIFIES_AS_ACTIVE"]),
        ("Detection: ALTERED_PAYLOAD_NOT_DETECTED", per_type["ALTERED_PAYLOAD_NOT_DETECTED"]),
        ("False Acceptance Rate (FAR)", m["false_acceptance_rate"]),
        ("False Rejection Rate (FRR)", m["false_rejection_rate"]),
        ("Revocation Detection Rate", m["revocation_detection_rate"]),
        ("Tamper Detection Rate", m["tamper_detection_rate"]),
    ]
    for label, item in rows:
        num_den = f"{item['numerator']} / {item['denominator']}"
        print(f"  {label:<40} | {num_den:<15} | {item['rate_pct']:.2f}%")
    print("================================================================================")


if __name__ == "__main__":
    main()

