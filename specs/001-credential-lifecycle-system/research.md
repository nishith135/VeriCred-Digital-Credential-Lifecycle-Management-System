# Technical Research & Architecture Decisions

**Feature**: `specs/001-credential-lifecycle-system`  
**Date**: 2026-10-28  
**Status**: Completed  

---

## 1. Cryptographic Authenticity vs Payload Integrity

### Problem Statement
Constitutional Principle III and `MASTER_SPEC.md` strictly forbid presenting a deterministic cryptographic hash alone as proof of issuer authenticity. We must rigorously distinguish between payload integrity and issuer identity.

### Research & Decision
1. **Canonical Payload Hashing (Payload Integrity):**
   - **Mechanism:** Compute SHA-256 over a canonicalized JSON string representation of the issued credential claims (`learner_id`, `course_id`, `completion_id`, `issued_at`, `score`).
   - **Canonicalization Rules:** Keys sorted alphabetically, whitespace stripped (`json.dumps(obj, sort_keys=True, separators=(',', ':'))`), UTF-8 encoded.
   - **Outcome:** Detects any modification or tampering with claim values relative to the authoritative issued record.
2. **Issuer Authenticity (Cryptographic Signatures):**
   - **Mechanism:** Asymmetric public-key cryptography (Ed25519) or authorized key registry. At issuance, the issuer signs the canonical payload hash using a private key. The public key is registered in the `issuers` table.
   - **Outcome:** Proves non-repudiation and authentic origin. A verifier checks the signature against the issuer's published public key.
3. **Verification Decision Matrix:**
   - Hash match + Signature valid + Not revoked = **`VALID`**
   - Hash mismatch (any claim modified) = **`TAMPERED`** (takes precedence over all other errors)
   - Hash match + Signature valid + Revocation recorded = **`REVOKED`**
   - Hash match + Signature invalid = **`INVALID_ISSUER`**
   - Credential ID not in database = **`NOT_FOUND`**

---

## 2. Relational Transaction Isolation & Concurrency Control

### Problem Statement
To prevent race conditions where concurrent issuance requests for the same completion record create duplicate credentials, the issuance workflow must guarantee strict atomicity.

### Research & Decision
1. **Storage Constraint:** Unique database index on `credentials(completion_id)`.
2. **SQLAlchemy Session Lifecycle:**
   - Execute issuance in an atomic transaction:
     ```python
     async with session.begin():
         # 1. Select CompletionRecord with row lock or check eligibility
         # 2. Insert Credential (will raise IntegrityError on duplicate)
         # 3. Insert AuditEvent
     ```
3. **Error Mapping:** Catch PostgreSQL unique violation (`IntegrityError`), rollback session, and return HTTP 409 Conflict with structured reason code `DUPLICATE_ISSUANCE_NOT_PERMITTED`.

---

## 3. High-Performance Deterministic Synthetic Data Generation

### Problem Statement
The system must generate 20,000 learners, 1,000 courses, 10,000 credentials, and 5,000 verification requests from a single seed (`42`) within 60 seconds on standard hardware, with exact byte-level checksum repeatability.

### Research & Decision
1. **PRNG Seeding:** Use Python's `random.Random(seed)` and NumPy PRNG with fixed seeds. Avoid unseeded global random states.
2. **Topological Generation Order:**
   1. `issuers` (10 issuers)
   2. `courses` (1,000 courses)
   3. `credential_rules` (1,000 active rules, 1:1 or 1:N per course)
   4. `learners` (20,000 learners)
   5. `completion_records` (~25,000 records; some passing >=80%, some failing <80%)
   6. `credentials` (10,000 credentials issued strictly for passing completions)
   7. `revocations` (~500 revoked credentials)
   8. `verification_requests` (5,000 requests distributed across valid, revoked, and nonexistent IDs)
   9. `audit_events` (issuance, revocation, verification audit entries)
3. **Bulk Insertion:** Use SQLAlchemy Core `insert()` with batches of 5,000 rows (`session.execute(insert(Model), chunk)`), avoiding slow ORM model instantiation.

---

## 4. Anomaly Fixture Generation & Ground-Truth Segregation

### Problem Statement
Constitutional Principle V mandates that ground-truth labels remain strictly segregated from the operational verification logic. Production constraints must never be relaxed to accommodate anomalies.

### Research & Decision
1. **Isolation Strategy:** Anomalies are generated in dedicated evaluation fixtures and exported into `ground_truth_anomalies.json` / CSV. They are never inserted into the production database with violated constraints.
2. **The 4 Required Anomaly Scenarios:**
   - **Anomaly 1 (Premature Issuance):** Credential timestamp < Completion timestamp. (Captured in an evaluation dataset to test eligibility validators).
   - **Anomaly 2 (Duplicate Credential ID):** Test fixture submits duplicate public ID against the database; asserted to trigger DB unique constraint rejection.
   - **Anomaly 3 (Revoked Credential Verifying Active):** Cache-invalidation test: credential is revoked in database, but verifier query tests against stale cache or evaluates authoritative status; asserted that authoritative state is returned as `REVOKED`.
   - **Anomaly 4 (Altered Payload Undetected):** Payload claim modified by 1 bit/score changed from 85 to 95. Cryptographic hash test verifies detection rate is 100%.

---

## 5. Frontend Architecture: FastAPI + Jinja2 + HTMX + Google Stitch

### Problem Statement
Per approved ADR-005, the frontend must be server-rendered Jinja2 templates enhanced with HTMX, served directly by FastAPI. Google Stitch provides the visual prototype.

### Research & Decision
1. **Template Hierarchy:**
   - `templates/base.html`: Modern layout shell, Google Font (Inter), HTMX 1.9.10 script inclusion, navigation bar, flash message container.
   - `templates/pages/`:
     - `index.html`: Dashboard with system statistics and quick actions.
     - `verify.html`: Public credential verification lookup with dynamic result card.
     - `credentials.html`: Administrative credential management and issuance table.
     - `audit.html`: Append-only audit event log feed.
   - `templates/partials/`:
     - `verification_badge.html`: HTMX fragment returning colored status badge (`VALID`, `REVOKED`, `TAMPERED`, `NOT_FOUND`).
     - `credential_row.html`: Single row for credentials table.
     - `revocation_modal.html`: HTMX-driven modal dialog for authorized revocation.
2. **HTMX Integration Pattern:**
   - Verification Form:
     ```html
     <form hx-post="/verify" hx-target="#verification-result" hx-indicator="#verify-spinner">
         <input type="text" name="credential_id" placeholder="CRD-2026-..." required />
         <button type="submit">Verify Credential</button>
     </form>
     <div id="verification-result"></div>
     ```
   - When submitted, FastAPI route `/verify` checks if the request has `HX-Request: true`. If yes, it renders `partials/verification_badge.html`. If not, it renders full `pages/verify.html`. Zero JavaScript boilerplate required.
