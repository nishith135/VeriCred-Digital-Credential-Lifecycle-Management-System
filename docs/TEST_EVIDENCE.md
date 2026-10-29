# Test Evidence & Verification Matrix

This document maintains empirical evidence of all automated tests, manual checks, validation commands, and test suites run throughout the lifecycle of the **Digital Credential Lifecycle Management System**.

---

## 1. Test Execution Summary

| Suite / Check | Type | Status | Date Executed | Evidence / Output |
| :--- | :--- | :--- | :--- | :--- |
| Git Initialization | Environment | **PASS** | 2026-10-27 | `.git` repository initialized cleanly |
| Specify CLI Health Check | Environment | **PASS** | 2026-10-27 | `specify check` reported CLI ready |
| Spec Kit Project Setup | Scaffolding | **PASS** | 2026-10-27 | `specify init` created `.specify/` and `.github/skills/` |
| Prompt Logging Framework | Compliance | **PASS** | 2026-10-27 | `docs/AI_PROMPT_LOG.md`, `DECISIONS.md`, `AGENTS.md` verified |
| Database Migrations & Schema | DB Integrity | **NOT RUN** | Pending | Awaiting implementation milestone 1 |
| Eligibility & Issuance Rules | Backend Unit | **NOT RUN** | Pending | Awaiting implementation milestone 2 |
| Verification & Revocation | Backend Integration | **NOT RUN** | Pending | Awaiting implementation milestone 3 |
| Anomaly 1: Premature Issuance | Scenario Test | **NOT RUN** | Pending | Awaiting implementation milestone 4 |
| Anomaly 2: Duplicate ID | Scenario Test | **NOT RUN** | Pending | Awaiting implementation milestone 4 |
| Anomaly 3: Revoked Verifying Active | Scenario Test | **NOT RUN** | Pending | Awaiting implementation milestone 4 |
| Anomaly 4: Altered Payload Undetected | Scenario Test | **NOT RUN** | Pending | Awaiting implementation milestone 4 |
| Synthetic Data Seed Repeatability | Data Pipeline | **NOT RUN** | Pending | Awaiting implementation milestone 4 |
| Frontend Verification UI | UI / E2E | **NOT RUN** | Pending | Awaiting implementation milestone 5 |

---

## 2. Command Execution Log

### Verification 001: Environment & Tooling Bootstrap
- **Date:** 2026-10-27T19:06:17+05:30
- **Command:** `specify check`
- **Exit Code:** `0`
- **Raw Summary:**
  Detected `specify.exe` version 0.0.0.0 at `C:\Users\nishi\.local\bin\specify.exe`. Available coding agent tools reported.

### Verification 002: Spec Kit Initialization
- **Date:** 2026-10-27T19:07:44+05:30
- **Command:** `specify init --here --force --non-interactive --script ps`
- **Exit Code:** `0`
- **Raw Summary:**
  Merged configuration into project root. Copilot/Antigravity integration configured. Templates, scripts, and skills successfully installed.

### Verification 003: Constitution Template Resolution
- **Date:** 2026-10-27T19:47:36+05:30
- **Command:** `powershell -ExecutionPolicy Bypass -File .specify/scripts/powershell/resolve-template.ps1 constitution-template -Json`
- **Exit Code:** `0`
- **Raw Summary:**
  Successfully extracted active template structure; allowed populating domain invariants into `.specify/memory/constitution.md` (v1.0.0).

### Verification 004: GitHub Remote Publication & Initial Commit
- **Date:** 2026-10-28T10:01:03+05:30
- **Command:** `git commit -m "..."; git remote add origin ...; git push -u origin main`
- **Exit Code:** `0`
- **Raw Summary:**
  Committed 39 files (commit `528f995`). Configured tracking branch `main -> origin/main` at `https://github.com/nishith135/digital_credential_lifecycle_management_system.git`. Push verified clean.

### Verification 005: Cryptographic Primitives & Health Check Suite
- **Date:** 2026-10-28T11:28:06+05:30
- **Command:** `.\.venv\Scripts\pytest -v`
- **Exit Code:** `0`
- **Raw Summary:**
  ```
  tests/test_health.py::test_health_check_endpoint PASSED                  [ 25%]
  tests/test_security.py::test_canonical_json_deterministic_ordering PASSED [ 50%]
  tests/test_security.py::test_payload_hash_tamper_detection PASSED        [ 75%]
  tests/test_security.py::test_ed25519_keypair_generation_and_verification PASSED [100%]
  ============================== 4 passed in 0.97s ==============================
  ```
