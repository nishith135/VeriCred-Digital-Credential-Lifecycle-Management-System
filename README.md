# VeriCred — Digital Credential Lifecycle Management System

**Tamper-Evident Academic Credential Lifecycle, Multi-Factor Verification, and Reproducible Synthetic Evaluation Platform.**

Developed for the **YottaFlex AI Candidate Evaluation Hackathon** within the official 72-hour submission window.

---

## 1. Executive Summary & Problem Solved

Traditional academic credentials suffer from critical vulnerability windows: transcript fraud, diploma mills, forgeable digital badges, and delayed or uncoordinated revocation notices.

**VeriCred** provides an end-to-end, zero-trust digital credential platform built on top of **PostgreSQL 17** and **FastAPI**:
- **Atomic Pre-Issuance Enforcement:** Academic eligibility rules (course completion, minimum 80.0% score, date window compliance) are enforced atomically at the database level. Ineligible or premature issuance is structurally blocked.
- **Multi-Factor Cryptographic Verification:** Independent 4-factor consensus (Existence, Canonical SHA-256 Digest Integrity, Ed25519 Asymmetric Issuer Signature, and Live Database Revocation Tombstone).
- **Tamper-Precedence Security Invariant:** A cryptographically altered credential payload is strictly identified and flagged as `TAMPERED`, taking precedence over revocation or active status.
- **Append-Only Immutability:** Revocation never erases historical evidence. Every lifecycle transition, verification attempt, and administrative sanction creates an append-only audit event.
- **Reproducible Synthetic Benchmark:** High-performance data generator producing 20,000 learners, 1,000 courses, 10,000 credentials, 300 revocations, and 5,000 verifications in **< 1.7 seconds** with 4 controlled failure vectors evaluated against segregated ground truth.

---

## 2. System Architecture & Tech Stack

```text
                               +------------------------------------------+
                               |        VeriCred Client Browser           |
                               | (HTML5 + Tailwind + HTMX 2.0 + Material) |
                               +--------------------+---------------------+
                                                    |
                                         HTTP / JSON / HTML Partial
                                                    |
                                                    v
+---------------------------------------------------------------------------------------------------+
| FastAPI Unified Server (backend.main:app)                                                         |
|                                                                                                   |
|  +--------------------+  +--------------------+  +--------------------+  +--------------------+   |
|  |   Verify Portal    |  | Credential Registry|  |    Audit Ledger    |  |    Anomaly Lab     |   |
|  |     (/verify)      |  |     (/registry)    |  |      (/audit)      |  |    (/anomalies)    |   |
|  +---------+----------+  +---------+----------+  +---------+----------+  +---------+----------+   |
|            |                       |                       |                       |              |
|  +---------v-----------------------v-----------------------v-----------------------v----------+   |
|  | Domain Services: EligibilityService | IssuanceService | VerificationService | Revocation    |   |
|  +--------------------------------------------------------------------------------------------+   |
|                                                    |                                              |
|                                  SQLAlchemy AsyncSession + asyncpg                                |
+----------------------------------------------------+----------------------------------------------+
                                                     |
                                                     v
                                +-----------------------------------------+
                                |  PostgreSQL 17.2 Database               |
                                |  - B-Tree Unique Public Identifiers     |
                                |  - Append-Only Audit Event Ledger       |
                                |  - Referential Integrity (RESTRICT FKs) |
                                +-----------------------------------------+
```

### Technology Highlights
- **Backend:** Python 3.13, FastAPI, Pydantic v2, Uvicorn
- **Persistence:** PostgreSQL 17, SQLAlchemy 2.0 (AsyncIO), Alembic
- **Cryptography:** Ed25519 asymmetric signatures (RFC 8032), canonical SHA-256 hashing
- **Frontend:** Jinja2 server-rendered templates, HTMX 2.0, Tailwind CSS runtime, Material Symbols, Geist & JetBrains Mono typography (zero Node.js/npm dependencies)
- **Testing:** Pytest, pytest-asyncio, HTTPX

---

## 3. Symmetrical Directory Structure

