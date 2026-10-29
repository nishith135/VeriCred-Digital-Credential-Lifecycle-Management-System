# VeriCred — Codebase Context & Audit Report

**Generated:** 2026-10-29  
**Scope:** Read-only full-stack audit of repository structure, architecture, data model, generator, RBAC, verification logic, presentation layer, test suite, known issues, and requirement gaps against `MASTER_SPEC.md`.

---

## 1. Repository Map

Excluded: `.venv/`, `.git/`, `__pycache__/`, `.pytest_cache/`, and `.agents/skills/` (third-party UI skill assets).

```text
c:\Projects\digital_credential_lifecycle_management_system\
├── .env                                                   (551 B)
├── .env.example                                           (619 B)
├── .gitignore                                             (766 B)
├── AGENTS.md                                              (13,616 B)
├── MASTER_SPEC.md                                         (35,850 B)
├── README.md                                              (16,650 B)
├── alembic.ini                                            (1,539 B)
├── pytest.ini                                             (167 B)
├── requirements.txt                                       (319 B)
├── .specify/
│   └── memory/constitution.md                             (6,100 B)
├── alembic/
│   ├── env.py                                             (2,293 B)
│   ├── script.py.mako                                     (635 B)
│   └── versions/
│       └── 20261028_0703_3891f21a6ba9_create_initial_credential_lifecycle_.py (12,907 B)
├── backend/
│   ├── __init__.py                                        (0 B)
│   ├── main.py                                            (3,360 B)
│   ├── api/
│   │   ├── v1/
│   │   │   ├── audit.py                                   (2,225 B)
│   │   │   ├── issuance.py                                (2,488 B)
│   │   │   ├── revocation.py                              (2,177 B)
│   │   │   └── verification.py                            (1,272 B)
│   │   └── views/
│   │       └── web.py                                     (28,497 B)
│   ├── core/
│   │   ├── config.py                                      (1,551 B)
│   │   ├── database.py                                    (2,086 B)
│   │   ├── exceptions.py                                  (4,054 B)
│   │   ├── rbac.py                                        (2,750 B)
│   │   └── security.py                                    (4,803 B)
│   ├── generator/
│   │   ├── anomalies.py                                   (10,928 B)
│   │   ├── cli.py                                         (5,262 B)
│   │   ├── db_loader.py                                   (4,275 B)
│   │   ├── exporter.py                                    (8,841 B)
│   │   ├── generator.py                                   (19,119 B)
│   │   └── validator.py                                   (8,278 B)
│   ├── models/
│   │   ├── __init__.py                                    (685 B)
│   │   ├── audit.py                                       (1,634 B)
│   │   ├── completion.py                                  (2,568 B)
│   │   ├── course.py                                      (1,722 B)
│   │   ├── credential.py                                  (3,006 B)
│   │   ├── credential_rule.py                             (2,282 B)
│   │   ├── issuer.py                                      (1,503 B)
│   │   ├── learner.py                                     (1,664 B)
│   │   ├── revocation.py                                  (1,789 B)
│   │   └── verification.py                                (2,303 B)
│   ├── schemas/
│   │   ├── __init__.py                                    (1,263 B)
│   │   ├── audit.py                                       (1,176 B)
│   │   ├── credential.py                                  (3,694 B)
│   │   ├── revocation.py                                  (1,165 B)
│   │   └── verification.py                                (1,857 B)
│   ├── services/
│   │   ├── __init__.py                                    (464 B)
│   │   ├── audit.py                                       (3,776 B)
│   │   ├── eligibility.py                                 (3,941 B)
│   │   ├── issuance.py                                    (6,512 B)
│   │   ├── revocation.py                                  (3,873 B)
│   │   └── verification.py                                (7,265 B)
│   ├── static/ (empty dirs: css/, js/)
│   └── templates/ (empty dirs: pages/, partials/)
├── data/
│   └── ground_truth_anomalies.json                        (2,005 B)
├── docs/
│   ├── AI_PROMPT_LOG.md                                   (87,710 B)
│   ├── BACKEND_INTEGRATION_REPORT.md                      (9,110 B)
│   ├── DECISIONS.md                                       (8,618 B)
│   ├── STATUS.md                                          (2,033 B)
│   └── TEST_EVIDENCE.md                                   (19,423 B)
├── exports/ (generated data files — names and sizes)
│   ├── anomaly_fixtures.json                              (5,839 B)
│   ├── audit_events.csv                                   (120,970 B)
│   ├── completion_records.csv                             (57,645 B)
│   ├── courses.csv                                        (5,071 B)
│   ├── credential_rules.csv                               (5,542 B)
│   ├── credentials.csv                                    (372,439 B)
│   ├── dataset_metadata.json                              (379 B)
│   ├── ground_truth.json                                  (2,005 B)
│   ├── issuers.csv                                        (1,519 B)
│   ├── learners.csv                                       (95,776 B)
│   ├── manifest.sha256                                    (1,183 B)
│   ├── revocations.csv                                    (1,460 B)
│   ├── seed_data.sql                                      (13,744 B)
│   ├── summary.json                                       (397 B)
│   └── verification_requests.csv                          (35,772 B)
├── frontend/
│   ├── static/css/veri-design.css                         (2,000 B)
│   ├── templates/
│   │   ├── base.html                                      (11,744 B)
│   │   ├── pages/
│   │   │   ├── anomalies.html                             (7,132 B)
│   │   │   ├── audit.html                                 (9,390 B)
│   │   │   ├── login.html                                 (8,481 B)
│   │   │   ├── registry.html                              (15,465 B)
│   │   │   └── verify.html                                (7,238 B)
│   │   └── partials/
│   │       ├── anomaly_result.html                        (4,438 B)
│   │       ├── audit_table.html                           (4,567 B)
│   │       ├── registry_table.html                        (4,390 B)
│   │       └── verification_badge.html                    (9,926 B)
│   └── ui/ (Google Stitch reference prototypes)
│       ├── anomalystresstest.txt                          (49,192 B)
│       ├── auditledger.txt                                (40,940 B)
│       ├── credentialregistry.txt                         (58,638 B)
│       └── verifycredential.txt                           (51,176 B)
├── scripts/
│   ├── generate_data.py                                   (289 B)
│   └── pip_install.py                                     (706 B)
├── specs/001-credential-lifecycle-system/
│   ├── data-model.md                                      (8,140 B)
│   ├── plan.md                                            (9,788 B)
│   ├── quickstart.md                                      (2,919 B)
│   ├── research.md                                        (6,897 B)
│   ├── spec.md                                            (21,994 B)
│   ├── tasks.md                                           (14,120 B)
│   ├── checklists/requirements.md                         (2,128 B)
│   └── contracts/api_contracts.md                         (4,713 B)
└── tests/
    ├── conftest.py                                        (3,546 B)
    ├── test_anomalies.py                                  (8,478 B)
    ├── test_audit.py                                      (4,681 B)
    ├── test_eligibility.py                                (3,874 B)
    ├── test_generator_determinism.py                      (3,463 B)
    ├── test_health.py                                     (683 B)
    ├── test_issuance.py                                   (7,072 B)
    ├── test_revocation.py                                 (7,104 B)
    ├── test_security.py                                   (2,832 B)
    ├── test_verification.py                               (8,622 B)
    └── test_web.py                                        (4,547 B)
```

