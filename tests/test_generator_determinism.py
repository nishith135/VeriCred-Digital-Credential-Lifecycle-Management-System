"""Automated tests for synthetic dataset seed determinism and export manifest repeatability."""

import filecmp
from pathlib import Path
import pytest

from backend.generator.anomalies import generate_anomaly_fixtures
from backend.generator.exporter import DatasetExporter
from backend.generator.generator import DEFAULT_SEED, DataGenerator
from backend.generator.validator import DatasetValidator


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
    
    fixtures1, gt1 = generate_anomaly_fixtures(seed=DEFAULT_SEED)
    fixtures2, gt2 = generate_anomaly_fixtures(seed=DEFAULT_SEED)
    
    exp1 = DatasetExporter(ds1, dir1)
    exp2 = DatasetExporter(ds2, dir2)
    
    manifest1 = exp1.export_all(fixtures1, gt1)
    manifest2 = exp2.export_all(fixtures2, gt2)
    
    # Assert identical SHA-256 checksums across all exported files
    assert manifest1 == manifest2
    
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
