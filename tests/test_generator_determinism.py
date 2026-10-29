"""Automated tests for synthetic dataset seed determinism and export manifest repeatability."""

import filecmp
from datetime import datetime, timezone
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core import database as db_module
from backend.core.security import compute_payload_hash
from backend.generator.db_loader import DatabaseLoader
from backend.generator.exporter import DatasetExporter
from backend.generator.generator import (
    DEFAULT_SEED,
    DataGenerator,
    generate_audit_events_df,
    generate_completions_df,
    generate_courses_df,
    generate_credential_rules_df,
    generate_credentials_df,
    generate_issuers_df,
    generate_learners_df,
    generate_revocations_df,
    generate_verification_requests_df,
    inject_anomalies_df,
)
from backend.generator.validator import DatasetValidator
from backend.models.completion import CompletionRecord
from backend.models.credential import Credential
from backend.services.issuance import IssuanceService
from backend.services.payloads import build_credential_payload


def test_generator_seed_determinism_in_memory():
    """Verify that running DataGenerator with seed 20261022 twice produces identical records and hashes."""
    gen1 = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    gen2 = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    
    ds1 = gen1.generate()
    ds2 = gen2.generate()
    
    # 1. Row counts
    assert len(ds1.learners) == len(ds2.learners)
    assert len(ds1.courses) == len(ds2.courses)
    assert len(ds1.credentials) == len(ds2.credentials)
    assert len(ds1.revocations) == len(ds2.revocations)
    assert len(ds1.audit_events) == len(ds2.audit_events)
    
    # 2. Master entities equality
    for i in range(len(ds1.learners)):
        assert ds1.learners[i] == ds2.learners[i]
        
    for i in range(len(ds1.courses)):
        assert ds1.courses[i] == ds2.courses[i]
        
    # 3. Cryptographic payload hashes and signatures equality
    for i in range(len(ds1.credentials)):
        c1 = ds1.credentials[i]
        c2 = ds2.credentials[i]
        assert c1["public_id"] == c2["public_id"]
        assert c1["canonical_payload_hash"] == c2["canonical_payload_hash"]
        assert c1["issuer_signature"] == c2["issuer_signature"]
        assert c1["payload_snapshot"] == c2["payload_snapshot"]
        
    # 4. Audit events equality
    for i in range(len(ds1.audit_events)):
        assert ds1.audit_events[i] == ds2.audit_events[i]


def test_export_manifest_sha256_repeatability(tmp_path: Path):
    """Verify that exporting two separate runs with identical seed yields identical file checksums in manifest.sha256."""
    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"
    
    gen1 = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    gen2 = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    
    ds1 = gen1.generate()
    ds2 = gen2.generate()
    
    exp1 = DatasetExporter(ds1, dir1)
    exp2 = DatasetExporter(ds2, dir2)
    
    manifest1 = exp1.export_all(ds1.ground_truth)
    manifest2 = exp2.export_all(ds2.ground_truth)
    
    # Assert identical SHA-256 checksums across all exported files (including ground_truth and staging)
    assert manifest1 == manifest2
    assert "ground_truth.csv" in manifest1
    assert "ground_truth.json" in manifest1
    assert "credential_import_staging.csv" in manifest1
    
    # Check that manifest.sha256 content is identical
    content1 = (dir1 / "manifest.sha256").read_text(encoding="utf-8")
    content2 = (dir2 / "manifest.sha256").read_text(encoding="utf-8")
    assert content1 == content2


def test_validator_detects_clean_generated_dataset():
    """Verify that generated synthetic data has zero referential or date ordering violations."""
    gen = DataGenerator(seed=DEFAULT_SEED, scale=0.02)
    ds = gen.generate()
    
    validator = DatasetValidator(ds)
    report = validator.validate_all()
    
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.stats["credentials_count"] > 0
    assert report.stats["revocations_count"] > 0


def test_validator_rejects_malformed_public_ids():
    """Verify that DatasetValidator flags any public_id that violates the canonical regex formats."""
    gen = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    ds = gen.generate()
    ds.credentials[0]["public_id"] = "LEGACY-BAD-ID"
    ds.completions[0]["public_id"] = "CMP-LRN-000001-CRS-000001-02"

    report = DatasetValidator(ds).validate_all()
    assert report.is_valid is False
    assert any("credential public_id" in e for e in report.errors)
    assert any("completion public_id" in e for e in report.errors)