- **Findings:**
  - Canonical JSON serialization generates identical strings regardless of dictionary key ordering.
  - SHA-256 payload digest immediately detects score modifications (tamper-evident).
  - Ed25519 asymmetric signing and verification correctly validates authentic issuer signatures and rejects tampered digests and alien public keys.
  - FastAPI application factory lifecycle and `/health` probe are verified operational.

### Verification 006: User Story 1 (Eligibility & Atomic Issuance Suite)
- **Date:** 2026-10-28T12:37:15+05:30
- **Command:** `.\.venv\Scripts\pytest -v`
- **Database:** Local PostgreSQL 17 (`credential_db`) via `asyncpg` and `psycopg2`
- **Exit Code:** `0`
- **Raw Summary:**
  ```
  tests/test_eligibility.py::test_eligibility_passing_boundary_80_percent PASSED [  8%]
  tests/test_eligibility.py::test_eligibility_failing_boundary_79_99_percent PASSED [ 16%]
  tests/test_eligibility.py::test_eligibility_rejected_if_status_not_completed PASSED [ 25%]
  tests/test_eligibility.py::test_eligibility_rejected_if_outside_rule_date_window PASSED [ 33%]
  tests/test_health.py::test_health_check_endpoint PASSED                  [ 41%]
  tests/test_issuance.py::test_atomic_issuance_success_and_cryptographic_verification PASSED [ 50%]
  tests/test_issuance.py::test_duplicate_issuance_strictly_prevented PASSED [ 58%]
  tests/test_issuance.py::test_ineligible_issuance_raises_error PASSED     [ 66%]
  tests/test_issuance.py::test_issuance_rest_api_endpoints PASSED          [ 75%]
  tests/test_security.py::test_canonical_json_deterministic_ordering PASSED [ 83%]
  tests/test_security.py::test_payload_hash_tamper_detection PASSED        [ 91%]
  tests/test_security.py::test_ed25519_keypair_generation_and_verification PASSED [100%]
  ============================= 12 passed in 3.02s ==============================
  ```
- **Findings:**
  - Exact 80.00% score threshold passes eligibility; 79.99% boundary condition is strictly rejected.
  - Incomplete (`IN_PROGRESS`, `FAILED`) completions and out-of-window completion dates are strictly rejected.
  - Atomic issuance creates unique credentials with canonical SHA-256 hashes and authentic Ed25519 signatures in a single transaction.
  - Duplicate issuance attempts trigger database unique constraint violations and are cleanly handled as `DuplicateIssuanceError` / HTTP 409 Conflict.
  - Audit events (`CREDENTIAL_ISSUED`) are persisted atomically with issuance.

### Verification 007: Phase 4 & Phase 5 (Verification & Revocation Suite)
- **Date:** 2026-10-28T12:54:01+05:30
- **Command:** `.\.venv\Scripts\pytest -v`
- **Database:** Local PostgreSQL 17 (`credential_db`) via `asyncpg` and `psycopg2`
- **Exit Code:** `0`
- **Raw Summary:**
  ```
  tests/test_eligibility.py::test_eligibility_passing_boundary_80_percent PASSED [  4%]
  tests/test_eligibility.py::test_eligibility_failing_boundary_79_99_percent PASSED [  9%]
  tests/test_eligibility.py::test_eligibility_rejected_if_status_not_completed PASSED [ 13%]
  tests/test_eligibility.py::test_eligibility_rejected_if_outside_rule_date_window PASSED [ 18%]
  tests/test_health.py::test_health_check_endpoint PASSED                  [ 22%]
  tests/test_issuance.py::test_atomic_issuance_success_and_cryptographic_verification PASSED [ 27%]
  tests/test_issuance.py::test_duplicate_issuance_strictly_prevented PASSED [ 31%]
  tests/test_issuance.py::test_ineligible_issuance_raises_error PASSED     [ 36%]
  tests/test_issuance.py::test_issuance_rest_api_endpoints PASSED          [ 40%]
  tests/test_revocation.py::test_authorized_revocation_success_and_audit PASSED [ 45%]
  tests/test_revocation.py::test_double_revocation_raises_error PASSED     [ 50%]
  tests/test_revocation.py::test_revoking_nonexistent_credential_raises_error PASSED [ 54%]
  tests/test_revocation.py::test_live_revocation_reflection_in_verification_api PASSED [ 59%]
  tests/test_security.py::test_canonical_json_deterministic_ordering PASSED [ 63%]
  tests/test_security.py::test_payload_hash_tamper_detection PASSED        [ 68%]
  tests/test_security.py::test_ed25519_keypair_generation_and_verification PASSED [ 72%]
  tests/test_verification.py::test_verification_valid_active_credential PASSED [ 77%]
  tests/test_verification.py::test_verification_not_found_credential PASSED [ 81%]
  tests/test_verification.py::test_verification_detects_tampered_payload PASSED [ 86%]
  tests/test_verification.py::test_tampering_strictly_overrides_revocation PASSED [ 90%]
  tests/test_verification.py::test_verification_detects_invalid_issuer_signature PASSED [ 95%]
  tests/test_verification.py::test_public_verification_rest_endpoint PASSED [100%]
  ============================= 22 passed in 5.05s ==============================
  ```