---

## 2. Context Report

### a. Architecture & Layer Boundary Violations

- **Verified Stack:**
  - **Backend:** FastAPI (`backend/main.py:47-99`), Pydantic v2 (`backend/schemas/`), SQLAlchemy 2.0 (`backend/models/`, `backend/core/database.py`), Alembic (`alembic/`).
  - **Database:** PostgreSQL 17 (`credential_db` at `localhost:5432`), using `postgresql+asyncpg` for FastAPI requests and `postgresql+psycopg2` for Alembic migrations and the synchronous CLI data loader (`backend/core/database.py:35-73`).
  - **Cryptography:** `cryptography` library implementing Ed25519 key generation/signing/verification and canonical JSON SHA-256 hashing (`backend/core/security.py`).
  - **Web UI:** Server-rendered Jinja2 templates + HTMX 2.0.4 + Tailwind CSS CDN (`frontend/templates/base.html:20-53`), served directly by FastAPI on `127.0.0.1:8000`.
- **Layer Organization:**
  - **Entrypoint (`backend/main.py`):** Configures CORS, mounts `/static` (`frontend/static`), registers `DomainException` handler, and includes `web_router`, `issuance_router`, `verification_router`, `revocation_router`, and `audit_router`.
  - **REST Routers (`backend/api/v1/`):** `issuance.py`, `verification.py`, `revocation.py`, `audit.py`.
  - **Web View Router (`backend/api/views/web.py`):** Handles HTML page routes (`/`, `/verify`, `/registry`, `/audit`, `/anomalies`, `/login`, `/role/switch`), HTMX partials (`/web/*`), and CSV/JSON audit export (`/web/export/audit`).
  - **Domain Services (`backend/services/`):** `EligibilityService`, `IssuanceService`, `VerificationService`, `RevocationService`, `AuditService`. There is no separate repository/DAO layer; services execute SQLAlchemy queries directly against `AsyncSession`.
