# Data Dictionary — Digital Credential Lifecycle Management System

This document defines the canonical schema for all **9** persistent relational entities in the Digital Credential Lifecycle Management System, generated directly from the SQLAlchemy ORM models in [`backend/models/`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/) and identifier patterns in [`backend/services/ids.py`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/services/ids.py).

---

## 1. Entity Field Definitions (All 9 Tables in FK Order)

### 1.1 `issuers` ([`Issuer`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/issuer.py))
Authorized academic institutions permitted to issue and cryptographically sign credentials.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(32)` | Required | `^ISS-\d{5}$` (e.g., `ISS-00001`) | Identifier | `UNIQUE` (Indexed) | Must match canonical regex `ID_PATTERNS["issuer"]` |
| `name` | `VARCHAR(255)` | Required | Non-empty institution name | Text | Non-unique | Length `1..255` characters |
| `public_key_pem` | `TEXT` | Required | PEM-encoded Ed25519 public key | Cryptographic Key (PEM) | Non-unique | Valid RFC 8032 Ed25519 SubjectPublicKeyInfo PEM |
| `status` | `VARCHAR(32)` | Required | `'ACTIVE'`, `'SUSPENDED'`, `'RETIRED'` | Enum state | Non-unique | `CHECK (status IN ('ACTIVE', 'SUSPENDED', 'RETIRED'))` (`chk_issuer_status`) |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

> **CSV / DataFrame Extension Columns (`issuers.csv`):** `retired_at` (`TIMESTAMPTZ`, Optional, UTC cutoff timestamp when `status = 'RETIRED'`) and `successor_issuer_id` (`INTEGER`, Optional, FK reference to successor `issuers.id`).
>
> **Issuer Retirement:** An issuer with status RETIRED ceases issuing new credentials while historical credentials remain verifiable using its recorded public key. The effective date and successor issuer are recorded in the ISSUER_RETIRED audit event.

---

### 1.2 `courses` ([`Course`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/course.py))
Academic courses and curriculum modules offered by accredited institutions.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(32)` | Required | `^CRS-\d{6}$` (e.g., `CRS-000001`) | Identifier | `UNIQUE` (Indexed) | Must match canonical regex `ID_PATTERNS["course"]` |
| `title` | `VARCHAR(255)` | Required | Distinct `<Qualifier> <Subject>` title | Text | Unique across generated catalog | Length `1..255` characters; no duplicate course titles |
| `version` | `VARCHAR(32)` | Required | Semantic version string (e.g., `'1.0'`) | Version string | Non-unique | Non-empty string, default `'1.0'` |
| `status` | `VARCHAR(32)` | Required | `'ACTIVE'`, `'ARCHIVED'` | Enum state | Non-unique | `CHECK (status IN ('ACTIVE', 'ARCHIVED'))` (`chk_course_status`) |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

> **CSV / DataFrame Extension Columns (`courses.csv`):** `department` (`VARCHAR`, Required in export, academic department name) and `level` (`VARCHAR`, Required in export, academic level qualifier such as `Introductory`, `Foundational`, `Undergraduate`, `Intermediate`, `Applied`, `Laboratory`, `Upper-Division`, `Advanced`, `Graduate`, `Doctoral`).

---

### 1.3 `credential_rules` ([`CredentialRule`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/credential_rule.py))
Academic policy rules governing eligibility criteria for credential issuance per course.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `course_id` | `INTEGER` | Required | Existing `courses.id` | Foreign Key | Non-unique (Indexed) | `FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT` |
| `rule_version` | `VARCHAR(32)` | Required | Semantic version string (e.g., `'1.0'`) | Version string | Non-unique | Non-empty string, default `'1.0'` |
| `min_score` | `NUMERIC(5, 2)` | Required | `0.00` to `100.00` (default `80.00`) | Percentage points (`%`) | Non-unique | `CHECK (min_score >= 0.00 AND min_score <= 100.00)` (`chk_min_score`) |
| `required_completion_status` | `VARCHAR(32)` | Required | `'COMPLETED'` | Enum state | Non-unique | Default `'COMPLETED'`; compared against `completion_records.status` |
| `effective_from` | `TIMESTAMPTZ` | Required | Valid UTC timestamp `< effective_to` | ISO-8601 UTC (`timestamptz`) | Non-unique | `CHECK (effective_to > effective_from)` (`chk_rule_dates`) |
| `effective_to` | `TIMESTAMPTZ` | Required | Valid UTC timestamp `> effective_from` | ISO-8601 UTC (`timestamptz`) | Non-unique | `CHECK (effective_to > effective_from)` (`chk_rule_dates`) |
| `active` | `BOOLEAN` | Required | `TRUE`, `FALSE` | Boolean flag | Non-unique | Non-null boolean, default `TRUE` |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