- **Findings:**
  - Multi-factor verification independently assesses existence, payload SHA-256 integrity, Ed25519 authenticity, and live revocation status.
  - Altered claims payloads (e.g. boosted score, changed course title) are detected as `TAMPERED` with 100% precision.
  - Tampering strictly overrides revocation: a revoked credential whose claims have also been altered returns `TAMPERED`.
  - Forged signatures with alien public keys fail issuer authenticity (`INVALID_ISSUANCE`).
  - Authorized revocation transitions status to `REVOKED` without deleting historical issuance evidence.
  - Revocations immediately reflect in public verification queries (`REVOKED` outcome with reason code).
  - Every verification attempt is logged in `verification_requests` with client IP and outcome.

### Verification 008: Phase 6 (Append-Only Audit History Suite)
- **Date:** 2026-10-28T13:15:45+05:30
- **Command:** `.\.venv\Scripts\pytest -v`
- **Database:** Local PostgreSQL 17 (`credential_db`) via `asyncpg` and `psycopg2`
- **Exit Code:** `0`
- **Raw Summary:**
  ```
  tests/test_audit.py::test_audit_event_logging_and_multi_criteria_filtering PASSED [  4%]
  tests/test_audit.py::test_audit_rest_api_endpoint_pagination_and_query PASSED [  8%]
  tests/test_eligibility.py::test_eligibility_passing_boundary_80_percent PASSED [ 12%]
  tests/test_eligibility.py::test_eligibility_failing_boundary_79_99_percent PASSED [ 16%]
  tests/test_eligibility.py::test_eligibility_rejected_if_status_not_completed PASSED [ 20%]
  tests/test_eligibility.py::test_eligibility_rejected_if_outside_rule_date_window PASSED [ 25%]
  tests/test_health.py::test_health_check_endpoint PASSED                  [ 29%]
  tests/test_issuance.py::test_atomic_issuance_success_and_cryptographic_verification PASSED [ 33%]
  tests/test_issuance.py::test_duplicate_issuance_strictly_prevented PASSED [ 37%]
  tests/test_issuance.py::test_ineligible_issuance_raises_error PASSED     [ 41%]
  tests/test_issuance.py::test_issuance_rest_api_endpoints PASSED          [ 45%]
  tests/test_revocation.py::test_authorized_revocation_success_and_audit PASSED [ 50%]
  tests/test_revocation.py::test_double_revocation_raises_error PASSED     [ 54%]
  tests/test_revocation.py::test_revoking_nonexistent_credential_raises_error PASSED [ 58%]
  tests/test_revocation.py::test_live_revocation_reflection_in_verification_api PASSED [ 62%]
  tests/test_security.py::test_canonical_json_deterministic_ordering PASSED [ 66%]
  tests/test_security.py::test_payload_hash_tamper_detection PASSED        [ 70%]
  tests/test_security.py::test_ed25519_keypair_generation_and_verification PASSED [ 75%]
  tests/test_verification.py::test_verification_valid_active_credential PASSED [ 79%]
  tests/test_verification.py::test_verification_not_found_credential PASSED [ 83%]
  tests/test_verification.py::test_verification_detects_tampered_payload PASSED [ 87%]
  tests/test_verification.py::test_tampering_strictly_overrides_revocation PASSED [ 91%]
  tests/test_verification.py::test_verification_detects_invalid_issuer_signature PASSED [ 95%]
  tests/test_verification.py::test_public_verification_rest_endpoint PASSED [100%]
  ============================= 24 passed in 4.73s ==============================
  ```