- **Layer Boundary Violations:**
  1. **Direct ORM / SQL queries in routers instead of services:**
     - `backend/api/v1/revocation.py:42-63`: `get_credential_audit_history` executes `select(AuditEvent)` directly in the route handler rather than calling `AuditService.query_events`.
     - `backend/api/views/web.py:113-128, 173-181, 205-266, 360-410, 423-451, 501-502, 552-570`: Executes direct SQLAlchemy `select`, `func.count`, and multi-table `join` queries across `Credential`, `CompletionRecord`, `Learner`, `Course`, `Issuer`, `Revocation`, `VerificationRequest`, and `AuditEvent` inside the view router.
  2. **Business rules hardcoded in the view router:**
     - `backend/api/views/web.py:244-253` hardcodes eligibility rules (`CompletionRecord.status == "COMPLETED"`, `CompletionRecord.assessment_score >= 80.0`) instead of using `EligibilityService`.
  3. **Anomaly evaluation logic and ground-truth access embedded in the view router:**
     - `backend/api/views/web.py:577-709` (`_evaluate_single_anomaly`) calls `generate_anomaly_fixtures()` (which returns both fixtures and `ground_truth`), performs inline ad-hoc checks instead of calling domain services, and hardcodes `actual = "REVOKED"` for Scenario 3 (`web.py:656`).

---

### b. Data Model

Defined in `backend/models/` and migrated in `alembic/versions/20261028_0703_3891f21a6ba9_create_initial_credential_lifecycle_.py`:

| Table (`__tablename__`) | Model File | PK | Public ID / Unique Columns | Foreign Keys | Check Constraints / Enums |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `issuers` | `backend/models/issuer.py` | `id` (Int) | `public_id` (UQ) | None | `status IN ('ACTIVE', 'SUSPENDED', 'RETIRED')` |
| `courses` | `backend/models/course.py` | `id` (Int) | `public_id` (UQ) | None | `status IN ('ACTIVE', 'ARCHIVED')` |
| `credential_rules` | `backend/models/credential_rule.py` | `id` (Int) | None | `course_id -> courses.id` (`RESTRICT`) | `effective_to > effective_from`, `min_score BETWEEN 0 AND 100` |
| `learners` | `backend/models/learner.py` | `id` (Int) | `public_id` (UQ), `email` (UQ) | None | `status IN ('ACTIVE', 'SUSPENDED')` |
| `completion_records` | `backend/models/completion.py` | `id` (Int) | **None** (no `public_id` column) | `learner_id -> learners.id`, `course_id -> courses.id`, `rule_id -> credential_rules.id` (all `RESTRICT`) | `assessment_score BETWEEN 0 AND 100`, `status IN ('COMPLETED', 'IN_PROGRESS', 'FAILED')` |
| `credentials` | `backend/models/credential.py` | `id` (Int) | `public_id` (UQ), `completion_id` (UQ) | `completion_id -> completion_records.id` (`RESTRICT`), `issuer_id -> issuers.id` (`RESTRICT`) | `status IN ('ACTIVE', 'REVOKED')` |
| `revocations` | `backend/models/revocation.py` | `id` (Int) | **None** (no `public_id` column), `credential_id` (UQ) | `credential_id -> credentials.id` (`RESTRICT`) | `reason_code IN ('ACADEMIC_MISCONDUCT', 'ADMINISTRATIVE_ERROR', 'RESCINDED', 'OTHER')` |
| `verification_requests` | `backend/models/verification.py` | `id` (Int) | `public_id` (UQ) | `credential_id -> credentials.id` (Nullable, `SET NULL`) | `outcome IN ('VALID', 'REVOKED', 'TAMPERED', 'NOT_FOUND', 'INVALID_ISSUANCE')` |
| `audit_events` | `backend/models/audit.py` | `id` (Int) | `event_id` (UQ) | None (stores `target_entity_type`, `target_entity_id`) | None |

- **How Audit Events Are Written:**
  - **Issuance (`backend/services/issuance.py:131-153`):** Creates `AuditEvent(event_type="CREDENTIAL_ISSUED", target_entity_type="Credential", target_entity_id=credential_public_id, ...)` in the same DB transaction as `Credential`.
  - **Revocation (`backend/services/revocation.py:84-100`):** Creates `AuditEvent(event_type="CREDENTIAL_REVOKED", target_entity_type="Credential", target_entity_id=credential_public_id, ...)` in the same DB transaction as `Revocation`.
  - **Verification (`backend/services/verification.py:60-72, 129-141`):** Writes a `VerificationRequest` row to `verification_requests`, but **never** writes an `AuditEvent` row to `audit_events`.
  - **Generator (`backend/generator/generator.py:395-449`):** Generates `AuditEvent` rows for `RULE_MODIFIED`, `CREDENTIAL_ISSUED`, and `CREDENTIAL_REVOKED`, but **never** for `verification_requests`.

---

### c. Generator

- **CLI Entrypoints:**
  - `python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports [--load-db] [--truncate] [--no-validate]` (`backend/generator/cli.py:20-58`)
  - `python scripts/generate_data.py` (`scripts/generate_data.py:1-12`)
- **Defaults & Scale:**
  - `DEFAULT_SEED = 20261022` and `REFERENCE_DATETIME = 2026-10-22T12:00:00+00:00` in `backend/generator/generator.py:31-32`. (Note: `backend/core/config.py:37` and `.env.example:13` define `DEFAULT_SEED=42`, which is not used by `generator.py`).
  - Default `scale = 1.0` produces: 7 issuers, 1,000 courses, 1,000 credential rules, 20,000 learners, 14,000 completions, 10,000 credentials, 300 revocations, 5,000 verification requests, and 11,300 audit events (`backend/generator/generator.py:106-135`).