### 1.4 `learners` ([`Learner`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/learner.py))
Enrolled students and credential holders. Identity matching relies on `public_id` and `email`, never on `full_name` alone.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(32)` | Required | `^LRN-\d{6}$` (e.g., `LRN-000001`) | Identifier | `UNIQUE` (Indexed) | Must match canonical regex `ID_PATTERNS["learner"]` |
| `full_name` | `VARCHAR(255)` | Required | Any valid personal name (`en_IN`) | Text | **Non-unique** (natural duplicates allowed) | Length `1..255` characters; never used alone for identity matching |
| `email` | `VARCHAR(255)` | Required | Valid email address | Email (`RFC 5322`) | `UNIQUE` (Indexed) | Unique per learner across the registry |
| `status` | `VARCHAR(32)` | Required | `'ACTIVE'`, `'SUSPENDED'`, `'GRADUATED'` | Enum state | Non-unique | `CHECK (status IN ('ACTIVE', 'SUSPENDED', 'GRADUATED'))` (`chk_learner_status`) |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

### 1.5 `completion_records` ([`CompletionRecord`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/completion.py))
Empirical academic completion and assessment records linking a learner, course, and eligibility rule.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(64)` | Required | `^CMP-LRN-\d{6}-CRS-\d{6}$` | Identifier | `UNIQUE` (Indexed) | Must match `ID_PATTERNS["completion"]`; enforces at most one record per `(learner, course)` |
| `learner_id` | `INTEGER` | Required | Existing `learners.id` | Foreign Key | Non-unique (Indexed) | `FOREIGN KEY (learner_id) REFERENCES learners(id) ON DELETE RESTRICT` |
| `course_id` | `INTEGER` | Required | Existing `courses.id` | Foreign Key | Non-unique (Indexed) | `FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT` |
| `rule_id` | `INTEGER` | Required | Existing `credential_rules.id` | Foreign Key | Non-unique (Indexed) | `FOREIGN KEY (rule_id) REFERENCES credential_rules(id) ON DELETE RESTRICT` |
| `assessment_score` | `NUMERIC(5, 2)` | Optional (Required for issuance) | `0.00` to `100.00` | Percentage points (`%`) | Non-unique | `CHECK (assessment_score IS NULL OR (assessment_score >= 0.00 AND assessment_score <= 100.00))` (`chk_assessment_score_range`) |
| `status` | `VARCHAR(32)` | Required | `'IN_PROGRESS'`, `'COMPLETED'`, `'FAILED'`, `'WITHDRAWN'` | Enum state | Non-unique | `CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED', 'WITHDRAWN'))` (`chk_completion_status`) |
| `completion_timestamp` | `TIMESTAMPTZ` | Optional (Required when `COMPLETED`) | Valid UTC timestamp within rule effective window | ISO-8601 UTC (`timestamptz`) | Non-unique | Must fall within `[rule.effective_from, rule.effective_to]` for valid eligibility |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

