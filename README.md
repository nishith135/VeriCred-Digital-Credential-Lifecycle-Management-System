# VeriCred — Digital Credential Lifecycle Management System

VeriCred is a production-grade digital credential platform built with **Python 3.13**, **FastAPI**, **PostgreSQL 17**, **SQLAlchemy 2.0**, and **HTMX**. It manages the complete lifecycle of academic credentials: eligibility evaluation, atomic cryptographic issuance (canonical SHA-256 digests and RFC 8032 Ed25519 signatures), tamper-evident multi-factor verification, authorized revocation with append-only audit preservation, role-based access control with PII redaction, and reproducible synthetic evaluation against segregated ground truth.

Developed for the **YottaFlex AI Candidate Evaluation Hackathon** within the official 72-hour window.

---

## 1. Architecture Layers

- **Presentation Layer (Jinja2 + HTMX):** Server-rendered templates served directly by FastAPI without Node.js or a JavaScript build step. Interactive UI flows (credential verification, registry browsing, audit ledger searching, and real-time anomaly evaluation) are powered by HTMX partial requests with server-side SQL pagination (`50` rows per page).
- **Application & Routing Layer (FastAPI):** Centralized HTTP endpoints exposing both HTML web routes and versioned JSON REST APIs (`/api/v1/`). It implements server-side role-based access control (RBAC), signed HMAC session cookies, Bearer API key authentication, sliding-window rate limiting on verification endpoints, and public verifier PII redaction.
- **Domain Services Layer (Python):** Encapsulates core business workflows: `EligibilityService` evaluates completion scores and date windows; `IssuanceService` executes atomic credential creation with Ed25519 signing; `VerificationService` runs 4-factor cryptographic verification with tamper-precedence; `RevocationService` handles idempotent revocations; and `AuditService` logs every lifecycle mutation to an append-only ledger.
- **Data & Cryptographic Layer (SQLAlchemy 2.0 & PostgreSQL):** Relational persistence over PostgreSQL 17 using B-Tree indexed unique public IDs, foreign keys with `ON DELETE RESTRICT` policies, check constraints on enum fields, and PostgreSQL sequences. Cryptographic operations utilize `cryptography.hazmat` for canonical RFC 8785 JSON hashing and Ed25519 digital signatures.

---

## 2. Quickstart & How to Run

### Prerequisites
- Python 3.13+ (or 3.11+)
- PostgreSQL 17 (or 15+) running locally on port 5432
- Database created: `credential_db` (live) and `credential_test_db` (automated tests)

### Step 1: Clone and Install Dependencies
```bash
git clone https://github.com/nishith135/digital_credential_lifecycle_management_system.git
cd digital_credential_lifecycle_management_system

python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Environment Configuration
Copy the template configuration:
```bash
cp .env.example .env
```
Ensure `.env` contains valid database credentials and secrets:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/credential_db
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/credential_db
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/credential_test_db
TEST_DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@localhost:5432/credential_test_db
SESSION_SECRET=dev-session-secret-change-in-production-min32chars
REGISTRAR_API_KEY=reg_live_7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c
AUDITOR_API_KEY=aud_live_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d
DEMO_MODE=true
```

### Step 3: Run Database Migrations
Apply Alembic migrations to create the schema and PostgreSQL sequences:
```bash
alembic upgrade head
```

### Step 4: Generate Synthetic Dataset and Load Database
Generate the full baseline dataset (`scale=1.0`, `seed=20261022`) into `./exports` and load it into PostgreSQL (`credential_db`):
```bash
python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports --load-db
```

