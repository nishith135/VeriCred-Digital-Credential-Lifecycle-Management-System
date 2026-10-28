# API & Endpoint Specifications

**Feature**: `specs/001-credential-lifecycle-system`  
**Base URL**: `/api/v1`  
**Protocol**: REST / JSON & HTMX HTML Fragments  

---

## 1. REST JSON Endpoints

### 1.1 Issuance: Evaluate Eligibility
- **Route**: `POST /api/v1/issuance/evaluate`
- **Purpose**: Pre-check whether a completion record qualifies for credential granting.
- **Request Body**:
  ```json
  {
    "completion_id": 1042
  }
  ```
- **Response (200 OK — Eligible)**:
  ```json
  {
    "eligible": true,
    "learner_id": "LRN-00123",
    "course_id": "CRS-00045",
    "rule_version": "1.0",
    "assessment_score": 88.50,
    "min_required_score": 80.00,
    "reason": "Eligibility criteria passed."
  }
  ```
- **Response (200 OK — Ineligible)**:
  ```json
  {
    "eligible": false,
    "reason_code": "INELIGIBLE_SCORE",
    "assessment_score": 72.00,
    "min_required_score": 80.00,
    "reason": "Assessment score below required threshold."
  }
  ```

---

### 1.2 Issuance: Issue Credential (Atomic)
- **Route**: `POST /api/v1/issuance/issue`
- **Purpose**: Atomically issue a unique credential, generate SHA-256 payload hash and issuer signature, and commit the audit event.
- **Request Body**:
  ```json
  {
    "completion_id": 1042,
    "issuer_id": "ISS-00001"
  }
  ```
- **Response (201 Created)**:
  ```json
  {
    "credential_id": "CRED-2026-001042",
    "status": "ACTIVE",
    "issued_at": "2026-10-28T10:30:00Z",
    "canonical_payload_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "issuer_public_id": "ISS-00001",
    "audit_event_id": "EVT-009821"
  }
  ```
- **Error (409 Conflict — Duplicate)**:
  ```json
  {
    "detail": {
      "error_code": "DUPLICATE_ISSUANCE_NOT_PERMITTED",
      "message": "A credential has already been issued for this completion record."
    }
  }
  ```

---

### 1.3 Verification: Multi-Factor Verification Check
- **Route**: `POST /api/v1/verification/verify`
- **Purpose**: Public unauthenticated verification endpoint.
- **Request Body (Lookup by ID)**:
  ```json
  {
    "credential_id": "CRED-2026-001042"
  }
  ```
- **Response (200 OK — Valid)**:
  ```json
  {
    "verification_id": "VRF-004512",
    "outcome": "VALID",
    "credential_id": "CRED-2026-001042",
    "issuer_name": "Metropolitan University",
    "learner_reference": "LRN-00123",
    "course_title": "Advanced Distributed Systems",
    "issued_at": "2026-10-28T10:30:00Z",
    "integrity_check_passed": true,
    "issuer_authenticated": true,
    "revocation_status": "NONE"
  }
  ```
- **Response (200 OK — Revoked)**:
  ```json
  {
    "verification_id": "VRF-004513",
    "outcome": "REVOKED",
    "credential_id": "CRED-2026-001042",
    "integrity_check_passed": true,
    "issuer_authenticated": true,
    "revoked_at": "2026-10-28T11:00:00Z",
    "reason_code": "ACADEMIC_MISCONDUCT"
  }
  ```
- **Response (200 OK — Tampered)**:
  ```json
  {
    "verification_id": "VRF-004514",
    "outcome": "TAMPERED",
    "credential_id": "CRED-2026-001042",
    "integrity_check_passed": false,
    "reason_code": "PAYLOAD_HASH_MISMATCH"
  }
  ```
- **Response (404 Not Found)**:
  ```json
  {
    "verification_id": "VRF-004515",
    "outcome": "NOT_FOUND",
    "reason_code": "UNKNOWN_CREDENTIAL_ID"
  }
  ```

---

### 1.4 Revocation: Authorize Revocation
- **Route**: `POST /api/v1/revocation/revoke`
- **Purpose**: Authorized administrative revocation of an issued credential.
- **Request Body**:
  ```json
  {
    "credential_id": "CRED-2026-001042",
    "actor_id": "ADM-0004",
    "reason_code": "ACADEMIC_MISCONDUCT",
    "notes": "Verified plagiarism in capstone submission."
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "revocation_id": 42,
    "credential_id": "CRED-2026-001042",
    "status": "REVOKED",
    "revocation_timestamp": "2026-10-28T11:00:00Z",
    "audit_event_id": "EVT-009845"
  }
  ```

---

## 2. HTMX Web Endpoints

These endpoints return HTML fragments when the `HX-Request: true` header is present, allowing real-time UI updates without full page reloads.

- `GET /`: Serves complete dashboard HTML (`templates/pages/index.html`).
- `GET /verify`: Serves public verification page (`templates/pages/verify.html`).
- `POST /verify`: Receives form data (`credential_id`), queries verification service, and returns HTML fragment `templates/partials/verification_badge.html`.
- `GET /credentials`: Serves administrative credential table (`templates/pages/credentials.html`).
- `POST /credentials/{id}/revoke`: Processes revocation and returns updated table row HTML fragment (`templates/partials/credential_row.html`).
- `GET /audit`: Serves live audit event stream (`templates/pages/audit.html`).
