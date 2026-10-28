# VeriCred Backend Integration Report
**Target Framework:** FastAPI + Jinja2 + HTMX (Server-Rendered / Partial Swaps)  
**Verification Date:** 2026-10-28  
**Repository State:** Verified against active backend code, models, schemas, and PostgreSQL 17.

---

## 1. Backend API Inventory

The backend currently exposes **5 operational REST endpoints** across 4 functional routers, plus a system health probe.

### 1.1 Complete Endpoint Catalog

| HTTP Method | Path | Purpose | Router / Module | Status | Auth / Protection |
|---|---|---|---|---|---|
| `GET` | `/health` | System health, environment, and version probe | `src/main.py` | **Implemented** | Public (Unauthenticated) |
| `POST` | `/api/v1/issuance/evaluate` | Evaluates learner completion record against academic rules without issuing | `src/api/v1/issuance.py` | **Implemented** | Public / System Actor |
| `POST` | `/api/v1/issuance/issue` | Atomically verifies eligibility, computes SHA-256 hash, signs via Ed25519, and persists credential | `src/api/v1/issuance.py` | **Implemented** | Required Header: `X-Issuer-Private-Key` |
| `POST` | `/api/v1/verification/verify` | Multi-factor verification (Existence, SHA-256 hash, Ed25519 signature, Revocation register) | `src/api/v1/verification.py` | **Implemented** | Public (Unauthenticated) |
| `POST` | `/api/v1/revocation/revoke` | Authorized administrative revocation with standardized reason codes and audit preservation | `src/api/v1/revocation.py` | **Implemented** | Body: `actor_id` (No RBAC token yet) |
| `GET` | `/api/v1/revocation/audit/{credential_public_id}` | Retrieves historical audit trail for a single credential | `src/api/v1/revocation.py` | **Implemented** | Public / Administrative |
| `GET` | `/api/v1/audit/events` | Multi-criteria query engine for system-wide append-only audit ledger with pagination | `src/api/v1/audit.py` | **Implemented** | Public / Administrative |

---

### 1.2 Endpoint Specifications

#### 1. System Health Check
- **Path / Method:** `GET /health`
- **Request Parameters:** None
- **Response Schema:** `{"status": "healthy", "environment": str, "version": "1.0.0"}`
- **Errors:** `500 Internal Server Error`

#### 2. Academic Eligibility Evaluation
- **Path / Method:** `POST /api/v1/issuance/evaluate`
- **Request Body (`EligibilityEvaluationRequest`):**
  ```json
  {
    "completion_id": 101
  }
  ```
- **Response Body (`EligibilityEvaluationResult` - 200 OK):**
  ```json
  {
    "is_eligible": true,
    "completion_id": 101,
    "learner_public_id": "LRN-000101",
    "learner_name": "Alice Smith",
    "course_public_id": "CRS-000005",
    "course_title": "Applied Cryptography 301",
    "assessment_score": 92.50,
    "required_min_score": 80.00,
    "completion_status": "COMPLETED",
    "already_issued": false,
    "reasons": []
  }
  ```
- **Error Responses:**
  - `404 Not Found` (`COMPLETION_NOT_FOUND`): Completion record or rule does not exist.
  - `422 Unprocessable Entity`: Validation failure.

#### 3. Atomic Credential Issuance
- **Path / Method:** `POST /api/v1/issuance/issue`
- **Headers:** `X-Issuer-Private-Key: <PEM-encoded Ed25519 Private Key>` (Required)
- **Request Body (`CredentialIssuanceRequest`):**
  ```json
  {
    "completion_id": 101,
    "issuer_public_id": "ISS-00001",
    "actor_id": "REGISTRAR-OFFICE-01"
  }
  ```
- **Response Body (`CredentialResponse` - 201 Created):**
  ```json
  {
    "id": 1,
    "public_id": "CRED-2026-000001",
    "completion_id": 101,
    "issuer_id": 1,
    "issued_at": "2026-10-28T12:00:00Z",
    "canonical_payload_hash": "a1b2c3d4...",
    "issuer_signature": "MEUCIQD...",
    "payload_snapshot": { },
    "status": "ACTIVE",
    "created_at": "2026-10-28T12:00:00Z"
  }
  ```
- **Error Responses:**
  - `400 Bad Request` (`MISSING_ISSUER_KEY`): Missing `X-Issuer-Private-Key` header.
  - `404 Not Found` (`ISSUER_NOT_FOUND` / `COMPLETION_NOT_FOUND`).
  - `409 Conflict` (`DUPLICATE_ISSUANCE_REJECTED`): Completion already issued.
  - `422 Unprocessable Entity` (`ELIGIBILITY_REQUIREMENTS_NOT_MET`): Score < 80% or status != COMPLETED.

#### 4. Public Credential Verification
- **Path / Method:** `POST /api/v1/verification/verify`
- **Request Body (`VerificationQueryRequest`):**
  ```json
  {
    "credential_public_id": "CRED-2026-000001",
    "payload_to_verify": null
  }
  ```
