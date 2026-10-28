# Developer Quickstart & Verification Guide

**Project**: VeriCred — Digital Credential Lifecycle Management System  
**Feature**: `specs/001-credential-lifecycle-system`  
**Stack**: Python 3.11+, FastAPI, PostgreSQL 15+, SQLAlchemy, Alembic, Pytest, Jinja2, HTMX  

---

## 1. Prerequisites

- **Python**: Version 3.11, 3.12, or 3.13
- **PostgreSQL**: Version 15+ running locally (or via Docker)
- **Git**: Installed and configured

---

## 2. Environment Setup

### 2.1 Clone & Virtual Environment
```powershell
# Create Python virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install core dependencies
pip install -r requirements.txt
```

### 2.2 Environment Configuration
Create a `.env` file in the workspace root (or copy `.env.example`):
```ini
DATABASE_URL=postgresql+asyncpg://postgres:banana%40123@localhost:5432/credential_db
SYNC_DATABASE_URL=postgresql://postgres:banana%40123@localhost:5432/credential_db
APP_ENV=development
SECRET_KEY=dev_secret_key_for_local_testing_only
DEBUG=True
```

---

## 3. Database Initialization & Migrations

```powershell
# Run database migrations to establish the latest schema
alembic upgrade head
```

---

## 4. Synthetic Data Generation & Benchmark

Generate the baseline dataset (20,000 learners, 1,000 courses, 10,000 credentials, 5,000 verifications) and 4 controlled anomaly fixtures using the canonical seed `20261022`:

```powershell
# Run generator and export CSV / JSON / SQL with SHA-256 manifest
python -m backend.generator.cli --seed 20261022 --scale 1.0 --output-dir ./exports --load-db

# Validate dataset referential integrity and date ordering
python -m backend.generator.validator --export-dir ./exports
```

---

## 5. Running Automated Tests

Run the complete 36-test suite covering unit models, cryptographic consensus, API routes, web templates, and anomaly evaluation:

```powershell
# Run full Pytest suite
pytest -v

# Run verification & anomaly scenario tests specifically
pytest tests/test_verification.py tests/test_anomalies.py -v
```

---

## 6. Running the Unified Web Application & API Server

VeriCred uses a clean, single-port unified architecture where FastAPI directly serves both REST API endpoints and Jinja2 + HTMX server-rendered pages:

```powershell
# Start unified server with live reload
uvicorn backend.main:app --reload --port 8000
```

Open your browser to:
- **Public Verification Portal:** [http://localhost:8000/verify](http://localhost:8000/verify)
- **Credential Registry & Pre-Issuance:** [http://localhost:8000/registry](http://localhost:8000/registry)
- **Immutable Audit Ledger:** [http://localhost:8000/audit](http://localhost:8000/audit)
- **Anomaly Stress-Test Lab:** [http://localhost:8000/anomalies](http://localhost:8000/anomalies)
- **Interactive OpenAPI Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