- **Seed & Determinism:**
  - Uses isolated `random.Random(seed)`, `Faker("en_IN")` with `fake.seed_instance(seed)`, deterministic Ed25519 key generation via `SHA-256(f"issuer_{idx}_seed_{self.seed}")`, and fixed `REFERENCE_DATETIME`.
- **ID Formats (Spec vs Actual):**

| Entity | Problem Statement Spec | Generator (`backend/generator/generator.py`) | Runtime Service (`backend/services/`) |
| :--- | :--- | :--- | :--- |
| Credential | `CRD-2026-000001` | `CRED-2026-000001` (`generator.py:276`) | `CRED-{year}-{8_hex}` (`issuance.py:37`) |
| Learner | `LRN-000001` | `LRN-000001` (`generator.py:213`) | N/A |
| Course | `CRS-000001` | `CRS-00001` (5-digit pad, `generator.py:178`) | N/A |
| Completion | `CMP-<learner-id>-<course-id>` | **Missing** (integer `id` only, `generator.py:241-251`) | **Missing** (integer `id` only) |
| Verification | `VER-2026-000001` | `VRF-000001` (`generator.py:382`) | `VRF-{8_hex}` (`verification.py:44`) |
| Revocation | `REV-<credential-id>-01` | **Missing** (integer `id` only, `generator.py:336-343`) | **Missing** (integer `id` only) |
| Issuer | `ISS-...` | `ISS-00001` (`generator.py:158`) | N/A |
| AuditEvent | `EVT-...` | `EVT-00000001` (`generator.py:449`) | `EVT-{10_hex}` (`audit.py:23`) |

- **Edge Cases & Ground Truth:**
  - Generated by `generate_anomaly_fixtures()` in `backend/generator/anomalies.py:40-250`.
  - Produces 4 anomaly fixtures (`CASE-ANOMALY-001` through `004`: `PREMATURE_ISSUANCE`, `DUPLICATE_CREDENTIAL_ID`, `REVOKED_VERIFIES_AS_ACTIVE`, `ALTERED_PAYLOAD_TAMPERING`) exported to `exports/anomaly_fixtures.json`, and 4 ground-truth labels exported to `exports/ground_truth.json` (and duplicated at `data/ground_truth_anomalies.json`).
- **Output Files (`backend/generator/exporter.py`):**
  - 9 CSV files (`issuers.csv`, `courses.csv`, `credential_rules.csv`, `learners.csv`, `completion_records.csv`, `credentials.csv`, `revocations.csv`, `verification_requests.csv`, `audit_events.csv`).
  - 4 JSON files (`ground_truth.json`, `anomaly_fixtures.json`, `dataset_metadata.json`, `summary.json`).
  - 1 SQL file (`seed_data.sql`) — **Incomplete:** `exporter.py:160-188` only writes `INSERT` statements for `issuers` and `courses`, omitting the remaining 7 tables.
  - 1 SHA-256 checksum manifest (`manifest.sha256`).

---

### d. Auth / Roles (RBAC)

- **Mechanism (`backend/core/rbac.py`):**
  - Defines 3 personas: `registrar` ("University Registrar"), `verifier` ("Public Verifier"), and `auditor` ("Compliance Auditor").
  - Stored in a plain-text cookie `vericred_role` (set by `GET/POST /role/switch` in `backend/api/views/web.py:78-97`) or overridden by query param `?role=...`.
  - **Default Role (`backend/core/rbac.py:57-65`):** When no cookie or query param is present, `get_current_role` defaults to `Role.REGISTRAR.value` (`"registrar"`).
- **Route-by-Route Permission Table:**

| Route | Method | UI Role Behavior | Backend / API Enforcement |
| :--- | :--- | :--- | :--- |
| `/`, `/verify` | `GET` | Public verification portal; defaults header badge to `University Registrar` if no cookie is set | None (Public) |
| `/web/verify` | `POST` | HTMX verification | None (Public) |
| `/login` | `GET` | Displays 3 persona switcher cards | None |
| `/role/switch` | `GET, POST` | Sets `vericred_role` cookie and redirects | None (Unauthenticated; anyone can switch to any role) |
| `/registry` | `GET` | Hides active "Revoke" button in `registry_table.html:67` if `not is_registrar` | **None** (Verifier/Auditor can access `/registry`) |
| `/web/registry/table` | `GET` | Same template condition | **None** |
| `/web/revocation/revoke` | `POST` | Revoke modal only rendered/opened for `is_registrar` | **Enforced** (`backend/api/views/web.py:314-326` checks `role_def.get("can_revoke")`; returns HTTP 200 with error toast if false) |
| `/audit` | `GET` | None (`can_inspect_audit` in `rbac.py:28,39,50` is never checked) | **None** (Verifier can access `/audit`) |
| `/web/audit/table` | `GET` | None | **None** |
| `/web/export/audit` | `GET` | None (`can_export` in `rbac.py:27,38,49` is never checked) | **None** (Verifier can download audit exports) |
| `/anomalies` | `GET` | None | **None** |
| `/web/anomalies/run/*` | `POST` | None | **None** |
| `/api/v1/issuance/evaluate` | `POST` | N/A (REST API) | **None** |
| `/api/v1/issuance/issue` | `POST` | N/A (REST API) | **None** (Checks `X-Issuer-Private-Key` header presence, no role check) |
| `/api/v1/revocation/revoke` | `POST` | N/A (REST API) | **None** (Completely unauthenticated; bypasses `/web/revocation/revoke` check) |
| `/api/v1/revocation/audit/{id}` | `GET` | N/A (REST API) | **None** |
| `/api/v1/verification/verify` | `POST` | N/A (REST API) | None (Public by design) |
| `/api/v1/audit/events` | `GET` | N/A (REST API) | **None** |