### Step 5: Start the Web Application
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser to:
- **Public Verification:** [http://localhost:8000/verify](http://localhost:8000/verify)
- **Credential Registry:** [http://localhost:8000/registry](http://localhost:8000/registry) *(requires Registrar or Auditor)*
- **Audit Ledger:** [http://localhost:8000/audit](http://localhost:8000/audit) *(requires Registrar or Auditor)*
- **Anomaly Lab:** [http://localhost:8000/anomalies](http://localhost:8000/anomalies) *(requires Registrar or Auditor)*
- **Persona Switcher:** [http://localhost:8000/login](http://localhost:8000/login) *(demo convenience)*
- **System Health:** [http://localhost:8000/health](http://localhost:8000/health)

### Step 6: Run Automated Tests
All unit, integration, and security tests execute against `credential_test_db`, leaving `credential_db` completely untouched:
```bash
pytest -v
```

### Step 7: Run Evaluation Module
Evaluate all 10,000 credentials and 20 staging duplicates through the real verification engine:
```bash
python -m backend.evaluation.run --db live --out ./exports
```

### Step 8: Run Dataset Validator
Validate referential integrity, canonical ID regexes, and audit reconciliation:
```bash
# Validate exported CSV/JSON files
python -m backend.generator.validator --export-dir ./exports --with-ground-truth

# Validate live database tables directly
python -m backend.generator.validator --db live --with-ground-truth
```

---

## 3. Public Identifiers & Deterministic Seed

All public identifiers use immutable, zero-padded, human-readable formats generated from global sequential counters. The year segment for credentials and verification requests is fixed to the constant `2026`, while chronological issuance and verification timestamps remain distributed across actual years.

| Entity | ID Format | Example | Sequence / Generation Rule |
|---|---|---|---|
| **Issuer** | `ISS-NNNNN` | `ISS-00001` | Sequential 5-digit zero-padded index |
| **Course** | `CRS-NNNNNN` | `CRS-000001` | Sequential 6-digit zero-padded index |
| **Learner** | `LRN-NNNNNN` | `LRN-000001` | Sequential 6-digit zero-padded index |
| **Completion** | `CMP-<learner>-<course>` | `CMP-LRN-000001-CRS-000484` | Natural compound key enforcing at most 1 record per (learner, course) |
| **Credential** | `CRD-2026-NNNNNN` | `CRD-2026-000001` | Global sequential counter via `credential_public_seq` |
| **Revocation** | `REV-<credential>-01` | `REV-CRD-2026-000012-01` | Bound 1:1 to target credential identifier |
| **Verification** | `VER-2026-NNNNNN` | `VER-2026-000001` | Global sequential counter via `verification_public_seq` |
| **AuditEvent** | `EVT-NNNNNNNN` | `EVT-00000001` | Global sequential counter via `audit_event_public_seq` |

### Deterministic Seed: `20261022`
The synthetic data generator relies on a single constant seed (`20261022`) used across Python's `random.Random`, `numpy.random.default_rng`, and `Faker.seed`. Running the generator with this seed produces byte-identical exports and checksums in `exports/manifest.sha256`.

---

## 4. Entity Model & Relationship Cardinality

Comprehensive field specifications, data types, allowed values, validation rules, and lifecycle transitions are documented in [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md). An issuer with status RETIRED ceases issuing new credentials while historical credentials remain verifiable using its recorded public key. The effective date and successor issuer are recorded in the ISSUER_RETIRED audit event. The `audit_events` table is protected at the database level by a PostgreSQL `BEFORE UPDATE OR DELETE` row-level trigger that enforces an append-only ledger by raising an exception on any attempted update or deletion.

### Database Entity-Relationship Diagram

![VeriCred Database ER Diagram](docs/architecture/database_er_diagram.png)

```
+-----------+          +--------------------+          +-------------+
|  learners | 1      N | completion_records | N      1 |   courses   |
+-----------+----------+--------------------+----------+-------------+
                             | 1            1 |               | 1
                             | (UNIQUE)       |               |
                             v                v               v N
                       +-------------+  +-------------------------------+
                       | credentials |  |        credential_rules       |
                       +-------------+  +-------------------------------+
                         | 1       | 1                ^
                         |         |                  |
           1:0..1 (UNIQUE)         v 1:N              |
                         |     +-----------------------+
                         v     | verification_requests |
                   +-------------+---------------------+
                   | revocations |
                   +-------------+
                         |
                         +-----------------------------+
                                                       |
                                                       v
                                            +--------------------+
                                            |    audit_events    |
                                            | (Polymorphic Ledger|
                                            +--------------------+
```

### Entity Relationships Summary

| Parent Entity | Child Entity | Cardinality | Child FK Nullable? | Foreign Key Constraint & `ON DELETE` Policy |
| :--- | :--- | :---: | :---: | :--- |
| `courses` (`id`) | `credential_rules` (`course_id`) | `1 : N` (`1:1` baseline) | No (`NOT NULL`) | `FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT` |
| `learners` (`id`) | `completion_records` (`learner_id`) | `1 : N` | No (`NOT NULL`) | `FOREIGN KEY (learner_id) REFERENCES learners(id) ON DELETE RESTRICT` |
| `courses` (`id`) | `completion_records` (`course_id`) | `1 : N` | No (`NOT NULL`) | `FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT` |
| `credential_rules` (`id`) | `completion_records` (`rule_id`) | `1 : N` | No (`NOT NULL`) | `FOREIGN KEY (rule_id) REFERENCES credential_rules(id) ON DELETE RESTRICT` |
| `completion_records` (`id`) | `credentials` (`completion_id`) | `1 : 0..1` (`UNIQUE`) | No (`NOT NULL`) | `FOREIGN KEY (completion_id) REFERENCES completion_records(id) ON DELETE RESTRICT` |
| `issuers` (`id`) | `credentials` (`issuer_id`) | `1 : N` | No (`NOT NULL`) | `FOREIGN KEY (issuer_id) REFERENCES issuers(id) ON DELETE RESTRICT` |
| `credentials` (`id`) | `revocations` (`credential_id`) | `1 : 0..1` (`UNIQUE`) | No (`NOT NULL`) | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT` |
| `credentials` (`id`) | `verification_requests` (`credential_id`) | `1 : N` | Yes (`NULL` if `NOT_FOUND`) | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE SET NULL` |
| Any Entity (`id` / `public_id`) | `audit_events` (`target_entity_id`) | `1 : N` (Polymorphic) | No (`NOT NULL`) | Reconciled 1:1 via `DatasetValidator._validate_audit_reconciliation` |

---

## 5. The Four Edge Cases & Ground-Truth Segregation

The dataset injects 4 controlled anomaly scenarios (`20` cases each at `scale=1.0`, `80` total) to evaluate the system's verification and integrity safeguards:

1. **`PREMATURE_ISSUANCE` (20 cases):** Credentials whose `issued_at` timestamp is earlier than the learner's `completion_timestamp`, despite having valid SHA-256 hashes and valid Ed25519 signatures.
   - *Expected Outcome:* `INVALID_ISSUANCE` (`reason_code: PREMATURE_ISSUANCE_TIMESTAMP`).
2. **`DUPLICATE_CREDENTIAL_ID` (20 cases):** Written exclusively to `exports/credential_import_staging.csv` with `public_id`s that duplicate existing credentials. These rows are **never** loaded into the database, preserving PostgreSQL unique constraints.
   - *Expected Outcome:* Rejected during import validation or staging evaluation (`reason_code: DUPLICATE_CREDENTIAL_PUBLIC_ID`).
3. **`REVOKED_VERIFIES_AS_ACTIVE` (20 cases):** A valid `Revocation` record exists in the `revocations` table, but the parent row in `credentials.status` was deliberately kept as `ACTIVE`.
   - *Expected Outcome:* `REVOKED` (`reason_code: REVOCATION_RECORD_FOUND`). `VerificationService` performs a live relational join against `revocations`, ensuring un-updated status flags cannot mask a revocation.
4. **`ALTERED_PAYLOAD_NOT_DETECTED` (20 cases):** 10 credentials with tampered `payload_snapshot` JSON (digest mismatch), and 10 credentials with tampered `payload_snapshot` and a matched tampered `canonical_payload_hash` (signature mismatch + relational claim mismatch).
   - *Expected Outcome:* `TAMPERED` (`reason_code: PAYLOAD_DIGEST_MISMATCH` or `RELATIONAL_PAYLOAD_MISMATCH`).

### Ground-Truth Segregation
Ground-truth anomaly labels are isolated entirely in `exports/ground_truth.csv` and `exports/ground_truth.json`.
- **No Database Contamination:** Operational database tables contain zero `is_anomaly`, `label`, or `expected_outcome` columns.
- **AST Static Leakage Guard:** Automated test `tests/test_anomalies.py::test_static_ground_truth_leakage_guard` parses the Python AST of all files in `backend/services/`, `backend/api/`, and `backend/core/` to guarantee no runtime service imports or reads ground truth.
- **Independent Evaluation:** `backend/evaluation/` evaluates credentials blindly through the standard `VerificationService.verify_credential` method (running with `persist=False` so no evaluation events pollute the database) and only afterward compares outcomes against the segregated ground-truth file to compute metrics.

---

## 6. Roles & Server-Side Permission Matrix

VeriCred defines three distinct personas:
- **`verifier` (Public Verifier):** Default unauthenticated role. Can query `/verify`, submit credentials for verification, and inspect redacted results. Prohibited from viewing the credential registry, audit ledgers, or anomaly labs.
- **`registrar` (Academic Registrar):** Authorized staff role. Can issue credentials, trigger revocations, view the full registry and audit events, and run the Anomaly Lab.
- **`auditor` (Compliance Officer):** Read-only audit role. Can inspect the registry, export audit logs, and run evaluation benchmarks, but cannot issue or revoke credentials.

### Authentication & Security Boundary
> [!IMPORTANT]
> **Demo Convenience vs. Real Security Boundary:**
> The top-right persona dropdown and `/login` persona switcher (`/role/switch`) are provided **strictly for demonstration convenience** during evaluation walkthroughs. In production (`DEMO_MODE=false`), `/role/switch` is disabled for privileged roles.
> 
> The **real security boundaries** are:
> 1. **Server-Side RBAC Enforcement:** Every route is guarded on the server by FastAPI dependencies (`require_role("registrar")`, etc.). No route trusts client-provided assertions.
> 2. **Cryptographically Signed Cookies:** In browser sessions, the `vericred_role` cookie is signed with HMAC-SHA256 (`itsdangerous.TimestampSigner`) using `SESSION_SECRET`. Unsigned, invalid, or tampered cookies automatically fall back to `verifier`.
> 3. **API Bearer Keys:** External API clients authenticate via `Authorization: Bearer <key>` using timing-safe comparisons (`hmac.compare_digest`) against `REGISTRAR_API_KEY` and `AUDITOR_API_KEY` configured in `.env`.
> 4. **Public PII Redaction:** The public verification response schema (`PublicVerificationResponse`) never exposes learner full names, email addresses, learner IDs (`LRN-*`), assessment scores, or internal database keys.

### Server-Side Route Access Matrix

| Route | Method | Public Verifier | Registrar | Auditor |
| :--- | :---: | :---: | :---: | :---: |
| `/` & `/verify` | `GET` | 200 OK | 200 OK | 200 OK |
| `/web/verify` & `/api/v1/verification/verify` | `POST` | 200 OK *(Redacted PII)* | 200 OK *(Full)* | 200 OK *(Full)* |
| `/registry` & `/web/registry/table` | `GET` | **403 Forbidden** | 200 OK | 200 OK *(No Revoke button)* |
| `/audit` & `/web/audit/table` | `GET` | **403 Forbidden** | 200 OK | 200 OK |
| `/web/export/audit` | `GET` | **403 Forbidden** | 200 OK | 200 OK |
| `/anomalies` & `/web/anomalies/run*` | `GET`/`POST` | **403 Forbidden** | 200 OK | 200 OK |
| `/web/revocation/revoke` | `POST` | **403 Forbidden** | 200 OK | **403 Forbidden** |
| `/api/v1/issuance/*` | `POST` | **403 Forbidden** | 200 OK | **403 Forbidden** |
| `/api/v1/revocation/revoke` | `POST` | **403 Forbidden** | 200 OK | **403 Forbidden** |
| `/role/switch` | `POST` | 303 Redirect | 303 Redirect | 303 Redirect |

---

## 7. Known Limitations

- **Single Active Key per Issuer:** Key rotation with historical key archives is modeled via issuer retirement (`RETIRED` status with `successor_issuer_id`), rather than multiple active keys per individual issuer record.
- **In-Memory Rate Limiting:** The sliding-window verification rate limiter stores request timestamps in application process memory (`SlidingWindowRateLimiter`). In a multi-worker production cluster, this would be backed by Redis.
- **Single-Node Database Transactions:** Concurrency controls rely on PostgreSQL transaction isolation (`SERIALIZABLE` / row locking via `with_for_update`). Distributed multi-region consensus is outside the scope of this implementation.
- **Browser Persona Switcher:** The demo persona switcher sets a signed role cookie. In a live enterprise deployment, authentication would integrate with an external SAML 2.0 / OIDC Identity Provider (e.g., Okta, Keycloak).

---

## 8. Verification & Test Evidence

Comprehensive test logs, ADRs, and verification transcripts are tracked in:
- [docs/VALIDATION_SUMMARY.md](docs/VALIDATION_SUMMARY.md): Final full-scale database and export validation metrics.
- [docs/TEST_EVIDENCE.md](docs/TEST_EVIDENCE.md): Detailed verification runs across all milestones.
- [docs/DECISIONS.md](docs/DECISIONS.md): Architectural Decision Records (ADR-001 through ADR-013).
- [docs/AI_PROMPT_LOG.md](docs/AI_PROMPT_LOG.md): Full AI prompt history and disclosure log.
- [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md): Complete data dictionary for all 9 entities.
