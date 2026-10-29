# Architecture & Project Decisions Record (ADR)

This document records the foundational technical and organizational decisions made during the design and development of the **Digital Credential Lifecycle Management System** (YottaFlex AI candidate project).

---

## ADR-001: Adoption of GitHub Spec Kit and Spec-Driven Development (SDD)
- **Date:** 2026-10-27
- **Status:** Approved
- **Context:**
  The project is being constructed in a tight 72-hour solo hackathon window. Unplanned or ad-hoc AI code generation ("vibe coding") frequently leads to broken foreign keys, hallucinated APIs, incomplete edge cases, and scope creep that endangers deadlines.
- **Decision:**
  Adopt GitHub Spec Kit as the core engineering methodology following the formal lifecycle:
  `Constitution → Specify → Clarify → Plan → Tasks → Analyze → Implement → Converge`.
- **Alternatives Considered:**
  1. *Direct Prompt-and-Code:* Prompting the LLM to write full files immediately. Rejected because it lacks architectural coherence and verifiable acceptance criteria.
  2. *Standard Agile User Stories:* Writing manual Jira/Markdown stories. Rejected because it lacks native agent tooling and consistency analyzers.
- **Trade-offs & Mitigations:**
  - *Trade-off:* Initial upfront time spent writing specs and constitutions before seeing running code.
  - *Mitigation:* The 10 Spec Kit skills automate boilerplate generation and ensure that when coding begins, tasks are atomic, testable, and aligned with `MASTER_SPEC.md`.

---

## ADR-002: Mandatory AI Prompt Logging & Traceability Framework
- **Date:** 2026-10-27
- **Status:** Approved
- **Context:**
  The project submission guidelines require complete disclosure of AI assistance, exact prompts submitted, areas of heavy reliance, user review and validation, and rationale behind decisions.
- **Decision:**
  Establish `docs/AI_PROMPT_LOG.md` as a living audit log, supported by `docs/DECISIONS.md`, `docs/TEST_EVIDENCE.md`, and an automated agent rule in `AGENTS.md`. All coding agents must log prompts, file diffs, and test results before reporting task completion.
- **Alternatives Considered:**
  1. *Retrospective Log Generation at Final Submission:* Reconstructing prompt history at the end. Rejected because exact prompt wording and intermediate decisions are inevitably forgotten or distorted.
  2. *External Tool Export Only:* Relying solely on IDE export features. Rejected because external exports lack context linking specific prompt inputs to exact file diffs and passing test runs.
- **Trade-offs & Mitigations:**
  - *Trade-off:* Lightweight overhead on each prompt cycle.
  - *Mitigation:* Structured, concise entries that can be updated incrementally without disrupting implementation momentum.

---

## ADR-003: Core Technology Stack Selection
- **Date:** 2026-10-27
- **Status:** Approved
- **Context:**
  The system requires reliable relational integrity, transactional ACID guarantees for issuance and revocation, deterministic synthetic data generation at scale (20,000 learners, 1,000 courses, 10,000 credentials), cryptographic integrity verification, and a responsive demonstration UI.
- **Decision:**
  Standardize on:
  - **Backend:** Python + FastAPI (high performance, native Pydantic schema validation, OpenAPI documentation).
  - **Database & ORM:** PostgreSQL + SQLAlchemy + Alembic (strict relational constraints, foreign keys, migrations).
  - **Frontend:** React (modern component architecture, clear separation of presentation from API contracts).
  - **Testing:** Pytest (fast, parameterizable test suites for both valid lifecycle paths and anomaly scenarios).
- **Alternatives Considered:**
  1. *Microservices / Event Bus (e.g., Kafka):* Rejected as excessive complexity for a 72-hour solo build.
  2. *NoSQL / MongoDB:* Rejected because credential lifecycle rules require strict ACID guarantees and foreign-key referential integrity.
- **Trade-offs & Mitigations:**
  - *Trade-off:* Requires managing local Postgres service and Alembic migrations.
  - *Mitigation:* Containerized or straightforward local setup with automated migration scripts.

---

## ADR-004: Ratification of Project Constitution v1.0.0
- **Date:** 2026-10-27
- **Status:** Approved
- **Context:**
  Spec-Driven Development requires establishing core engineering principles and non-negotiables before drafting specifications or code.
