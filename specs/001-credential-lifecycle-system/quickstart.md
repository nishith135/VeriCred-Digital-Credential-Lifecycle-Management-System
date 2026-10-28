# Developer Quickstart & Verification Guide

**Feature**: `specs/001-credential-lifecycle-system`  
**Stack**: Python 3.11+, FastAPI, PostgreSQL 15+, SQLAlchemy, Alembic, Pytest, Jinja2, HTMX  

---

## 1. Prerequisites

- **Python**: Version 3.11 or higher
- **PostgreSQL**: Version 15 or higher running locally (or via Docker)
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
Create a `.env` file in the workspace root (ignored by Git):
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/credential_system
SYNC_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/credential_system
APP_ENV=development
SECRET_KEY=dev_secret_key_for_local_testing_only
```

---

## 3. Database Initialization & Migrations

```powershell
# Run database migrations to latest schema
alembic upgrade head
```

---

## 4. Synthetic Data Generation

Generate the baseline dataset (20k learners, 1k courses, 10k credentials, 5k verifications) with the reproducible seed `42`:
```powershell
# Run generator and export CSV / JSON / SQL
python -m src.generator.cli --seed 42 --output-dir ./exports

# Verify dataset integrity and checksum repeatability
python -m src.generator.validator --export-dir ./exports
```

---

## 5. Running Automated Tests

```powershell
# Run full Pytest suite (unit, integration, anomaly fixtures)
pytest -v

# Run verification & anomaly scenario tests specifically
pytest tests/test_verification.py tests/test_anomalies.py -v
```

---

## 6. Running the Web Application

```powershell
# Start FastAPI application with live reload
uvicorn src.main:app --reload --port 8000
```
Open your browser to:
- **Public Verification Interface:** `http://localhost:8000/verify`
- **Administrative Dashboard:** `http://localhost:8000/credentials`
- **Interactive OpenAPI Docs:** `http://localhost:8000/docs`
