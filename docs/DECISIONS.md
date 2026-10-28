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

