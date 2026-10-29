# VeriCred Validation Summary

Empirical verification evidence and acceptance metrics for the **Digital Credential Lifecycle Management System**, produced from the full-scale generation (`scale=1.0`, `seed=20261022`) loaded into PostgreSQL (`credential_db`).

---

## 1. Generation & Database Ingestion

- **Command:** `python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports --load-db`
- **Seed:** `20261022`
- **Scale:** `1.0`
- **Generation & Load Time:** `7.82 seconds` (target < 60s)
- **Database Engine:** PostgreSQL 17 (`credential_db`)

### Operational Table Counts (`credential_db`)

| Table | Row Count | First Public ID | Last Public ID | Notes |
|---|---|---|---|---|
| `issuers` | `12` | `ISS-00001` | `ISS-00012` | 2 retired issuers (`ISS-00003`, `ISS-00007`) with successor routing |
| `courses` | `1,000` | `CRS-000001` | `CRS-001000` | 0 duplicate titles, realistic department/level attributes |
| `credential_rules` | `1,000` | — | — | 1 rule per course (minimum passing score 80.0%) |
| `learners` | `20,000` | `LRN-000001` | `LRN-020000` | Realistic names (`en_IN`), natural duplicate names allowed, unique emails |
| `completion_records` | `15,300` | `CMP-LRN-000001-CRS-000484` | `CMP-LRN-020000-CRS-000570` | 11,370 COMPLETED (74.31%), 2,345 IN_PROGRESS (15.33%), 1,585 FAILED (10.36%) |
| `credentials` | `10,000` | `CRD-2026-000001` | `CRD-2026-010000` | Constant 2026 year segment; 1,370 COMPLETED records unissued |
| `revocations` | `300` | `REV-CRD-2026-000012-01` | `REV-CRD-2026-009949-01` | 300 revoked credentials (280 status REVOKED, 20 REVOKED_VERIFIES_AS_ACTIVE) |
| `verification_requests` | `5,000` | `VER-2026-000001` | `VER-2026-005000` | Historical audit logs of verification queries |
| `audit_events` | `16,302` | `EVT-00000001` | `EVT-00016302` | Full lifecycle audit trail (10,000 issued + 300 revoked + 5,000 verifications + 2 retirements) |

---

## 2. Validator Runs & Reconciliation

### A. Validator on Export Directory (`./exports`)

```bash
python -m backend.generator.validator --export-dir ./exports --with-ground-truth
```

```json
{
  "is_valid": true,
  "source": "export_dir (./exports)",
  "with_ground_truth": true,
  "errors_count": 0,
  "warnings_count": 0,
  "errors": [],
  "stats": {
    "reconciliation": {
      "credential_issued_events": 10000,
      "credentials_count": 10000,
      "credentials_reconciled": true,
      "credential_revoked_events": 300,
      "revocations_count": 300,
      "revocations_reconciled": true,
      "verification_performed_events": 5000,
      "verifications_count": 5000,
      "verifications_reconciled": true,
      "unresolved_audit_targets": 0
    },
    "ground_truth_reconciliation": {
      "total_labelled": 80,
      "premature_issuance_matched": 20,
      "duplicate_credential_id_matched": 20,
      "revoked_verifies_as_active_matched": 20,
      "altered_payload_not_detected_matched": 20,
      "unlabelled_violations": 0
    }
  }
}
```

### B. Validator on Live Database (`credential_db`)

```bash
python -m backend.generator.validator --db live --with-ground-truth
```

```json
{
  "is_valid": true,
  "source": "database (live)",
  "with_ground_truth": true,
  "errors_count": 0,
  "warnings_count": 0,
  "errors": [],
  "stats": {
    "reconciliation": {
      "credential_issued_events": 10000,
      "credentials_count": 10000,
      "credentials_reconciled": true,
      "credential_revoked_events": 300,
      "revocations_count": 300,
      "revocations_reconciled": true,
      "verification_performed_events": 5000,
      "verifications_count": 5000,
      "verifications_reconciled": true,
      "unresolved_audit_targets": 0
    },
    "ground_truth_reconciliation": {
      "total_labelled": 80,
      "premature_issuance_matched": 20,
      "duplicate_credential_id_matched": 20,
      "revoked_verifies_as_active_matched": 20,
      "altered_payload_not_detected_matched": 20,
      "unlabelled_violations": 0
    }
  }
}
```