- **Decision:**
  Ratify Constitution v1.0.0 in `.specify/memory/constitution.md` comprising 6 core principles:
  1. Strict Eligibility & Atomic Issuance (NON-NEGOTIABLE).
  2. Database Integrity & Constraint Supremacy (production constraints must never be weakened).
  3. Multi-Factor Verification & Authenticity Distinction (cryptographic hash vs digital signature).
  4. Append-Only Traceability & Historical Preservation (revocation does not erase history).
  5. Ground-Truth Isolation & Deterministic Reproducibility (fixed seed, 20k/1k/10k/5k).
  6. Test-First Rigor & Minimal Architecture (no microservices/blockchain; simple, maintainable).
- **Alternatives Considered:**
  1. *Generic Constitution Template:* Keeping default placeholders. Rejected because it fails to enforce domain-specific invariants required by YottaFlex AI and `MASTER_SPEC.md`.
- **Trade-offs & Mitigations:**
  - *Trade-off:* All tasks must strictly adhere to these 6 principles.
  - *Mitigation:* Clear principles avoid costly architectural refactoring later in the 72-hour window.

---

## ADR-005: Frontend Architecture Revision — Jinja2 + HTMX & Google Stitch Design Reference
- **Date:** 2026-10-28
- **Status:** Approved
- **Context:**
  The original proposal suggested a separate React frontend. In a 70-hour solo hackathon, maintaining a dual-language runtime (Node.js/npm alongside Python/FastAPI), complex client-side state management, and CORS adds disproportionate overhead without improving core evaluation criteria.
- **Decision:**
  1. **Production Frontend Stack:** Adopt server-rendered Jinja2 templates styled with HTML/CSS and enhanced with HTMX, served directly by FastAPI. No separate React or Node.js build pipeline unless explicitly approved.
  2. **Visual Prototyping Tool:** Use **Google Stitch** for visual UI prototyping and aesthetic design reference.
  3. **Stitch Integration Policy:** Treat Stitch exports strictly as design references, not production application code. The design will be sliced into reusable Jinja2 templates with HTMX attributes. All business logic remains strictly in backend Python services.
  4. **Timing of Design Integration:** Backend-first approach. Stitch designs are brought in once core domain models and FastAPI endpoints are validated (at the transition between Milestone M3 and Milestone M6).
- **Alternatives Considered:**
  1. *React SPA with Vite:* Rejected due to build configuration, API serialization friction, and redundant client-side routing.
  2. *Directly using Stitch code as production frontend:* Rejected because Stitch generates prototype markup that lacks validation hooks, server-side security, and clean template composition.
- **Trade-offs & Mitigations:**
  - *Trade-off:* UI elements must be translated from Stitch prototypes into Jinja2 components.
  - *Mitigation:* Clean, single-port Python application where FastAPI endpoints serve both JSON and HTMX HTML fragments with zero build latency.

---

## ADR-006: Top-Level Repository Separation — `backend/` and `frontend/`
- **Date:** 2026-10-28
- **Status:** Approved
- **Context:**
  The project originally placed backend Python code in `src/`, with templates in `frontend/templates/` and original design text files in `ui/`. To maximize architectural clarity and establish an intuitive, modular structure for evaluation and review, the user requested an explicit top-level separation between backend and frontend.
- **Decision:**
  1. Rename `src/` to `backend/`.
  2. Move all design files (`ui/`) into `frontend/ui/`.
  3. Consolidate all frontend assets (templates, static files, and UI specifications) under `frontend/`.
  4. Update all Python imports from `from src.` to `from backend.`.
- **Alternatives Considered:**
  1. *Moving tests and alembic inside `backend/`:* Rejected to keep project configuration (`pytest.ini`, `alembic.ini`) standard at the repository root.
  2. *Keeping `src/` and only consolidating `ui/`:* Rejected by user preference in favor of symmetrical top-level `backend/` and `frontend/` directories.
- **Trade-offs & Mitigations:**
  - *Trade-off:* 43 Python import paths updated.
  - *Mitigation:* Validated with full 36/36 pytest suite and CLI data generator test.

---

## ADR-007: Test Suite Database Isolation (`credential_test_db`) & Live DB Safety Guard
- **Date:** 2026-10-29
- **Status:** Approved
- **Context:**
  `tests/conftest.py` previously connected to `settings.DATABASE_URL` (`credential_db`). Because domain services call `await db.commit()` directly, running `pytest` permanently inserted test records into the live database (causing row-count drift such as 514 credentials vs. 513 issuance audit events).
- **Decision:**
  1. Introduce `TEST_DATABASE_URL` and `TEST_DATABASE_URL_SYNC` in `backend/core/config.py`, `.env`, and `.env.example` pointing to `credential_test_db`.
  2. Configure `tests/conftest.py` to automatically create `credential_test_db` if missing, run `alembic upgrade head` once per test session, and truncate all 9 tables (`RESTART IDENTITY CASCADE`) before and after every test.
  3. Enforce a startup safety guard (`pytest.exit`) that aborts immediately if the resolved database name does not end with `_test` (normalized for `_db`) or equals `credential_db`.