The repository enforces strict separation between backend business logic and presentation assets:

```text
digital_credential_lifecycle_management_system/
├── backend/                      # Python application package (formerly src/)
│   ├── api/
│   │   ├── v1/                   # RESTful API endpoints (issuance, verification, revocation, audit)
│   │   └── views/web.py          # HTML view router & HTMX partial handlers
│   ├── core/                     # App settings, DB engine pools, security primitives & exceptions
│   ├── generator/                # Seed-deterministic generator, db_loader, exporter, anomalies
│   ├── models/                   # SQLAlchemy ORM entities (Credential, Completion, Issuer, Audit...)
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── services/                 # Atomic domain workflows (Issuance, Verification, Revocation...)
│   └── main.py                   # FastAPI application factory and server entrypoint
│
├── frontend/                     # All presentation assets consolidated
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── base.html             # Master shell with sidebar navigation & live telemetry
│   │   ├── pages/                # verify.html, registry.html, audit.html, anomalies.html
│   │   └── partials/             # Reusable HTMX fragments (badges, tables, anomaly cards)
│   ├── static/                   # Static CSS and JS assets
│   └── ui/                       # Original Google Stitch UI reference designs
│
├── tests/                        # 36 automated test cases (100% passing)
├── alembic/                      # Database schema migration scripts
├── scripts/                      # CLI synthetic generation and database seeding scripts
└── docs/                         # Compliance logs, ADRs, test evidence, milestone status
```

---

## 4. Quickstart: Running the Unified Server

Because VeriCred uses FastAPI with server-side Jinja2 + HTMX, **a single command boots the entire stack** (no separate frontend build, webpack, or npm server required).

### Step 1: Clone & Setup Virtual Environment
```powershell
git clone https://github.com/nishith135/digital_credential_lifecycle_management_system.git
cd digital_credential_lifecycle_management_system

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 2: Environment Configuration
Create `.env` in the project root:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/credential_db
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/credential_db
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/credential_test_db
TEST_DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@localhost:5432/credential_test_db
APP_ENV=development
SECRET_KEY=yottaflex_secure_production_secret_key_2026
DEBUG=True
```

### Step 3: Run Database Migrations
```powershell
alembic upgrade head
```

### Step 4: Seed the Database with Synthetic Data
```powershell
python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports --load-db
```

### Step 5: Start the Application
```powershell
uvicorn backend.main:app --reload --port 8000
```

