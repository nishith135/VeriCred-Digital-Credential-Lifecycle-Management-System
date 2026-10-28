<!--
Sync Impact Report:
- Version change: v1.0.0 -> v1.1.0
- Ratification Date: 2026-10-27 | Amended: 2026-10-28
- Modified principles: Preserved all 6 Core Principles.
- Amended Section: Architectural & Technology Constraints updated per ADR-005: replaced React SPA with server-rendered Jinja2 templates, HTML/CSS, and HTMX served by FastAPI, utilizing Google Stitch as visual design reference.
- Deferred items: None.
-->

# Digital Credential Lifecycle Management System Constitution

## Core Principles

### I. Strict Eligibility & Atomic Issuance (NON-NEGOTIABLE)
Credentials MUST only be issued after all eligibility requirements in the applicable `CredentialRule` have been evaluated and satisfied against verified completion records. Credential creation, integrity metadata calculation, and issuance audit logging MUST commit atomically within a single database transaction. Issuance attempts that fail eligibility checks MUST return explicit reason codes, fail cleanly without mutating state, and leave an auditable record of the rejected attempt. Duplicate credentials MUST NOT be issued for the same completion record under standard operational policy.

### II. Database Integrity & Constraint Supremacy
Relational integrity MUST be enforced at the storage engine layer using PostgreSQL primary keys, foreign keys, unique constraints, and domain checks. Production database constraints MUST NEVER be weakened, bypassed, or dropped to manufacture anomalies or accommodate malformed synthetic data. Synthetic anomalies MUST be isolated in test fixtures or dedicated evaluation datasets.

### III. Multi-Factor Verification & Authenticity Distinction
Credential verification MUST independently evaluate three distinct factors: (1) payload integrity, (2) issuer authenticity, and (3) live revocation status. Verification MUST distinguish between a deterministic cryptographic hash (which detects data tampering relative to an issued state) and a digital signature or authorized key verification (which establishes issuer authenticity). A cryptographic hash alone MUST NOT be presented as proof of issuer identity or authenticity. Verification MUST NOT rely on a recipient's display name alone.

### IV. Append-Only Traceability & Historical Preservation
Revocation, credential modifications, and administrative exceptions MUST NOT delete, overwrite, or mutate historical issuance, verification, or audit records. Revocation records MUST reference the credential, capture an authorized actor, timestamp, and structured reason code, and be immediately reflected in subsequent verification queries. Audit logs and prior verification request records are strictly append-only.

### V. Ground-Truth Isolation & Deterministic Reproducibility
Synthetic data generation across all required volumes (20,000 learners, 1,000 courses, 10,000 credentials, 5,000 verification requests) MUST be fully reproducible from a single configured seed. Ground-truth anomaly labels MUST be stored independently and MUST NOT be accessible or ingested as inputs by the operational verification service. All four mandatory anomaly scenarios MUST be reproducible and evaluated against explicit ground truth.

### VI. Test-First Rigor & Minimal Architecture
Every lifecycle transition, eligibility boundary, and anomaly scenario MUST be validated with automated tests before declaring a task complete. To safeguard the 72-hour delivery window, the system MUST prioritize simple, maintainable implementations over unnecessary abstractions. Distributed ledgers, blockchain implementations, microservices, and speculative abstractions are strictly out of scope.

## Architectural & Technology Constraints

The system MUST adhere to the ratified core stack unless explicitly amended:
- **Backend Service:** Python 3.11+ with FastAPI for high-throughput, schema-validated REST APIs.
- **Persistence & Migrations:** PostgreSQL 15+ managed via SQLAlchemy ORM and Alembic schema migrations.
- **Frontend Architecture:** Server-rendered Jinja2 templates, modern CSS, and HTMX interactions served directly by FastAPI. Visual design reference prototyped via Google Stitch. React and separate Node.js build pipelines are prohibited unless explicitly approved.
- **Testing Engine:** Pytest for backend unit, integration, and anomaly test suites.
- **Data Export Formats:** Export pipelines MUST produce valid CSV, JSON, and SQL datasets with checksum verification.

## Security & Operational Standards

- **Server-Side Enforcement:** Role-based access control MUST be enforced in backend route handlers and database queries, never exclusively in frontend interface elements.
- **Privacy by Design:** Public verification endpoints MUST disclose only the minimal subset of data required to confirm authenticity and status, suppressing unnecessary personally identifiable information (PII).
- **Zero Secrets in Code/Logs:** No private keys, database passwords, or credentials may be committed to version control, embedded in logs, or published in public evaluation files.
- **Deterministic ID Generation:** Public identifiers for learners, courses, credentials, and verification requests MUST follow documented formatting conventions and be strictly distinct from internal database sequence IDs.

## Governance

This Constitution represents the supreme technical governance for the Digital Credential Lifecycle Management System. It supersedes informal agreements, ad-hoc agent proposals, and temporary implementation convenience.

- **Amendment Procedure:** Amendments require explicit review and approval by the Project Owner. Proposed amendments must state the rationale, version increment, and impact on existing specifications.
- **Compliance Enforcement:** Every Spec Kit artifact (`spec.md`, `plan.md`, `tasks.md`), pull request, and code implementation MUST be audited against these principles before merging.
- **Runtime Guidance:** Coding agents MUST consult `AGENTS.md` and `MASTER_SPEC.md` alongside this Constitution for operational instructions.

**Version**: 1.1.0 | **Ratified**: 2026-10-27 | **Last Amended**: 2026-10-28