---

### e. Verification Logic

Implemented in `VerificationService.verify_credential` (`backend/services/verification.py:35-178`):
1. **Existence (`verification.py:47-88`):** Queries `Credential` by `public_id` with `selectinload(Credential.issuer)` and `selectinload(Credential.revocation)`. If not found, inserts a `VerificationRequest` row (`outcome="NOT_FOUND"`) and returns `NOT_FOUND`.
2. **Payload Integrity (`verification.py:90-94`):** Uses `presented_payload` if passed; otherwise uses `credential.payload_snapshot` from the DB. Computes `compute_payload_hash(payload_to_check)` (`backend/core/security.py:19-41`, recursive key-sorted compact JSON SHA-256) and checks equality with `credential.canonical_payload_hash`.
   - *Gap:* When `presented_payload` is omitted (standard ID lookup), it hashes `credential.payload_snapshot` rather than reconstructing claims from relational tables (`Learner`, `Course`, `CompletionRecord`), so direct DB mutation of `payload_snapshot` + `canonical_payload_hash` or relational columns would not be cross-checked.
3. **Issuer Authenticity (`verification.py:96-101`):** Verifies `credential.issuer_signature` (Base64 Ed25519 signature over UTF-8 bytes of `canonical_payload_hash`) against `credential.issuer.public_key_pem` (`backend/core/security.py:112-132`).
4. **Revocation Status (`verification.py:103-104`):** Checks `(credential.status == "REVOKED") or (credential.revocation is not None)`.
5. **Rule / Eligibility / Premature Issuance Check:** **Missing.** `VerificationService` never loads `CompletionRecord` or `CredentialRule` and never checks whether `issued_at < completion_timestamp` or `assessment_score < min_score`. `INVALID_ISSUANCE` is only returned when Ed25519 signature verification fails (`verification.py:111-114`).
6. **Outcome Precedence (`verification.py:107-126`):** `NOT_FOUND` $\rightarrow$ `TAMPERED` $\rightarrow$ `INVALID_ISSUANCE` $\rightarrow$ `REVOKED` $\rightarrow$ `VALID`.

---

### f. Presentation Layer

| Page | Route & Templates | APIs / HTMX Endpoints Called | Data Displayed & Hardcoded / Defective Elements |
| :--- | :--- | :--- | :--- |
| **Base Shell** | `frontend/templates/base.html` | `/role/switch`, `/login` | Sidebar navigation, top header, persona dropdown. Hardcoded sidebar badges: `"Security Invariants: Active"`, `"Canonical Hashes: Enforced"`. |
| **Verify** | `GET /`, `GET /verify` (`pages/verify.html`, `partials/verification_badge.html`) | `POST /web/verify` | Search box, 3 quick-test sample buttons (`Sample Active Valid`, `Sample Revoked`, `Simulate Tampered Payload`), and an adversarial JSON tamper textarea (`verify.html:53-95`). **Bug in `verification_badge.html:124-144`:** Template references `result.credential_details.learner.name`, `.course.title`, and `.assessment.score`, which do not exist on `result.credential_details` (they live inside `result.credential_details.payload_snapshot`), causing Holder, Program, and Score to always display **`N/A`** / **`N/A%`**. Also `verification_badge.html:162` reads `result.revocation_details.revoked_by` instead of `revoked_by_actor_id`, rendering blank. |
| **Registry** | `GET /registry` (`pages/registry.html`, `partials/registry_table.html`) | `GET /web/registry/table`, `POST /web/revocation/revoke` | Shows 4 DB count cards (`total_issued`, `active_count`, `revoked_count`, `verifications_count`), search/status filter bar, 20-row table, and revocation modal. **Gaps:** `web.py:244-266` queries `eligible_candidates` for a "Pre-Issuance Deck" claimed in `README.md:159`, but `registry.html` never renders `eligible_candidates` and has no UI to issue credentials. Status dropdown defaults to `Status: ACTIVE` (`registry.html:145`), while initial page load queries all statuses (`web.py:241`). No pagination controls in UI. |
| **Audit** | `GET /audit` (`pages/audit.html`, `partials/audit_table.html`) | `GET /web/audit/table`, `GET /web/export/audit` | Shows 4 DB count cards (`total_events`, `total_issuances`, `total_revocations`, `total_verifications`), filter bar, and 50-row table with collapsible JSON details. Filter dropdown includes `VERIFICATION_PERFORMED` and `ELIGIBILITY_CHECK_FAILED` (`audit.html:123-124`), neither of which is ever logged to `audit_events`. |
| **Anomalies** | `GET /anomalies` (`pages/anomalies.html`, `partials/anomaly_result.html`) | `POST /web/anomalies/run/{scenario_id}`, `POST /web/anomalies/run-all` | **Hardcoded stats & fake traces:** Top 4 KPI cards (`4 Vectors`, `100% / 4 / 4 Passing`, `< 15 ms`, `Sandboxed`) are static HTML in `anomalies.html:35-83`. In `web.py:596-708`, scenario parameters and console traces are hardcoded strings (e.g., `"Candidate": "Chris Doe (STU-772910)"` when fixture 1 is `"Alice Premature"`, `"Queried live tombstone ledger: Block #1,849,202..."`), and Scenario 3 (`web.py:656`) hardcodes `actual = "REVOKED"` without calling `VerificationService` or the database. |
| **Login** | `GET /login` (`pages/login.html`) | `GET /role/switch?role=...` | 3 persona selection cards (`University Registrar`, `Public Verifier`, `Compliance Auditor`). |