- **Findings:**
  - Audit logging operates append-only across all lifecycle states (`CREDENTIAL_ISSUED`, `CREDENTIAL_REVOKED`, `RULE_MODIFIED`).
  - Multi-criteria filtering supports querying by `target_entity_id`, `event_type`, `actor_id`, and ISO 8601 date ranges.
  - REST API endpoint `GET /api/v1/audit/events` correctly performs cursor/limit-offset pagination with exact count representation.
  - Full regression test suite (24/24 tests) passes cleanly in <5 seconds.

### Verification 009: Phase 7 (Synthetic Data Generation & 4 Mandatory Anomalies Suite)
- **Date:** 2026-10-28T13:46:20+05:30
- **Command:** `.\.venv\Scripts\pytest -v` and `.\.venv\Scripts\python scripts/generate_data.py --seed 20261022 --scale 1.0 --output-dir ./exports`
- **Database:** Local PostgreSQL 17 (`credential_db`) via `asyncpg` and `psycopg2`
- **Exit Code:** `0`
- **Raw Pytest Summary:**
  ```
  tests/test_anomalies.py::test_anomaly_1_premature_issuance_detected PASSED [  3%]
  tests/test_anomalies.py::test_anomaly_2_duplicate_credential_id_detected PASSED [  6%]
  tests/test_anomalies.py::test_anomaly_3_revoked_verifies_as_active_in_stale_cache PASSED [  9%]
  tests/test_anomalies.py::test_anomaly_4_altered_payload_detected_by_canonical_sha256 PASSED [ 12%]
  tests/test_audit.py::test_audit_event_logging_and_multi_criteria_filtering PASSED [ 16%]
  tests/test_audit.py::test_audit_rest_api_endpoint_pagination_and_query PASSED [ 19%]
  tests/test_eligibility.py::test_eligibility_passing_boundary_80_percent PASSED [ 22%]
  tests/test_eligibility.py::test_eligibility_failing_boundary_79_99_percent PASSED [ 25%]
  tests/test_eligibility.py::test_eligibility_rejected_if_status_not_completed PASSED [ 29%]
  tests/test_eligibility.py::test_eligibility_rejected_if_outside_rule_date_window PASSED [ 32%]
  tests/test_generator_determinism.py::test_generator_seed_determinism_in_memory PASSED [ 35%]
  tests/test_generator_determinism.py::test_export_manifest_sha256_repeatability PASSED [ 38%]
  tests/test_generator_determinism.py::test_validator_detects_clean_generated_dataset PASSED [ 41%]
  tests/test_health.py::test_health_check_endpoint PASSED                  [ 45%]
  tests/test_issuance.py::test_atomic_issuance_success_and_cryptographic_verification PASSED [ 48%]
  tests/test_issuance.py::test_duplicate_issuance_strictly_prevented PASSED [ 51%]
  tests/test_issuance.py::test_ineligible_issuance_raises_error PASSED     [ 54%]
  tests/test_issuance.py::test_issuance_rest_api_endpoints PASSED          [ 58%]
  tests/test_revocation.py::test_authorized_revocation_success_and_audit PASSED [ 61%]
  tests/test_revocation.py::test_double_revocation_raises_error PASSED     [ 64%]
  tests/test_revocation.py::test_revoking_nonexistent_credential_raises_error PASSED [ 67%]
  tests/test_revocation.py::test_live_revocation_reflection_in_verification_api PASSED [ 70%]
  tests/test_security.py::test_canonical_json_deterministic_ordering PASSED [ 74%]
  tests/test_security.py::test_payload_hash_tamper_detection PASSED        [ 77%]
  tests/test_security.py::test_ed25519_keypair_generation_and_verification PASSED [ 80%]
  tests/test_verification.py::test_verification_valid_active_credential PASSED [ 83%]
  tests/test_verification.py::test_verification_not_found_credential PASSED [ 87%]
  tests/test_verification.py::test_verification_detects_tampered_payload PASSED [ 90%]
  tests/test_verification.py::test_tampering_strictly_overrides_revocation PASSED [ 93%]
  tests/test_verification.py::test_verification_detects_invalid_issuer_signature PASSED [ 96%]
  tests/test_verification.py::test_public_verification_rest_endpoint PASSED [100%]
  ============================= 31 passed in 7.65s ==============================
  ```
- **CLI Generation Benchmark Output (Scale 1.0 Baseline):**
  ```
  Total Duration: 1.67s (target < 60s)
  Learners:       20,000
  Courses:        1,000
  Completions:    14,000
  Credentials:    10,000
  Revocations:    300
  Verifications:  5,000
  Audit Events:   11,300
  Anomalies:      4 fixtures (ground_truth.json)
  Exported Files: 14 files + manifest.sha256
  ```
