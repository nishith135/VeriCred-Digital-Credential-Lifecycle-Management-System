# Implementation Plan: Digital Credential Lifecycle Management System

**Branch**: `main` | **Date**: 2026-10-28 | **Spec**: [specs/001-credential-lifecycle-system/spec.md](spec.md)  
**Input**: Feature specification from `specs/001-credential-lifecycle-system/spec.md`  

---

## Summary

Deliver a production-ready, testable digital credential lifecycle management system for academic credentials. The system guarantees atomic credential issuance based on evaluated course completion evidence, provides third-party verification evaluating payload integrity (SHA-256) and issuer authenticity (Ed25519 signatures), supports authorized credential revocation with instant live verification updates, maintains append-only audit histories, and generates reproducible synthetic datasets (20k learners, 1k courses, 10k credentials, 5k verifications) with four demonstrable anomaly scenarios evaluated against independent ground truth. The user interface is server-rendered via FastAPI using Jinja2 templates and HTMX, adapted from Google Stitch visual prototypes.

---

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: FastAPI (web/API), SQLAlchemy 2.0 (ORM), Pydantic v2 (validation), Jinja2 (templates), cryptography / PyCryptodome (Ed25519 signatures & SHA-256), HTMX 1.9.10 (frontend reactivity)  
**Storage**: PostgreSQL 15+ with Alembic for schema migrations  
**Testing**: Pytest (backend unit, integration, and anomaly evaluation suites)  
**Target Platform**: Linux / Windows server, local development via Antigravity IDE  
**Project Type**: Monolithic web service (FastAPI serving REST API, JSON endpoints, and Jinja2/HTMX HTML views) + Python CLI generator  
**Performance Goals**: Synthetic data generation of 20k learners, 1k courses, 10k credentials, 5k verifications in <60 seconds; HTMX verification queries in <200ms  
**Constraints**: Zero secrets in Git; production database constraints must never be weakened or dropped for anomaly testing; strictly no React or Node.js build tools  
**Scale/Scope**: 20,000 learners, 1,000 courses, 10,000 credentials, 5,000 verification requests, 4 mandatory anomalies, 6 core web screens  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle / Gate | Assessment | Status |
| :--- | :--- | :--- |
| **I. Strict Eligibility & Atomic Issuance** | Issuance requires verified `CompletionRecord` matching active `CredentialRule`. Credential creation, integrity hash, and audit log commit in a single database transaction. Duplicate issuance blocked by unique index on `completion_id`. | **PASS** |
| **II. Database Integrity & Constraint Supremacy** | Relational integrity enforced at PostgreSQL layer with PKs, FKs, Unique, and Check constraints. Synthetic anomalies isolated in dedicated evaluation fixtures without weakening production constraints. | **PASS** |
| **III. Multi-Factor Verification & Authenticity** | Verification independently checks payload SHA-256 hash, issuer Ed25519 signature, and live revocation status. Hash alone is never presented as proof of issuer authenticity. | **PASS** |
| **IV. Append-Only Traceability** | Revocation never mutates or deletes historical issuance rows or previous verification logs. `audit_events` and `verification_requests` are strictly append-only. | **PASS** |
| **V. Ground-Truth Isolation & Reproducibility** | Generator uses fixed-seed PRNG (`seed=42`). Ground-truth anomaly labels are segregated from verification service logic. All 4 mandatory anomalies are demonstrable and measurable. | **PASS** |
| **VI. Test-First Rigor & Minimal Architecture** | Monolithic FastAPI + Jinja2 + HTMX architecture avoids microservice or blockchain complexity. Pytest suites accompany all lifecycle transitions and anomaly paths. | **PASS** |

---

## Project Structure

### Documentation & Blueprints (this feature)