- **Trade-offs & Mitigations:**
  - *Trade-off:* Per-test `TRUNCATE ... RESTART IDENTITY CASCADE` adds ~0.3s per test (~19.5s total suite runtime).
  - *Mitigation:* Guarantees 100% deterministic, independent tests and zero mutation of `credential_db`.

---

## ADR-008: Canonical Public ID Standardization, Postgres Sequences & Unified Payload Builder
- **Date:** 2026-10-29
- **Status:** Approved
- **Context:**
  Public identifiers across the generator and runtime services previously diverged from the problem statement formats, `completion_records` and `revocations` lacked `public_id` columns, runtime services used random hex suffixes instead of sequential zero-padded numbers, and `IssuanceService` built a flat `payload_snapshot` while `DataGenerator` built a nested one.
- **Decision:**
  1. Centralize all public ID formatters and regex validators in `backend/services/ids.py` (`CRD-YYYY-000001`, `LRN-000001`, `CRS-000001`, `CMP-<learner>-<course>`, `VER-YYYY-000001`, `REV-<credential>-01`, `ISS-00001`, `EVT-00000001`).
  2. Add Alembic migration `7c2e9a41b5d3` adding `public_id` (unique, indexed, backfilled from parent `public_id`s) to `completion_records` and `revocations`, plus Postgres sequences (`credential_public_seq`, `verification_public_seq`, `audit_event_public_seq`) synced via `setval()` in `DatabaseLoader`.
  3. Create `backend/services/payloads.py` (`build_credential_payload`) as the single canonical nested payload builder used by `DataGenerator`, `IssuanceService`, and `anomalies.py`.
- **Trade-offs & Mitigations:**
  - *Trade-off:* Postgres sequences are non-transactional, so rolled-back runtime transactions can leave numeric gaps.
  - *Mitigation:* Guarantees race-safe sequential ID allocation under concurrent API requests without table locking.

---

### ADR-008: Verification Relational Cross-Check, Eligibility Re-Evaluation & Atomic Audit Reconciliation
- **Date:** 2026-10-29
- **Status:** Accepted
- **Context:** Verification previously checked only `compute_payload_hash(payload) == credential.canonical_payload_hash`, Ed25519 signature, and revocation status, without checking whether `CompletionRecord` and `CredentialRule` actually satisfied academic eligibility (`issued_at >= completion_timestamp`, `assessment_score >= rule.min_score`, `status == COMPLETED`) or whether `credential.payload_snapshot` had drifted from the relational rows (`learner`, `course`, `completion`, `issuer`). In addition, `VerificationService` did not log `VERIFICATION_PERFORMED` `AuditEvent`s, and `IssuanceService` did not persist `ELIGIBILITY_CHECK_FAILED` events when rejecting ineligible candidates.
- **Decision:**
  1. Reuse `EligibilityService.evaluate_completion_rules` inside `VerificationService.verify_credential` and return `INVALID_ISSUANCE` (with failing sub-checks in `reason_code` and `factors.failed_subchecks`) while preserving outcome precedence `NOT_FOUND -> TAMPERED -> INVALID_ISSUANCE -> REVOKED -> VALID`.
  2. When `presented_payload is None`, rebuild the credential payload from the relational rows via `build_credential_payload` and compare `RELATIONAL_CLAIM_KEYS = ("credential_id", "course", "learner", "assessment", "issuer")` against `credential.payload_snapshot` (excluding `issued_at` and `completion_timestamp` from JSON string comparison because `issued_at` is issuance metadata and both timestamps are compared as `datetime` objects in `evaluate_completion_rules`). Any mismatch returns `TAMPERED` (`reason_code="RELATIONAL_PAYLOAD_MISMATCH"`).
  3. Write a `VERIFICATION_PERFORMED` `AuditEvent` in the same transaction as `VerificationRequest` for every verification outcome (including `NOT_FOUND`), emit matching `VERIFICATION_PERFORMED` events in `DataGenerator` (`16,300` total audit events at `scale=1.0`), and log `ELIGIBILITY_CHECK_FAILED` in an independent `db_module.async_session_factory()` transaction when `IssuanceService` rejects an ineligible candidate.
  4. Enforce full audit-event count and target resolution reconciliation in `DatasetValidator` for both exported datasets and live database tables (`DatasetValidator.from_database`).