### 1.6 `credentials` ([`Credential`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/credential.py))
Cryptographically signed digital credentials issued strictly to eligible completion records.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(64)` | Required | `^CRD-\d{4}-\d{6}$` (e.g., `CRD-2026-000001`) | Identifier | `UNIQUE` (Indexed) | Must match `ID_PATTERNS["credential"]` |
| `completion_id` | `INTEGER` | Required | Existing `completion_records.id` | Foreign Key | `UNIQUE` (Indexed, 1:1) | `FOREIGN KEY (completion_id) REFERENCES completion_records(id) ON DELETE RESTRICT`; prevents duplicate issuance |
| `issuer_id` | `INTEGER` | Required | Existing `issuers.id` | Foreign Key | Non-unique (Indexed) | `FOREIGN KEY (issuer_id) REFERENCES issuers(id) ON DELETE RESTRICT` |
| `issued_at` | `TIMESTAMPTZ` | Required | UTC timestamp `>= completion_timestamp` | ISO-8601 UTC (`timestamptz`) | Non-unique | Verified >= `completion_timestamp` by `EligibilityService` and `VerificationService` |
| `canonical_payload_hash` | `VARCHAR(64)` | Required | 64-char lowercase hex SHA-256 digest | Hexadecimal (`256 bits`) | Non-unique | SHA-256 over RFC 8785 canonical JSON of `payload_snapshot` |
| `issuer_signature` | `TEXT` | Required | Base64-encoded 64-byte Ed25519 signature | Base64 (`512 bits`) | Non-unique | Ed25519 signature over `canonical_payload_hash` verified against `issuer.public_key_pem` |
| `payload_snapshot` | `JSON` | Required | Structured claim dictionary (`credential_id`, `learner`, `course`, `assessment`, `issuer`, `issued_at`, `completion_timestamp`) | JSON object | Non-unique | Cross-checked against relational tables during verification |
| `status` | `VARCHAR(32)` | Required | `'ACTIVE'`, `'REVOKED'`, `'EXPIRED'` | Enum state | Non-unique | `CHECK (status IN ('ACTIVE', 'REVOKED', 'EXPIRED'))` (`chk_credential_status`) |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

### 1.7 `revocations` ([`Revocation`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/revocation.py))
Append-only records of authorized credential revocations. Revoking a credential never deletes historical records.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(64)` | Required | `^REV-CRD-\d{4}-\d{6}-01$` | Identifier | `UNIQUE` (Indexed) | Must match `ID_PATTERNS["revocation"]` |
| `credential_id` | `INTEGER` | Required | Existing `credentials.id` | Foreign Key | `UNIQUE` (Indexed, 1:1) | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE RESTRICT`; a credential can be revoked at most once |
| `revoked_by_actor_id` | `VARCHAR(64)` | Required | Authorized actor identifier (e.g., `REGISTRAR-001`, `DEAN-OFFICE-01`) | Actor ID | Non-unique | Non-empty string identifying the revoking authority |
| `reason_code` | `VARCHAR(64)` | Required | `'ACADEMIC_MISCONDUCT'`, `'ADMINISTRATIVE_ERROR'`, `'RESCINDED'`, `'OTHER'` | Enum code | Non-unique | `CHECK (reason_code IN ('ACADEMIC_MISCONDUCT', 'ADMINISTRATIVE_ERROR', 'RESCINDED', 'OTHER'))` (`chk_revocation_reason`) |
| `revocation_timestamp` | `TIMESTAMPTZ` | Required | UTC timestamp `>= credential.issued_at` | ISO-8601 UTC (`timestamptz`) | Non-unique | Must be `>= credential.issued_at` |
| `notes` | `TEXT` | Optional | Free-text governance notes or `NULL` | Text | Non-unique | Optional supplementary justification |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

### 1.8 `verification_requests` ([`VerificationRequest`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/verification.py))
Immutable log of every credential verification request and its outcome.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `public_id` | `VARCHAR(64)` | Required | `^VER-\d{4}-\d{6}$` (e.g., `VER-2026-000001`) | Identifier | `UNIQUE` (Indexed) | Must match `ID_PATTERNS["verification"]` |
| `credential_id` | `INTEGER` | Optional (`NULL` when `NOT_FOUND`) | Existing `credentials.id` or `NULL` | Foreign Key | Non-unique (Indexed) | `FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE SET NULL` |
| `requested_identifier` | `VARCHAR(64)` | Required | Public ID queried by caller | Identifier string | Non-unique (Indexed) | Non-empty string submitted for verification |
| `verification_timestamp` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |
| `outcome` | `VARCHAR(32)` | Required | `'VALID'`, `'REVOKED'`, `'TAMPERED'`, `'INVALID_ISSUANCE'`, `'NOT_FOUND'` | Enum outcome | Non-unique | `CHECK (outcome IN ('VALID', 'REVOKED', 'TAMPERED', 'INVALID_ISSUANCE', 'NOT_FOUND'))` (`chk_verification_outcome`) |
| `reason_code` | `VARCHAR(64)` | Required | Diagnostic reason code (e.g., `'VERIFICATION_SUCCESSFUL'`, `'PAYLOAD_DIGEST_MISMATCH'`) | Code string | Non-unique | Non-empty reason code explaining `outcome` |
| `integrity_check_passed` | `BOOLEAN` | Required | `TRUE`, `FALSE` | Boolean flag | Non-unique | `TRUE` iff SHA-256 digest and relational cross-check pass |
| `issuer_authenticated` | `BOOLEAN` | Required | `TRUE`, `FALSE` | Boolean flag | Non-unique | `TRUE` iff Ed25519 signature verifies against `issuer.public_key_pem` |
| `requester_ip` | `VARCHAR(64)` | Optional | IPv4/IPv6 address or `NULL` | IP address | Non-unique | Optional client IP address |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

### 1.9 `audit_events` ([`AuditEvent`](file:///c:/Projects/digital_credential_lifecycle_management_system/backend/models/audit.py))
Append-only system audit ledger recording all lifecycle actions, rule changes, issuer retirements, eligibility rejections, and verifications. The `audit_events` table is protected at the database level by a PostgreSQL `BEFORE UPDATE OR DELETE` row-level trigger that enforces an append-only ledger by raising an exception on any attempted update or deletion.

| Field | Type | Required / Optional | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Required | Positive integers (`>= 1`) | Sequence PK | `PRIMARY KEY` | Auto-incrementing integer primary key |
| `event_id` | `VARCHAR(32)` | Required | `^EVT-\d{8}$` (e.g., `EVT-00000001`) | Identifier | `UNIQUE` (Indexed) | Must match `ID_PATTERNS["audit_event"]` |
| `event_type` | `VARCHAR(64)` | Required | `'RULE_MODIFIED'`, `'ISSUER_RETIRED'`, `'CREDENTIAL_ISSUED'`, `'CREDENTIAL_REVOKED'`, `'VERIFICATION_PERFORMED'`, `'ELIGIBILITY_CHECK_FAILED'` | Event type code | Non-unique (Indexed) | Non-empty event type; 1:1 count reconciliation enforced for `CREDENTIAL_ISSUED`, `CREDENTIAL_REVOKED`, and `VERIFICATION_PERFORMED` |
| `actor_id` | `VARCHAR(64)` | Optional | Actor identifier (e.g., `'REGISTRAR-001'`, `'PUBLIC-VERIFIER'`) or `NULL` | Actor ID | Non-unique | Identifies the authenticated role/system actor |
| `target_entity_type` | `VARCHAR(64)` | Required | `'Credential'`, `'CredentialRule'`, `'VerificationRequest'`, `'CompletionRecord'`, `'Issuer'`, `'Course'`, `'Learner'`, `'Revocation'` | Entity class name | Non-unique (Indexed) | Must resolve in `DatasetValidator._validate_audit_reconciliation` |
| `target_entity_id` | `VARCHAR(64)` | Required | Public ID (or PK string for `CredentialRule`) of target entity | Identifier | Non-unique (Indexed) | Must resolve to an existing entity in `target_entity_type` (`0` unresolved audit targets) |
| `occurred_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique (Indexed) | Chronological event timestamp |
| `details` | `JSON` | Required | Structured JSON event metadata | JSON object | Non-unique | Non-null JSON dictionary |
| `created_at` | `TIMESTAMPTZ` | Required | Valid UTC timestamp | ISO-8601 UTC (`timestamptz`) | Non-unique | Non-null timezone-aware UTC timestamp |