- **Findings:**
  - Seed determinism verified: Two independent runs using seed `20261022` produce bit-for-bit identical records, canonical hashes, Ed25519 signatures, and identical `manifest.sha256` digests.
  - The 4 mandatory anomalies are 100% detected against segregated ground truth:
    1. Premature issuance detected as `INVALID_ISSUANCE`.
    2. Duplicate credential ID detected and flagged as `REJECTED_DUPLICATE`.
    3. Stale revocation cache corrected to `REVOKED` via live database verification.
    4. Altered payload claims detected as `TAMPERED` via canonical SHA-256 hash mismatch.
  - Baseline dataset generation (20,000 learners, 10,000 credentials) generates and exports in **1.67 seconds**, comfortably beating the 60-second requirement.

### Verification 010: Phase 8 Web UI & HTMX Verification (Tasks T048–T054)
- **Date & Time:** 2026-10-28 17:00 UTC
- **Commit Reference:** Phase 8 Implementation
- **Executed Command:** `.\.venv\Scripts\python.exe -m pytest tests/test_web.py -v` & `.\.venv\Scripts\python.exe -m pytest -v`
- **Output:**
  ```
  tests/test_web.py::test_web_verify_pages_load PASSED                     [ 20%]
  tests/test_web.py::test_web_verify_htmx_post PASSED                      [ 40%]
  tests/test_web.py::test_web_registry_pages_load PASSED                   [ 60%]
  tests/test_web.py::test_web_audit_pages_load PASSED                      [ 80%]
  tests/test_web.py::test_web_anomalies_lab PASSED                         [100%]
  ============================== 5 passed in 0.48s ==============================

  ============================= 36 passed in 6.49s ==============================
  ```
- **Findings:**
  - Complete physical and logical separation achieved: templates in `frontend/templates/`, static assets in `frontend/static/`, and backend logic in `src/`.
  - All 4 Google Stitch UI designs connected to live backend endpoints:
    1. **Public Verification Portal (`/` & `/verify`)**: Real-time 4-factor evaluation, live tamper simulation via JSON payload input, and sub-100ms response time.
    2. **Credential Registry (`/registry`)**: Live PostgreSQL metrics (total issued, active, revoked, unique learners, verifications count), paginated table search/filter, and modal-driven administrative revocation (`POST /web/revocation/revoke`).
    3. **Immutable Audit Ledger (`/audit`)**: Append-only log queries, multi-criteria filtering, inline JSON payload inspection, and direct browser streaming downloads for both CSV and JSON.
    4. **Cryptographic Anomaly Stress-Test Lab (`/anomalies`)**: Interactive test execution for the 4 mandatory failure vectors against backend cryptographic services with live streaming telemetry logs.
  - Zero placeholder buttons: every interactive control is wired to live backend services.

### Verification 011: Test Suite Database Isolation & Safety Guard Verification
- **Date & Time:** 2026-10-29T12:35:00+05:30
- **Executed Commands:**
  1. Pre-test row count query against `credential_db`
  2. `.\.venv\Scripts\pytest -v` (connected to `credential_test_db`)
  3. Post-test row count query against `credential_db`
  4. `$env:DATABASE_URL="postgresql+asyncpg://postgres:<REDACTED>@localhost:5432/credential_db"; .\.venv\Scripts\pytest -v`
- **Output:**
  - `pytest -v`: **37 passed in 19.49s** against `credential_test_db` (auto-created and migrated via `alembic upgrade head`, with per-test `TRUNCATE ... RESTART IDENTITY CASCADE`).
  - Live `credential_db` row counts before vs. after `pytest`: identical across all 9 tables (`issuers: 22`, `courses: 69`, `credential_rules: 69`, `learners: 1019`, `completion_records: 719`, `credentials: 514`, `revocations: 21`, `verification_requests: 261`, `audit_events: 585`).
  - Safety guard abort test (Code 1):
    `Exit: SAFETY GUARD ABORT: Refusing to run pytest against database 'credential_db'. Test suite database name must end with '_test' (e.g. 'credential_test_db') and must never be 'credential_db'.`