Open your browser to:
- **Public Verification Portal:** [http://localhost:8000/verify](http://localhost:8000/verify)
- **Credential Registry:** [http://localhost:8000/registry](http://localhost:8000/registry)
- **Immutable Audit Ledger:** [http://localhost:8000/audit](http://localhost:8000/audit)
- **Anomaly Stress-Test Lab:** [http://localhost:8000/anomalies](http://localhost:8000/anomalies)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 5. Web Interface Walkthrough

All 4 demonstration interfaces are adapted from the official Google Stitch prototypes with 100% interactive backend functionality:

### Screen 1: Public Verification Portal (`/` & `/verify`)
- **Real-Time Verification:** Enter any public credential ID (e.g. `CRD-2026-000001`) to trigger a sub-100ms multi-factor check via HTMX without full-page reload.
- **Quick-Fill Pills:** Click sample pills to immediately test authentic, revoked, or non-existent identifiers.
- **Tamper Simulation Accordion:** Expand the payload JSON editor, alter a single byte (e.g., degree title or GPA), and observe the system immediately reject the credential with `TAMPERED` status and SHA-256 digest mismatch.

### Screen 2: Credential Registry (`/registry`)
- **Live Database Metrics:** Real-time KPI counts queried directly from PostgreSQL (`total_issued`, `active_count`, `revoked_count`, `unique_learners`, `verifications_count`).
- **Dynamic Filtering:** Search by student name, credential ID, course title, or status.
- **Pre-Issuance Deck:** Drawer showing verified course completion records awaiting credential minting.
- **Administrative Revocation Modal:** Click "Revoke" on any active credential, select a sanction reason (`ACADEMIC_MISCONDUCT`, `ADMINISTRATIVE_ERROR`, `RESCINDED`), enter explanatory notes, and submit. The record transitions to `REVOKED` and creates an audit tombstone.

### Screen 3: Immutable Audit Ledger (`/audit`)
- **Forensic Journal:** Append-only timeline of all issuance, revocation, and verification actions.
- **Multi-Criteria Filter Toolbar:** Filter by event type, actor, or target entity ID.
- **Inline Payload Inspector:** Click "Payload" on any row to expand and view the canonical JSON diff and cryptographic attestation block.
- **Direct Exports:** Click "Export CSV" or "Export JSON" to immediately download the full audit journal directly from the browser.

### Screen 4: Cryptographic Anomaly Stress-Test Lab (`/anomalies`)
- **Live Fire Simulation Bench:** Demonstrates the 4 mandatory failure vectors against backend services:
  1. *Premature Issuance:* Score 68.5% < 80.0% rejected by Policy Assertion Engine (`INVALID_ISSUANCE`).
  2. *Duplicate ID Prevention:* Unique collision rejected by PostgreSQL idempotency guard (`REJECTED_DUPLICATE`).
  3. *Revoked Credential in Stale Cache:* Database tombstone check overrides stale edge cache (`REVOKED`).
  4. *Altered Payload Hash Mismatch:* Modified JSON payload detected by canonical SHA-256 digest (`TAMPERED`).
- **One-Click Batch Execution:** Click "Run All Scenarios" to run the entire battery simultaneously with pass/fail deltas and live streaming console telemetry.

---

## 6. Synthetic Data Generator & Anomaly Benchmark

The generator in `backend/generator/` provides bit-for-bit reproducible synthetic data using canonical PRNG seeds:

```powershell
# Generate full baseline (20k learners, 1k courses, 10k credentials, 300 revocations, 5k verifications)
python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports

# Validate referential integrity and topological consistency
python -m backend.generator.validator --export-dir ./exports
```

### Benchmark Metrics (Scale 1.0)
| Metric | Specification Target | Observed Performance | Status |
| :--- | :--- | :--- | :--- |
| **Generation Runtime** | < 60 seconds | **1.67 seconds** | **35x faster than target** |
| **Seed Determinism** | Exact bit-for-bit repeatability | Verified (`manifest.sha256`) | **100% Deterministic** |
| **Referential Integrity** | 0 orphan FKs | 0 errors across 47,600 rows | **Pass** |
| **Anomaly Recall** | 100% detection against ground truth | 4 / 4 anomalies detected | **100% Recall** |

---

## 7. Automated Testing Evidence

The test suite runs strictly against an isolated test database (`credential_test_db`) configured via `TEST_DATABASE_URL` and `TEST_DATABASE_URL_SYNC`:
- **Automatic Provisioning & Migration:** On startup, `tests/conftest.py` automatically creates `credential_test_db` if it does not exist and runs `alembic upgrade head` once per test session.
- **Per-Test Isolation:** All 9 tables in `credential_test_db` are truncated (`TRUNCATE ... RESTART IDENTITY CASCADE`) before and after every test so tests are completely independent.
- **Live Database Safety Guard:** A startup guard in `tests/conftest.py` verifies that the resolved database name ends with `_test` (e.g., `credential_test_db`) and immediately aborts via `pytest.exit(...)` if pointed at `credential_db` or any non-test database.

Run the automated test suite across all 10 test modules (37 tests):

```powershell
pytest -v
```

### Test Suite Execution Output
```text
tests/test_anomalies.py::test_anomaly_1_premature_issuance_detected PASSED          [  2%]
tests/test_anomalies.py::test_anomaly_2_duplicate_credential_id_detected PASSED    [  5%]
tests/test_anomalies.py::test_anomaly_3_revoked_verifies_as_active_in_stale_cache PASSED [  8%]
tests/test_anomalies.py::test_anomaly_4_altered_payload_detected_by_canonical_sha256 PASSED [ 11%]
tests/test_audit.py::test_audit_event_logging_and_multi_criteria_filtering PASSED  [ 13%]
tests/test_audit.py::test_audit_rest_api_endpoint_pagination_and_query PASSED     [ 16%]
tests/test_eligibility.py::test_eligibility_passing_boundary_80_percent PASSED     [ 19%]
tests/test_eligibility.py::test_eligibility_failing_boundary_79_99_percent PASSED  [ 22%]
tests/test_eligibility.py::test_eligibility_rejected_if_status_not_completed PASSED [ 25%]
tests/test_eligibility.py::test_eligibility_rejected_if_outside_rule_date_window PASSED [ 27%]
tests/test_generator_determinism.py::test_generator_seed_determinism_in_memory PASSED [ 30%]
tests/test_generator_determinism.py::test_export_manifest_sha256_repeatability PASSED [ 33%]
tests/test_generator_determinism.py::test_validator_detects_clean_generated_dataset PASSED [ 36%]
tests/test_health.py::test_health_check_endpoint PASSED                            [ 38%]
tests/test_issuance.py::test_atomic_issuance_success_and_cryptographic_verification PASSED [ 41%]
tests/test_issuance.py::test_duplicate_issuance_strictly_prevented PASSED         [ 44%]
tests/test_issuance.py::test_ineligible_issuance_raises_error PASSED               [ 47%]
tests/test_issuance.py::test_issuance_rest_api_endpoints PASSED                    [ 50%]
tests/test_revocation.py::test_authorized_revocation_success_and_audit PASSED    [ 52%]
tests/test_revocation.py::test_double_revocation_raises_error PASSED               [ 55%]
tests/test_revocation.py::test_revoking_nonexistent_credential_raises_error PASSED [ 58%]
tests/test_revocation.py::test_live_revocation_reflection_in_verification_api PASSED [ 61%]
tests/test_security.py::test_canonical_json_deterministic_ordering PASSED         [ 63%]
tests/test_security.py::test_payload_hash_tamper_detection PASSED                  [ 66%]
tests/test_security.py::test_ed25519_keypair_generation_and_verification PASSED   [ 69%]
tests/test_verification.py::test_verification_valid_active_credential PASSED     [ 72%]
tests/test_verification.py::test_verification_not_found_credential PASSED        [ 75%]
tests/test_verification.py::test_verification_detects_tampered_payload PASSED     [ 77%]
tests/test_verification.py::test_tampering_strictly_overrides_revocation PASSED   [ 80%]
tests/test_verification.py::test_verification_detects_invalid_issuer_signature PASSED [ 83%]
tests/test_verification.py::test_public_verification_rest_endpoint PASSED        [ 86%]
tests/test_web.py::test_web_verify_pages_load PASSED                               [ 88%]
tests/test_web.py::test_web_verify_htmx_post PASSED                                [ 91%]
tests/test_web.py::test_web_registry_pages_load PASSED                             [ 94%]
tests/test_web.py::test_web_audit_pages_load PASSED                                [ 97%]
tests/test_web.py::test_web_anomalies_lab PASSED                                   [100%]

============================= 36 passed in 5.66s ==============================
```

---

## 8. Governance, AI Disclosure & Compliance

- **[MASTER_SPEC.md](MASTER_SPEC.md):** Formal project requirements and business rules.
- **[AGENTS.md](AGENTS.md):** Workspace operating manual enforcing mandatory prompt logging and test verification.
- **[docs/AI_PROMPT_LOG.md](docs/AI_PROMPT_LOG.md):** Verbatim AI prompt history, models used, changed files, and validation results across all 19 prompt entries.
- **[docs/DECISIONS.md](docs/DECISIONS.md):** Complete record of Architecture Decision Records (ADR-001 through ADR-006).
- **[docs/TEST_EVIDENCE.md](docs/TEST_EVIDENCE.md):** Full empirical test evidence, benchmarks, and invariant verifications.
- **[docs/STATUS.md](docs/STATUS.md):** Milestone tracker and final submission certification.

---

## 9. License

MIT License. Designed and developed for the YottaFlex AI Submission.