---

## 2. Entity Relationships Summary

| Parent Entity | Child Entity | Cardinality | Child FK Optional? | Foreign Key Constraint & `ON DELETE` Policy |
| :--- | :--- | :---: | :---: | :--- |
| `courses` (`id`) | `credential_rules` (`course_id`) | `1 : N` (`1 : 1` in baseline seed) | Required (`NOT NULL`) | `credential_rules.course_id -> courses.id` (`ON DELETE RESTRICT`) |
| `learners` (`id`) | `completion_records` (`learner_id`) | `1 : N` | Required (`NOT NULL`) | `completion_records.learner_id -> learners.id` (`ON DELETE RESTRICT`) |
| `courses` (`id`) | `completion_records` (`course_id`) | `1 : N` | Required (`NOT NULL`) | `completion_records.course_id -> courses.id` (`ON DELETE RESTRICT`) |
| `credential_rules` (`id`) | `completion_records` (`rule_id`) | `1 : N` | Required (`NOT NULL`) | `completion_records.rule_id -> credential_rules.id` (`ON DELETE RESTRICT`) |
| `completion_records` (`id`) | `credentials` (`completion_id`) | `1 : 0..1` (`UNIQUE`) | Required (`NOT NULL`) | `credentials.completion_id -> completion_records.id` (`ON DELETE RESTRICT`, `UNIQUE`) |
| `issuers` (`id`) | `credentials` (`issuer_id`) | `1 : N` | Required (`NOT NULL`) | `credentials.issuer_id -> issuers.id` (`ON DELETE RESTRICT`) |
| `credentials` (`id`) | `revocations` (`credential_id`) | `1 : 0..1` (`UNIQUE`) | Required (`NOT NULL`) | `revocations.credential_id -> credentials.id` (`ON DELETE RESTRICT`, `UNIQUE`) |
| `credentials` (`id`) | `verification_requests` (`credential_id`) | `1 : N` | Optional (`NULL` when `NOT_FOUND`) | `verification_requests.credential_id -> credentials.id` (`ON DELETE SET NULL`) |
| Any Entity (`public_id` / `id`) | `audit_events` (`target_entity_type`, `target_entity_id`) | `1 : N` (Polymorphic) | Required (`NOT NULL`) | Validated by `DatasetValidator._validate_audit_reconciliation` (`unresolved_audit_targets == 0`) |