---

### g. Tests and Validation

- **Existing Test Suite (`tests/`):**
  - 10 test files containing 37 tests (`test_anomalies.py`, `test_audit.py`, `test_eligibility.py`, `test_generator_determinism.py`, `test_health.py`, `test_issuance.py`, `test_revocation.py`, `test_security.py`, `test_verification.py`, `test_web.py`). All 37 pass when run via `pytest`.
- **Critical Defects in Testing & Validation:**
  1. **Tests Permanently Mutate the Live Database (`tests/conftest.py:26-45`):**
     - `test_async_engine` connects to `settings.DATABASE_URL` (`credential_db`). Although `db_session` calls `await session.rollback()` on teardown, the fixtures (`sample_issuer`, `sample_academic_setup`) and service methods (`IssuanceService.issue_credential`, `RevocationService.revoke_credential`, `VerificationService.verify_credential`, `AuditService.log_event`) call `await db.commit()` directly on the session. Every `pytest` run permanently inserts test records into `credential_db`.
  2. **Validator CLI Command in README Is a No-Op (`backend/generator/validator.py`):**
     - `README.md:188` documents `python -m backend.generator.validator --export-dir ./exports`, but `backend/generator/validator.py` has no `if __name__ == "__main__":` block or CLI argument parser; running it does nothing and exits 0.
  3. **Missing Evaluation Metrics Script (`MASTER_SPEC.md` §12.3):**
     - No script computes issuance accuracy, verification accuracy, revocation detection rate, tampering detection rate, false acceptance rate (FAR), or false rejection rate (FRR) with denominators from actual outputs.

---

### h. Status of Each Known Issue

1. **IDs are generated as `CRED-2026-...` instead of `CRD-2026-...`**
   - **Status:** **CONFIRMED**
   - **Evidence:**
     - `backend/generator/generator.py:276`: `public_id = f"CRED-2026-{cred_idx:06d}"`
     - `backend/services/issuance.py:37`: `return f"CRED-{year}-{random_suffix}"`
     - Additionally, verification IDs use `VRF-000001` (`generator.py:382`) / `VRF-{8_hex}` (`verification.py:44`) instead of `VER-2026-000001`, and `CompletionRecord` (`backend/models/completion.py`) and `Revocation` (`backend/models/revocation.py`) lack `public_id` columns for `CMP-<learner-id>-<course-id>` and `REV-<credential-id>-01`.

2. **Generated volume is far below spec (about 514 credentials, 261 verification requests)**
   - **Status:** **CONFIRMED**
   - **Evidence:**
     - `exports/dataset_metadata.json:2-16` and `exports/summary.json:2-16` show the dataset was generated with `"scale": 0.05` (producing 1,000 learners, 50 courses, 500 credentials, 15 revocations, 250 verifications, 565 audit events).
     - Running `pytest` against `credential_db` (`tests/conftest.py:26-45`) committed 14 additional test credentials and 11 additional test verification requests, resulting in exactly **514 credentials** and **261 verification requests** in the live PostgreSQL database.