```text
specs/001-credential-lifecycle-system/
├── spec.md              # Functional specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 technical research & cryptographic design
├── data-model.md        # Phase 1 PostgreSQL relational schema & constraints
├── quickstart.md        # Phase 1 developer setup & verification guide
├── contracts/
│   └── api_contracts.md # Phase 1 REST JSON & HTMX endpoint contracts
└── checklists/
    └── requirements.md  # Quality validation checklist
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── config.py           # Environment settings & Pydantic BaseSettings
│   ├── security.py         # Cryptographic payload hashing & Ed25519 signatures
│   └── database.py         # SQLAlchemy engine, session maker, base model
├── models/
│   ├── learner.py          # Learner ORM model
│   ├── course.py           # Course ORM model
│   ├── credential_rule.py  # CredentialRule ORM model
│   ├── completion.py       # CompletionRecord ORM model
│   ├── credential.py       # Credential ORM model
│   ├── issuer.py           # Issuer ORM model
│   ├── revocation.py       # Revocation ORM model
│   ├── verification.py     # VerificationRequest ORM model
│   └── audit.py            # AuditEvent ORM model
├── schemas/
│   ├── learner.py          # Pydantic input/output schemas
│   ├── credential.py       # Issuance request/response schemas
│   ├── verification.py     # Verification request/result schemas
│   └── revocation.py       # Revocation schemas
├── services/
│   ├── eligibility.py      # Business rule evaluation engine
│   ├── issuance.py         # Atomic issuance & cryptographic sealing service
│   ├── verification.py     # Multi-factor verification engine
│   ├── revocation.py       # Authorized revocation & cache-invalidation service
│   └── audit.py            # Append-only audit logger service
├── generator/
│   ├── cli.py              # Synthetic data generator CLI entry point
│   ├── generator.py        # Deterministic generation pipeline (seed=42)
│   ├── anomalies.py        # 4 mandatory anomaly fixture generators
│   └── exporter.py         # CSV, JSON, SQL export pipeline & checksum verifier
├── api/
│   ├── router.py           # API route aggregator
│   ├── v1/
│   │   ├── issuance.py     # REST endpoints for eligibility & issuance
│   │   ├── verification.py # REST endpoints for verification
│   │   ├── revocation.py   # REST endpoints for revocation
│   │   └── audit.py        # REST endpoints for audit queries
│   └── views/
│       └── web.py          # FastAPI routes serving Jinja2/HTMX web views
├── templates/
│   ├── base.html           # Master layout shell with HTMX script
│   ├── pages/
│   │   ├── index.html      # Dashboard view
│   │   ├── verify.html     # Public verification search view
│   │   ├── credentials.html# Credential list & management view
│   │   └── audit.html      # Audit event history view
│   └── partials/
│       ├── verification_badge.html # HTMX dynamic verification badge
│       ├── credential_row.html     # HTMX credential table row
│       └── revocation_modal.html   # HTMX revocation dialog
├── static/
│   ├── css/
│   │   └── styles.css      # Custom styling adapted from Google Stitch prototypes
│   └── js/
│       └── app.js          # Minimal UI helper scripts (if needed)
└── main.py                 # FastAPI application factory & startup

alembic/
├── env.py                  # Migration environment configuration
├── script.py.mako          # Migration script template
└── versions/               # Ordered schema migration scripts

tests/
├── conftest.py             # Test fixtures, test database setup, seeded test data
├── test_eligibility.py     # Tests for rule evaluation & score boundaries
├── test_issuance.py        # Tests for atomic issuance & duplicate rejection
├── test_verification.py    # Tests for valid, revoked, tampered, not-found states
├── test_revocation.py      # Tests for revocation & historical preservation
├── test_audit.py           # Tests for append-only audit event generation
├── test_anomalies.py       # Tests for the 4 mandatory anomaly scenarios
└── test_generator.py       # Tests for fixed-seed reproducibility & data volumes
```

**Structure Decision**: Monolithic single-project layout where FastAPI serves both REST JSON APIs and Jinja2+HTMX templates directly. This maximizes developer velocity, eliminates CORS/build tooling, and guarantees transactional ACID integrity across the entire credential lifecycle.

---

## Complexity Tracking

> **No Constitution Violations detected. All core principles satisfied.**

| Proposed Architecture Element | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| Single FastAPI + Jinja2 + HTMX Monolith | Minimizes moving parts in 72h window | React/Node SPA adds build toolchains, CORS, and deployment complexity. |
| Ed25519 Signatures + SHA-256 Hashes | Constitutional requirement to separate integrity from authenticity | A single hash cannot prove issuer identity or non-repudiation. |
| SQLAlchemy Core Batch Insert for Generator | Necessary to insert 20,000 learners and 10,000 credentials in <60s | Standard ORM `session.add()` on individual objects is too slow at this scale. |