---

## 3. Entity Lifecycle States

### 3.1 Issuer Lifecycle (`issuers.status`)
- **`ACTIVE`**: Authorized to issue and sign new credentials; public key active for verification.
- **`SUSPENDED`**: Temporarily barred from issuing new credentials.
- **`RETIRED`**: Permanently retired as of `retired_at` (`ISSUER_RETIRED` audit event logged); courses transition to `successor_issuer_id` for subsequent issuances while historical credentials issued before retirement remain verifiable via the retired issuer's public key.

### 3.2 Course Lifecycle (`courses.status`)
- **`ACTIVE`**: Available for learner enrollment and completion recording.
- **`ARCHIVED`**: Historical curriculum retained for credential verification and audit traceability.

### 3.3 Learner Lifecycle (`learners.status`)
- **`ACTIVE`**: Currently enrolled learner.
- **`SUSPENDED`**: Enrollment suspended.
- **`GRADUATED`**: Completed program requirements; issued credentials remain permanently verifiable.

### 3.4 Completion Record Lifecycle (`completion_records.status`)
- **`IN_PROGRESS`**: Course enrollment active; ineligible for credential issuance.
- **`COMPLETED`**: Course completed; eligible for credential issuance iff `assessment_score >= rule.min_score` (`80.00%`) and `completion_timestamp` falls within `[rule.effective_from, rule.effective_to]`.
- **`FAILED`**: Assessment score below threshold (`< 80.00%`); ineligible for credential issuance.
- **`WITHDRAWN`**: Learner withdrew prior to completion; ineligible for credential issuance.

### 3.5 Credential Lifecycle (`credentials.status`) & Verification Outcomes (`verification_requests.outcome`)
- **Credential States:**
  - **`ACTIVE`**: Issued and unrevoked in `credentials` table.
  - **`REVOKED`**: Revoked via an append-only `Revocation` record (`CREDENTIAL_REVOKED` audit event logged; historical issuance payload and signature preserved).
  - **`EXPIRED`**: Past optional expiration window.
- **Verification Outcome Precedence (`VerificationService.verify_credential`):**
  1. **`NOT_FOUND`**: No credential row matches `requested_identifier`.
  2. **`TAMPERED`**: Canonical SHA-256 digest mismatch (`PAYLOAD_DIGEST_MISMATCH`) or relational cross-check mismatch (`RELATIONAL_PAYLOAD_MISMATCH`).Strictly overrides revocation and eligibility states.
  3. **`INVALID_ISSUANCE`**: Ed25519 signature verification failed (`ISSUER_SIGNATURE_INVALID`) or academic/chronological eligibility rule violated (`PREMATURE_ISSUANCE_TIMESTAMP`, `BELOW_MIN_SCORE`, `INELIGIBLE_COMPLETION_STATUS`, `OUTSIDE_RULE_EFFECTIVE_WINDOW`).
  4. **`REVOKED`**: `credential.status == 'REVOKED'` or a `Revocation` row exists (`REVOKED_VERIFIES_AS_ACTIVE` caught via live join).
  5. **`VALID`**: All 4 verification checks and eligibility sub-checks pass.