def test_generated_credential_matches_build_credential_payload_hash():
    """Verify that for a generated credential, build_credential_payload output hashes to canonical_payload_hash."""
    gen = DataGenerator(seed=DEFAULT_SEED, scale=0.01)
    ds = gen.generate()
    assert len(ds.credentials) > 0

    cred = ds.credentials[0]
    comp = next(c for c in ds.completions if c["id"] == cred["completion_id"])
    learner = next(l for l in ds.learners if l["id"] == comp["learner_id"])
    course = next(c for c in ds.courses if c["id"] == comp["course_id"])
    issuer = next(i for i in ds.issuers if i["id"] == cred["issuer_id"])

    rebuilt_payload = build_credential_payload(
        credential_id=cred["public_id"],
        issued_at=cred["issued_at"],
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

    assert rebuilt_payload == cred["payload_snapshot"]
    assert compute_payload_hash(rebuilt_payload) == cred["canonical_payload_hash"]


@pytest.mark.asyncio
async def test_db_loader_setval_continuity_and_database_reconciliation(db_session: AsyncSession):
    """Verify db_loader sequence setval() continuity (max baseline + 1) and DB reconciliation checks."""
    gen = DataGenerator(seed=DEFAULT_SEED, scale=0.02)
    ds = gen.generate()
    baseline_max_cred_num = len(ds.credentials)
    assert baseline_max_cred_num == 200
    assert ds.credentials[-1]["public_id"] == "CRD-2026-000200"

    # Load into credential_test_db via DatabaseLoader (binds to db_module.sync_engine -> credential_test_db)
    loader = DatabaseLoader(ds)
    stats = loader.load_all(truncate_first=True)
    assert stats["loaded_counts"]["credentials"] == 200

    # Find an eligible COMPLETED completion record that has not yet been issued a credential
    stmt = (
        select(CompletionRecord)
        .outerjoin(Credential, Credential.completion_id == CompletionRecord.id)
        .where(
            Credential.id.is_(None),
            CompletionRecord.status == "COMPLETED",
            CompletionRecord.assessment_score >= 90.0,
        )
        .limit(1)
    )
    unissued_comp = (await db_session.execute(stmt)).scalar_one()

    # Issue a new credential via IssuanceService; sequence must return max baseline + 1 (201)
    issued = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=unissued_comp.id,
        issuer_public_id="ISS-00001",
        issuer_private_key_pem=ds.issuer_private_keys[1],
        actor_id="TEST-REGISTRAR",
    )
    assert issued.public_id == f"CRD-2026-{baseline_max_cred_num + 1:06d}"
    assert issued.public_id == "CRD-2026-000201"

    # Run DatasetValidator.from_database against credential_test_db and verify all reconciliation checks pass
    db_validator = DatasetValidator.from_database(db_module.sync_engine)
    report = db_validator.validate_all()
    assert report.is_valid is True, f"DB Validation errors: {report.errors}"
    rec = report.stats["reconciliation"]
    assert rec["credentials_count"] == 201
    assert rec["credential_issued_events"] == 201
    assert rec["credentials_reconciled"] is True
    assert rec["revocations_reconciled"] is True
    assert rec["verifications_reconciled"] is True
    assert rec["unresolved_audit_targets"] == 0


def test_standalone_stage_functions_return_dataframes_and_realistic_variety():
    """Verify each of the 10 stage functions can be called standalone and returns a pandas DataFrame."""
    import random
    import numpy as np
    import pandas as pd
    from faker import Faker

    Faker.seed(DEFAULT_SEED)
    rng = random.Random(DEFAULT_SEED)
    np_rng = np.random.default_rng(DEFAULT_SEED)
    fake = Faker("en_IN")
    fake.seed_instance(DEFAULT_SEED)

    issuers_df = generate_issuers_df(seed=DEFAULT_SEED, rng=rng, fake=fake)
    courses_df = generate_courses_df(n_courses=50, rng=rng)
    rules_df = generate_credential_rules_df(courses_df=courses_df)
    learners_df = generate_learners_df(n_learners=100, fake=fake, rng=rng)
    completions_df = generate_completions_df(
        learners_df=learners_df,
        courses_df=courses_df,
        rules_df=rules_df,
        n_completions=200,
        rng=rng,
        np_rng=np_rng,
        config={"min_eligible_completions": 65},
    )
    credentials_df = generate_credentials_df(
        completions_df=completions_df,
        learners_df=learners_df,
        courses_df=courses_df,
        issuers_df=issuers_df,
        n_credentials=50,
        rng=rng,
    )
    revocations_df = generate_revocations_df(
        credentials_df=credentials_df,
        n_revocations=5,
        rng=rng,
    )
    verifications_df = generate_verification_requests_df(
        credentials_df=credentials_df,
        n_verifications=25,
        rng=rng,
    )
    audit_events_df = generate_audit_events_df(
        rules_df=rules_df,
        issuers_df=issuers_df,
        credentials_df=credentials_df,
        revocations_df=revocations_df,
        verifications_df=verifications_df,
    )
    ground_truth_df = inject_anomalies_df(
        credentials_df=credentials_df,
        completions_df=completions_df,
        learners_df=learners_df,
        courses_df=courses_df,
        issuers_df=issuers_df,
        verifications_df=verifications_df,
        audit_events_df=audit_events_df,
        rng=rng,
    )

    for df in (
        issuers_df,
        courses_df,
        rules_df,
        learners_df,
        completions_df,
        credentials_df,
        revocations_df,
        verifications_df,
        audit_events_df,
        ground_truth_df,
    ):
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    # Course titles unique, with department and level
    assert courses_df["title"].is_unique
    assert "department" in courses_df.columns
    assert "level" in courses_df.columns

    # Learner emails unique, duplicate names > 0
    assert learners_df["email"].is_unique
    assert learners_df["full_name"].duplicated().sum() > 0

    # Incomplete statuses present (IN_PROGRESS and FAILED)
    statuses = set(completions_df["status"])
    assert "COMPLETED" in statuses
    assert "IN_PROGRESS" in statuses
    assert "FAILED" in statuses


