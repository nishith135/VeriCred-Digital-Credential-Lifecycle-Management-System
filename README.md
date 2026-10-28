# Digital Credential Lifecycle Management System

**Academic Digital Credential Lifecycle Management, Multi-Factor Verification, and Reproducible Synthetic Evaluation Platform.**

Developed as a solo hackathon project for the **YottaFlex AI Candidate Evaluation** within a 72-hour window.

---

## 1. Project Overview

This repository implements an end-to-end digital credential lifecycle management system for an academic institution. The system enforces strict business rules before issuance, records verifiable completion evidence, supports third-party verification, provides authorized credential revocation, and maintains tamper-resistant, append-only audit histories.

In addition to the operational web application, this repository includes a **reproducible synthetic-data pipeline** capable of generating verified datasets at scale (20,000 learners, 1,000 courses, 10,000 credentials, 5,000 verification requests) with four demonstrably labeled anomaly scenarios evaluated against independent ground truth.

---

## 2. Core Architecture & Stack

- **Backend:** Python 3.11+, FastAPI (REST API with Pydantic validation)
- **Database & Persistence:** PostgreSQL 15+, SQLAlchemy ORM, Alembic migrations
- **Frontend:** React SPA (workflow demonstration, issuance, verification, revocation, and audit logs)
- **Testing:** Pytest (unit, integration, and anomaly test suites)
- **Engineering Methodology:** [GitHub Spec Kit](https://github.com/github/spec-kit) & Spec-Driven Development (SDD)

---

## 3. Project Documentation & Governance

The repository maintains strict documentation and transparency standards:

- **[MASTER_SPEC.md](MASTER_SPEC.md):** The primary domain requirements and source of truth.
- **[AGENTS.md](AGENTS.md):** Workspace operating manual and agent governance rules.
- **[.specify/memory/constitution.md](.specify/memory/constitution.md):** Ratified project constitution (v1.0.0) defining core engineering laws.
- **[docs/AI_PROMPT_LOG.md](docs/AI_PROMPT_LOG.md):** Verbatim prompt log and AI disclosure history.
- **[docs/DECISIONS.md](docs/DECISIONS.md):** Architecture Decision Records (ADRs).
- **[docs/TEST_EVIDENCE.md](docs/TEST_EVIDENCE.md):** Empirical verification records and test results.
- **[docs/STATUS.md](docs/STATUS.md):** Milestone tracker and project timeline.

---

## 4. Current Milestone

- **M0: Environment & Governance Bootstrap** — Completed
- **M1: Constitution Ratification (v1.0.0)** — Completed
- **M2: Specification & Architectural Planning** — Next Up (`/speckit-specify`)

---

## 5. License

MIT