3. **Registry shows 514 issued but Audit Ledger shows 513 issuance events, and verification requests are not appearing as audit events (0)**
   - **Status:** **CONFIRMED**
   - **Evidence:**
     - **514 vs 513 discrepancy:**
       - `scale=0.05` seeded 500 `Credential` rows and 500 `CREDENTIAL_ISSUED` `AuditEvent` rows.
       - `pytest` runs committed 12 credentials via `IssuanceService.issue_credential` (+12 `Credential`, +12 `AuditEvent`), plus **2 direct `Credential` ORM inserts without `AuditEvent`s** in `tests/test_anomalies.py:113-133` (`test_anomaly_3`) and `tests/test_anomalies.py:192-203` (`test_anomaly_4`) $\rightarrow$ $500 + 12 + 2 = 514$ `Credential` rows.
       - `tests/test_audit.py:32-40` (`test_audit_event_logging_and_multi_criteria_filtering`) committed 1 synthetic `CREDENTIAL_ISSUED` `AuditEvent` without creating a `Credential` row $\rightarrow$ $500 + 12 + 1 = 513$ `CREDENTIAL_ISSUED` rows in `audit_events`.
     - **0 verification audit events:**
       - Neither `VerificationService.verify_credential` (`backend/services/verification.py:60-72, 129-141`) nor `DataGenerator._generate_audit_events` (`backend/generator/generator.py:395-449`) ever writes `VERIFICATION_PERFORMED` events to `audit_events`.
       - `backend/api/views/web.py:443-449` queries `AuditEvent.event_type.like("%VERIFICATION%")` on `/audit`, which always returns `0`.

4. **Role state is inconsistent: the public verify page shows "University Registrar" while the persona page says Public Verifier**
   - **Status:** **CONFIRMED**
   - **Evidence:**
     - `backend/core/rbac.py:57-65` (`get_current_role`) defaults to `Role.REGISTRAR.value` (`"registrar"` = `"University Registrar"`) whenever no `vericred_role` cookie is set. Visiting `/verify` without a cookie displays `"University Registrar"` in the top-right dropdown and sidebar (`frontend/templates/base.html:114, 142`).
     - Additionally, `get_current_role` checks `request.query_params.get("role")` before `request.cookies.get("vericred_role")` (`rbac.py:59-64`), and `/role/switch` (`web.py:88`) falls back to `request.headers.get("referer")` when `redirect` is not passed (such as from the header dropdown `base.html:148`).

5. **Role checks may exist only in the UI; the API may not enforce them**
   - **Status:** **CONFIRMED**
   - **Evidence:**
     - None of the `/api/v1/*` routers (`backend/api/v1/issuance.py`, `revocation.py`, `audit.py`) import or enforce RBAC. `POST /api/v1/revocation/revoke` can be called by any unauthenticated client or any role.
     - In `backend/api/views/web.py`, only `POST /web/revocation/revoke` (`web.py:314-326`) checks `can_revoke`. `GET /registry`, `GET /audit`, and `GET /web/export/audit` have no role checks on the server.

6. **The UI contains test controls, hardcoded stats, and claims that may not be backed by real computation**
   - **Status:** **CONFIRMED**
   - **Evidence:**
     - `frontend/templates/pages/verify.html:53-95`: Contains quick-sample buttons and an adversarial payload tampering JSON editor on the public verification portal.
     - `frontend/templates/pages/anomalies.html:35-83`: Hardcodes `4 Vectors`, `100% / 4 / 4 Passing`, `< 15 ms`, and `Sandboxed`.
     - `backend/api/views/web.py:596-708`: Hardcodes fake parameter labels (`"Chris Doe (STU-772910)"`), fake engine traces (`"Block #1,849,202. Stale L2 edge cache purged"`), and hardcodes `actual = "REVOKED"` in Scenario 3 (`web.py:656`).

---

### i. Additional Problems Found

1. **Verification Badge UI Displays `"N/A"` for Holder, Course, and Score (`frontend/templates/partials/verification_badge.html:124-144`):**
   - `VerificationService.verify_credential` (`backend/services/verification.py:144-151`) returns `credential_details` with `payload_snapshot` nested inside it, whereas `verification_badge.html` tries to read `.learner.name`, `.course.title`, and `.assessment.score` directly off `result.credential_details`. It also reads `result.revocation_details.revoked_by` (`verification_badge.html:162`) instead of `revoked_by_actor_id` (`verification.py:157`).
2. **Mismatched `payload_snapshot` Structure Between Generator and `IssuanceService`:**
   - `DataGenerator._generate_credentials` (`backend/generator/generator.py:278-299`) builds a nested dictionary (`course.code`, `course.title`, `learner.id`, `learner.name`, `assessment.score`), while `IssuanceService.issue_credential` (`backend/services/issuance.py:101-113`) builds a flat dictionary (`course_id`, `course_title`, `learner_id`, `learner_name`, `assessment_score`).
3. **Incomplete SQL Export (`backend/generator/exporter.py:160-188`):**
   - `seed_data.sql` only exports `issuers` and `courses`, omitting the other 7 tables.
4. **`VerificationService` Never Checks Premature Issuance / Eligibility (`backend/services/verification.py:35-178`):**
   - `VerificationService` does not check whether a credential was issued before `completion_timestamp` or with a failing `assessment_score` (`INVALID_ISSUANCE` is only triggered on Ed25519 signature mismatch).