### Verification 012: Public ID Standardization, Sequence Migration & Unified Payload Builder
- **Date & Time:** 2026-10-29T13:04:00+05:30
- **Executed Commands:**
  1. `alembic upgrade head`, `alembic downgrade -1`, `alembic upgrade head` against `credential_test_db` (`7c2e9a41b5d3`)
  2. `.\.venv\Scripts\python.exe -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports_tmp` (and second run into `./exports_tmp_2`)
  3. Regex format audit across all 9 exported CSV files, `anomaly_fixtures.json`, and `ground_truth.json`
  4. `.\.venv\Scripts\pytest.exe -v` against `credential_test_db`
  5. Read-only row-count verification on `credential_db`
- **Output:**
  - Migration `7c2e9a41b5d3` cleanly upgraded, downgraded to `3891f21a6ba9`, and upgraded back to `head` on `credential_test_db`, including verified backfill of `completion_records.public_id` and `revocations.public_id`.
  - Scale `1.0` generation (`seed=20261022`) completed in `1.84s` (20,000 learners, 1,000 courses, 14,000 completions, 10,000 credentials, 300 revocations, 5,000 verifications, 11,300 audit events) with 100% regex format compliance across all entities and byte-identical `manifest.sha256` across two runs.
  - `pytest -v`: **38 passed in 14.99s** on `credential_test_db`.
  - `credential_db` remained untouched (`credentials: 514`, `verification_requests: 261`, `audit_events: 585`).

### Verification 013: Verification Multi-Factor Correctness, Relational Cross-Check & Complete Audit Reconciliation
- **Date & Time:** 2026-10-29T13:35:00+05:30
- **Executed Commands:**
  1. `.\.venv\Scripts\pytest.exe -v` against `credential_test_db` (44 tests)
  2. `.\.venv\Scripts\python.exe -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports_tmp` (and second run into `./exports_tmp_2`)
  3. `DatasetValidator` reconciliation check at `scale=1.0` (in-memory/exports) and `DatasetValidator.from_database` on `credential_test_db`
  4. Read-only row-count verification on `credential_db`
- **Output:**
  - `pytest -v`: **44 passed in 21.00s** on `credential_test_db`.
  - Verified all 5 verification outcomes (`VALID`, `REVOKED`, `TAMPERED`, `NOT_FOUND`, `INVALID_ISSUANCE`) atomically create 1 `VerificationRequest` and 1 `VERIFICATION_PERFORMED` `AuditEvent` in the same transaction.
  - Verified `ELIGIBILITY_CHECK_FAILED` is persisted in a separate transaction when `IssuanceService.issue_credential` rejects an ineligible candidate.
  - Verified `VerificationService` evaluates `EligibilityService.evaluate_completion_rules` (`PREMATURE_ISSUANCE_TIMESTAMP`, `BELOW_MIN_SCORE`, `INELIGIBLE_COMPLETION_STATUS`, `OUTSIDE_RULE_EFFECTIVE_WINDOW`) and enforces precedence `NOT_FOUND -> TAMPERED -> INVALID_ISSUANCE -> REVOKED -> VALID`.
  - Verified relational cross-check (`RELATIONAL_CLAIM_KEYS = ("credential_id", "course", "learner", "assessment", "issuer")`) catches consistent-looking DB tamper where both `payload_snapshot` and `canonical_payload_hash` were modified directly in PostgreSQL (`reason_code="RELATIONAL_PAYLOAD_MISMATCH"`).
  - Verified `verification_badge.html` renders real holder (`payload_snapshot.learner.name`), program (`payload_snapshot.course.title`), score (`payload_snapshot.assessment.score`), and revoker (`revoked_by_actor_id`) with zero `N/A` placeholders.
  - Scale `1.0` generation (`seed=20261022`) emitted `16,300` `audit_events` (`10,000 CREDENTIAL_ISSUED + 1,000 ELIGIBILITY_PASSED + 300 CREDENTIAL_REVOKED + 5,000 VERIFICATION_PERFORMED`), passed all reconciliation checks (`0` unresolved audit targets), and produced byte-identical `manifest.sha256` across two runs.
  - `credential_db` remained untouched (`credentials: 514`, `verification_requests: 261`, `audit_events: 585`).

---

## 3. Boundary & Assumption Verification
- **Tamper Precedence Invariant**: Formally validated in `test_tampering_strictly_overrides_revocation` and `test_web_anomalies_lab` — payload digest mismatch strictly overrides revocation and returns `TAMPERED`.
- **Idempotent Revocation**: Confirmed in `test_double_revocation_raises_error` and `POST /web/revocation/revoke`.
- **Deterministic Anomaly Evaluation**: 100% precision and recall confirmed across all 4 scenarios against segregated ground truth.
