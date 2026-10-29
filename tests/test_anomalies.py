"""Automated evaluation of the four injected anomaly scenarios, dry-run verification, and evaluation metrics."""

import ast
from pathlib import Path
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.evaluation import EvaluationRunner
from backend.generator.db_loader import DatabaseLoader
from backend.generator.exporter import DatasetExporter
from backend.generator.generator import DEFAULT_SEED, DataGenerator
from backend.models import Credential
from backend.services.verification import VerificationService


def _scan_forbidden_ground_truth_imports(target_paths: list[Path]) -> list[str]:
    """Statically scan Python files for imports or references to ground truth or generator anomalies."""
    forbidden_modules = {"backend.generator.anomalies", "anomalies", "ground_truth"}
    violations: list[str] = []

    for base_path in target_paths:
        files = [base_path] if base_path.is_file() else list(base_path.rglob("*.py"))
        for py_file in files:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if any(f in alias.name for f in forbidden_modules):
                            violations.append(f"{py_file}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    if any(f in mod for f in forbidden_modules):
                        violations.append(f"{py_file}: from {mod} import ...")
                    for alias in node.names:
                        if any(f in alias.name for f in forbidden_modules):
                            violations.append(f"{py_file}: from {mod} import {alias.name}")
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if "ground_truth" in node.value or "credential_import_staging" in node.value:
                        violations.append(f"{py_file}: string literal {node.value!r}")
    return violations


def test_static_ground_truth_leakage_guard(tmp_path: Path):
    """Ensure backend/services, backend/api, and backend/core never import or reference ground truth."""
    prod_dirs = [
        Path("backend/services"),
        Path("backend/api"),
        Path("backend/core"),
    ]
    assert _scan_forbidden_ground_truth_imports(prod_dirs) == []

    # Verify the scanner catches a service file that imports ground truth
    bad_service = tmp_path / "leaky_service.py"
    bad_service.write_text(
        "from backend.generator.anomalies import load_ground_truth\n",
        encoding="utf-8",
    )
    caught = _scan_forbidden_ground_truth_imports([bad_service])
    assert len(caught) >= 1


@pytest.mark.asyncio
async def test_dry_run_verification_leaves_all_9_table_counts_unchanged(
    db_session: AsyncSession,
):
    """Verify that VerificationService.verify_credential(..., persist=False) leaves all 9 table counts unchanged."""
    gen = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    ds = gen.generate()
    DatabaseLoader(ds).load_all(truncate_first=True)

    counts_before = await EvaluationRunner.count_all_tables(db_session)
    assert counts_before["credentials"] == 100

    # Verify an existing credential and a non-existent credential with persist=False
    res_found = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id=ds.credentials[0]["public_id"],
        persist=False,
    )
    assert res_found.outcome in ("VALID", "REVOKED", "INVALID_ISSUANCE", "TAMPERED")

    res_missing = await VerificationService.verify_credential(
        db=db_session,
        credential_public_id="CRD-2026-999999",
        persist=False,
    )
    assert res_missing.outcome == "NOT_FOUND"

    counts_after = await EvaluationRunner.count_all_tables(db_session)
    assert counts_after == counts_before


@pytest.mark.asyncio
async def test_all_four_injected_anomalies_detected_on_loaded_dataset(
    db_session: AsyncSession,
    tmp_path: Path,
):
    """Verify all 4 injected anomaly types in a generated dataset are detected with 100% accuracy."""
    gen = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    ds = gen.generate()
    DatabaseLoader(ds).load_all(truncate_first=True)
    DatasetExporter(ds, tmp_path).export_all(ds.ground_truth)

    # 1. PREMATURE_ISSUANCE -> INVALID_ISSUANCE
    premature_gt = [g for g in ds.ground_truth if g["issue_type"] == "PREMATURE_ISSUANCE"]
    assert len(premature_gt) == 2
    for g in premature_gt:
        res = await VerificationService.verify_credential(
            db=db_session,
            credential_public_id=g["entity_public_id"],
            persist=False,
        )
        assert res.outcome == "INVALID_ISSUANCE"
        assert "PREMATURE_ISSUANCE_TIMESTAMP" in res.factors.failed_subchecks

    # 2. DUPLICATE_CREDENTIAL_ID -> rejected by unique constraint in rolled-back savepoint
    dup_gt = [g for g in ds.ground_truth if g["issue_type"] == "DUPLICATE_CREDENTIAL_ID"]
    assert len(dup_gt) == 2
    assert len(ds.credential_import_staging) == 2
    for s_row in ds.credential_import_staging:
        rejected = False
        try:
            async with db_session.begin_nested():
                db_session.add(
                    Credential(
                        public_id=s_row["public_id"],
                        completion_id=s_row["completion_id"],
                        issuer_id=s_row["issuer_id"],
                        issued_at=s_row["issued_at"],
                        canonical_payload_hash=s_row["canonical_payload_hash"],
                        issuer_signature=s_row["issuer_signature"],
                        payload_snapshot=s_row["payload_snapshot"],
                        status=s_row["status"],
                    )
                )
                await db_session.flush()
        except IntegrityError:
            rejected = True
        assert rejected is True

    # 3. REVOKED_VERIFIES_AS_ACTIVE -> REVOKED (even though credentials.status == ACTIVE)
    stale_rev_gt = [g for g in ds.ground_truth if g["issue_type"] == "REVOKED_VERIFIES_AS_ACTIVE"]
    assert len(stale_rev_gt) == 2
    for g in stale_rev_gt:
        cred_row = next(c for c in ds.credentials if c["public_id"] == g["entity_public_id"])
        assert cred_row["status"] == "ACTIVE"
        res = await VerificationService.verify_credential(
            db=db_session,
            credential_public_id=g["entity_public_id"],
            persist=False,
        )
        assert res.outcome == "REVOKED"
        assert res.factors.is_revoked is True

    # 4. ALTERED_PAYLOAD_NOT_DETECTED -> TAMPERED (both snapshot-only and snapshot+hash halves)
    altered_gt = [g for g in ds.ground_truth if g["issue_type"] == "ALTERED_PAYLOAD_NOT_DETECTED"]
    assert len(altered_gt) == 2
    for g in altered_gt:
        res = await VerificationService.verify_credential(
            db=db_session,
            credential_public_id=g["entity_public_id"],
            persist=False,
        )
        assert res.outcome == "TAMPERED"
        assert res.factors.payload_hash_matches is False

    # 5. Full EvaluationRunner check
    report = await EvaluationRunner.run_evaluation(db_session, exports_dir=tmp_path)
    assert report["row_count_delta"] == 0
    assert report["metrics"]["overall_accuracy"]["numerator"] == 102
    assert report["metrics"]["overall_accuracy"]["denominator"] == 102
    assert report["metrics"]["false_acceptance_rate"]["numerator"] == 0
    assert report["metrics"]["false_acceptance_rate"]["denominator"] == 6
    assert report["metrics"]["false_rejection_rate"]["numerator"] == 0