5. **Audit Export Truncated at 5,000 Rows (`backend/api/views/web.py:501`):**
   - `/web/export/audit` hardcodes `.limit(5000)`, which silently truncates exports at full scale (11,300+ audit events).
6. **Leftover Empty Directories Under `backend/`:**
   - `backend/static/css`, `backend/static/js`, `backend/templates/pages`, and `backend/templates/partials` are empty directories left over from the `src/` to `backend/` + `frontend/` split.

---

## 3. Problem Statement Requirements Gap List

| Requirement | Status | Gap Summary |
| :--- | :--- | :--- |
| **9 Entities & Relationships** | **DONE** | All 9 tables modeled with PKs, FKs, unique constraints, and check constraints. |
| **ID Formats** (`CRD-`, `LRN-`, `CMP-`, `VER-`, `REV-`) | **PARTIAL** | `LRN-000001` is compliant. Credential uses `CRED-` instead of `CRD-`. Verification uses `VRF-` instead of `VER-2026-`. `CompletionRecord` (`CMP-...`) and `Revocation` (`REV-...`) lack `public_id` columns. |
| **Baseline Volume (20k / 1k / 10k / 5k, seed `20261022`)** | **PARTIAL** | Generator supports `scale=1.0`, but `./exports` and the live DB were populated at `scale=0.05` and mutated by `pytest` runs. |
| **4 Labelled Edge Cases & Ground Truth** | **PARTIAL** | Fixtures and `ground_truth.json` exist, but `VerificationService` does not check premature issuance (Anomaly 1), and `/anomalies` uses hardcoded traces/outcomes. |
| **Eligibility & Atomic Issuance** | **DONE** | Enforced in `EligibilityService` and `IssuanceService` (missing UI button in `/registry` to trigger issuance from `eligible_candidates`). |
| **Multi-Factor Verification** | **PARTIAL** | Checks existence, SHA-256 hash, Ed25519 signature, and revocation; misses premature issuance check, does not log to `audit_events`, and UI badge displays `N/A` for holder/course/score. |
| **Revocation & Append-Only Audit History** | **PARTIAL** | Preserves history on revocation, but verification requests are missing from `audit_events`, and test runs polluted live DB counts. |
| **RBAC (UI + API)** | **PARTIAL** | Only `POST /web/revocation/revoke` enforces RBAC; all `/api/v1/*` routes and `/registry`, `/audit`, `/web/export/audit` lack backend role checks. Default persona is Registrar instead of Verifier. |
| **Validation, Reproducibility & Metrics** | **PARTIAL** | Seed determinism passes, but `validator.py` lacks a CLI entrypoint and no evaluation script computes FAR/FRR/accuracy metrics with denominators. |
| **CSV/JSON/SQL Exports & Documentation** | **PARTIAL** | CSVs, JSONs, and `manifest.sha256` work; `seed_data.sql` only exports 2 of 9 tables; no standalone `docs/DATA_DICTIONARY.md`. |
| **Identity Matching Not Relying on Name Alone** | **DONE** | All lookups and relationships use `public_id`, integer PKs, and unique `email`. |

---

## 4. Open Questions Before Implementation

1. **Public ID Formats & Schema Migration:** Should we add `public_id` columns (via a new Alembic migration) to `completion_records` (`CMP-LRN-000001-CRS-000001`) and `revocations` (`REV-CRD-2026-000001-01`), and standardize Credential (`CRD-2026-000001`), Course (`CRS-000001`), and Verification (`VER-2026-000001`) IDs across both the generator and runtime services?
2. **Verification Events in `audit_events`:** Should every `VerificationService.verify_credential` call (and synthetic verification in `DataGenerator`) also write a `VERIFICATION_PERFORMED` row to `audit_events` (so the Audit Ledger tracks all verifications alongside `verification_requests`), or should the Audit Ledger query/count verification audits directly from `verification_requests`?
3. **Role Enforcement Matrix & Default Persona:** When no `vericred_role` cookie is present, should the default role be `verifier` (`Public Verifier`) instead of `registrar`, and which exact routes (`POST /api/v1/issuance/*`, `POST /api/v1/revocation/*`, `GET /api/v1/audit/*`, `/registry`, `/audit`, `/web/export/audit`) should strictly reject unauthorized roles with HTTP 403 vs. rendering a read-only view?
4. **Public `/verify` Page Controls:** On `/verify`, should we completely remove the "Quick Samples" pills and the "Simulate Third-Party Payload Tampering" JSON textarea so `/verify` is a clean public verification page, or move tamper simulation exclusively into `/anomalies`?
5. **Test Database Isolation:** Should `pytest` (`tests/conftest.py`) use a separate test database (e.g., `credential_test_db`) or nested SAVEPOINT transactions (`session.begin_nested()`) so running `pytest` never mutates the seeded `credential_db` dataset?