- **Response Body (`VerificationResponse` - 200 OK):**
  ```json
  {
    "verification_id": "VRF-A1B2C3D4",
    "credential_public_id": "CRED-2026-000001",
    "outcome": "VALID",
    "reason_code": "VERIFICATION_SUCCESSFUL",
    "message": "Credential is valid, authentic, and active.",
    "timestamp": "2026-10-28T16:00:00Z",
    "factors": {
      "record_found": true,
      "payload_integrity_valid": true,
      "issuer_authenticated": true,
      "revocation_checked": true,
      "is_revoked": false
    },
    "credential_details": {
      "credential_id": "CRED-2026-000001",
      "learner": { "id": "LRN-000101", "name": "Alice Smith" },
      "course": { "code": "CRS-000005", "title": "Applied Cryptography 301" },
      "assessment": { "score": 92.50, "status": "COMPLETED" },
      "issuer": { "id": "ISS-00001", "name": "National Institute of Technology" }
    },
    "revocation_details": null
  }
  ```
- **Possible Outcomes:** `VALID`, `REVOKED`, `TAMPERED`, `NOT_FOUND`, `INVALID_ISSUANCE`.

#### 5. Authorized Credential Revocation
- **Path / Method:** `POST /api/v1/revocation/revoke`
- **Request Body (`RevocationRequest`):**
  ```json
  {
    "credential_public_id": "CRED-2026-000001",
    "actor_id": "DEAN-OFFICE-01",
    "reason_code": "ACADEMIC_MISCONDUCT",
    "notes": "Unauthorized material detected during exam audit."
  }
  ```
- **Response Body (`RevocationResponse` - 200 OK):**
  ```json
  {
    "revocation_id": 1,
    "credential_public_id": "CRED-2026-000001",
    "previous_status": "ACTIVE",
    "current_status": "REVOKED",
    "revoked_at": "2026-10-28T16:05:00Z",
    "revoked_by": "DEAN-OFFICE-01",
    "reason_code": "ACADEMIC_MISCONDUCT",
    "notes": "Unauthorized material detected during exam audit."
  }
  ```

#### 6. Multi-Criteria Audit Ledger Query
- **Path / Method:** `GET /api/v1/audit/events`
- **Query Parameters:**
  - `event_type`: Optional string (e.g. `CREDENTIAL_ISSUED`, `CREDENTIAL_REVOKED`, `RULE_MODIFIED`)
  - `actor_id`: Optional string (e.g. `DEAN-OFFICE-01`)
  - `target_entity_type`: Optional string (`Credential`, `CredentialRule`, `CompletionRecord`)
  - `target_entity_id`: Optional string (`CRED-2026-000001`)
  - `from_date`: Optional ISO 8601 datetime
  - `to_date`: Optional ISO 8601 datetime
  - `limit`: Integer (`1` to `1000`, default `100`)
  - `offset`: Integer (`>= 0`, default `0`)

---

## 2. API Documentation & Data Layer

- **FastAPI Swagger UI:** `http://localhost:8000/docs` (active in DEBUG mode).
- **ReDoc UI:** `http://localhost:8000/redoc`.
- **OpenAPI Schema:** `http://localhost:8000/openapi.json`.
- **Error Format:** Standardized JSON via `DomainException`: `{"error": str, "code": str, "details": dict}`.

---

## 3. Frontend Integration Requirements

- **Framework:** FastAPI + Jinja2 + HTMX (server-rendered templates and reactive partial swaps without a Node/React build pipeline).
- **Base URL:** Same-origin (`/` and `/api/v1/...`).
- **Templates Directory:** `src/templates/` (`pages/` and `partials/`).
- **Static Assets:** `src/static/` (`css/` and `js/`).

---

## 4. Screen-to-Endpoint Mapping (Google Stitch Designs)

### Screen 1: Public Verification Portal
- **Search & Verify Action:** `POST /api/v1/verification/verify` (Supported).
- **Tamper Simulation:** `POST /api/v1/verification/verify` with `payload_to_verify` (Supported).
- **Quick-Fill Pills:** Static sample IDs or helper (Supported).
- **4-Factor Checklist Badge:** `factors` dictionary in `VerificationResponse` (Supported).

### Screen 2: Credential Registry & Management Console
- **Overview Metrics:** Missing aggregate query in REST API; can be queried in web view router.
- **Credentials Table Listing:** Missing `GET /api/v1/credentials`; needs a query endpoint with pagination in the web route.
- **Revocation Action:** `POST /api/v1/revocation/revoke` (Supported).
- **Audit History Modal:** `GET /api/v1/revocation/audit/{id}` (Supported).

### Screen 3: Immutable Audit Ledger Explorer
- **Ledger Query & Filters:** `GET /api/v1/audit/events` (Supported).
- **JSON Payload Inspection:** `details` JSONB field in `AuditEventResponse` (Supported).
- **Export Ledger:** CLI exporter exists; needs a web download route (e.g. `/web/export/audit`).

### Screen 4: Cryptographic Anomaly Stress-Test Lab
- **Anomaly Fixtures:** Generated via `src/generator/anomalies.py`; needs web route runner to execute tests and return comparison partials.

---

## 5. Implementation Roadmap
1. Build `src/api/views/web.py` to bridge web views, credential queries, and HTMX partial endpoints.
2. Construct `src/templates/base.html` shell with modern dark-slate tokens and HTMX integration.
3. Wire the 4 views using the Stitch templates in `ui/`.
4. Validate live interactivity and verify complete test suite.