---

## 3. Evaluation Report on Live Database (`credential_db`)

```bash
python -m backend.evaluation.run --db live --out ./exports
```

```text
================================================================================
  Evaluation Report (live database) -> exports\evaluation_report.json
================================================================================
  Total Elapsed Time:       12343.78 ms
  Credentials Evaluated:    10,000
  Staging Duplicates:       20
  Row Count Delta (9 tbls): 0
--------------------------------------------------------------------------------
  Metric                                   | Num / Den       | Rate      
--------------------------------------------------------------------------------
  Overall Accuracy                         | 10020 / 10020   | 100.00%
  Detection: PREMATURE_ISSUANCE            | 20 / 20         | 100.00%
  Detection: DUPLICATE_CREDENTIAL_ID       | 20 / 20         | 100.00%
  Detection: REVOKED_VERIFIES_AS_ACTIVE    | 20 / 20         | 100.00%
  Detection: ALTERED_PAYLOAD_NOT_DETECTED  | 20 / 20         | 100.00%
  False Acceptance Rate (FAR)              | 0 / 60          | 0.00%
  False Rejection Rate (FRR)               | 0 / 9660        | 0.00%
  Revocation Detection Rate                | 300 / 300       | 100.00%
  Tamper Detection Rate                    | 20 / 20         | 100.00%
================================================================================
```

---

## 4. Deterministic Reproducibility

Two consecutive runs with `--seed 20261022` produce byte-identical checksum manifests across all 15 export files:

```text
MANIFEST_MATCH: IDENTICAL
dd5867094afebdd42286e4ffdb19b09e3517be1b0ebf450f34e163d07f870556  audit_events.csv
6b3cc53eb9bd43481972e2578f5894071b563d20f51d0f97663c57ada8e090a0  completion_records.csv
15709b8032898b120e99a9fc8298ec2db41245fbe7eddc03f9f28c71e5c18cb6  courses.csv
612474aba343af388b4ad64c9b14c6051882079da1faa3563373a9239b1171fd  credential_import_staging.csv
5a8a78b7cebcc1c1faa9db79b6ff631ddcc8ec65f7c99ba83b601cb9cdc92a30  credential_rules.csv
78a5a1d1cb1dbd768099d8c23d40780c6995c0b242f3cb971606ec8e2948600f  credentials.csv
8ffa7bc5b4f6609a111073f30d67ff4167eb5c35849a17800334110a30462369  dataset_metadata.json
3b1b71e039452a2b1ad72557bd66e62b4339bd394b60d15ca73a0c3ef27c3159  ground_truth.csv
882298e92f9e1520b9557829fa73d46f631e6e22f099595e48206818a360eed5  ground_truth.json
cb4fcab707f84084363dd7c1657f50f1c2da4878ccf9ed8228084d79ad961d34  issuers.csv
826bda4ba8626fc7d71fc54fccb271a0b0438ef6c9cd7abb673ef720f4461e43  learners.csv
a59a3ed7b1466a7980e464cafc07a460dc7a4e37db3f73d5a4704c8d2c33d562  revocations.csv
e114eec66545021587cbe620e34877b9e50e628df537f7eef2c2f844dedc67eb  seed_data.sql
42b18a459a59a9d9cd5123ddba6d8dcb549b6d7c30198911e8abb4820ca30dc7  summary.json
3c1a1f83e5effee94df86469cd821b45fe5f4b86170e0c0eac2561cc8283293d  verification_requests.csv
```

---

## 5. Source Manifest & Data Integrity Statement

All records in this dataset are **100% synthetically generated** using:
- **Python `Faker` (`en_IN` locale)** for realistic learner names.
- **NumPy & Pandas** for distributions, scores (`normal(75.0, 14.0)`), and topological record generation.
- **Cryptographic Primitives (`cryptography.hazmat`)** for canonical SHA-256 payload digests and Ed25519 asymmetric signatures.

**Zero External or Private PII:**
- No real individual personal data, proprietary school rosters, or external databases were queried, scraped, or ingested.
- All email addresses follow deterministic patterns (`firstname.lastname.id@edu-network.in`).
- Ground-truth anomaly labels are strictly segregated in `ground_truth.csv`/`ground_truth.json` and are never stored in operational database columns.

