# Credential Lifecycle Management System --- Master Specification

**Document type:** Master project context / source of truth\
**Status:** Initial draft --- ready for implementation planning and
controlled refinement\
**Version:** 0.1\
**Project context:** Solo hackathon build, starting from scratch\
**Time constraint:** 70 hours across 3 days\
**Proposed stack:** Python, FastAPI, PostgreSQL, React\
**Primary objective:** Deliver a working, demonstrable, testable
end-to-end credential lifecycle system and the required reproducible
synthetic-data package.

> **Instructions for coding agents:** Read this document before making
> changes. Treat it as the primary project context. Do not silently
> change requirements, entity names, ID conventions, business rules, API
> contracts, or architecture. If a requirement is ambiguous, consult the
> "Assumptions and decisions" section, choose the safest minimal option
> only when necessary, and document the decision. Prefer small, testable
> changes over generating the entire application in one pass. Run
> relevant tests after changes and update the implementation status.

------------------------------------------------------------------------

## 1. Executive summary

Build a digital credential lifecycle management system for an academic
setting. The system records course completion evidence, evaluates
credential eligibility, issues unique credentials only when requirements
pass, enables third-party verification, supports credential revocation,
preserves audit history, and evaluates its behavior against documented
rules.

The project has two tightly connected deliverables:

1.  **Working application:** React frontend, FastAPI backend, PostgreSQL
    database, issuance/verification/revocation workflows, and audit
    views.
2.  **Reproducible data and evaluation package:** Python synthetic-data
    generator, specified data volumes, four labelled anomaly scenarios,
    separate ground-truth data, CSV/JSON/SQL exports, validation
    reports, fixed-seed reproducibility, and documentation.

The project must not be merely a certificate-PDF generator or a CRUD
dashboard. Its central value is enforcing the credential lifecycle rules
and demonstrating correctness under normal, boundary, and deliberately
invalid conditions.

## 2. Original challenge summarized

The challenge requires a solution that issues credentials after
completion requirements are met and supports revocation and third-party
verification. It should expose important decisions and exceptions,
preserve traceability, and produce measurable outputs.

Required actors/systems: - Learner - Instructor - Academic
administrator - Support staff - Platform administrator

Required entities: - Learner - Course - CredentialRule -
CompletionRecord - Credential - Issuer - VerificationRequest -
Revocation - AuditEvent

Required synthetic-data baseline: - 20,000 learners - 1,000 courses -
10,000 credentials - 5,000 verification requests

Required anomaly scenarios: 1. Credential issued before completion. 2.
Duplicate credential ID. 3. Revoked credential incorrectly verifies as
active. 4. Altered payload whose integrity failure is not detected.

Required engineering outputs include a data dictionary, valid
parent/child generation order, deterministic IDs, derived values
calculated from source records, separate ground truth, integrity
validation, CSV/JSON/SQL exports, README, schema documentation,
generator command, fixed seed, source manifest, validation summary, and
a repeatability demonstration using the same seed.

External data is optional. Synthetic data is preferred unless a lawful,
suitable public source materially improves the project. Never bypass
access controls or use confidential/personal information without a
lawful basis.

## 3. Goals

### 3.1 Mandatory goals

-   Enforce documented eligibility rules before normal credential
    issuance.
-   Generate unique and stable credential identifiers.
-   Associate credentials with valid learner, course/completion, rule
    and issuer records.
-   Store integrity-verification metadata for issued credentials.
-   Let a third party submit a credential for verification.
-   Check current revocation status during verification.
-   Record verification requests, including unsuccessful requests.
-   Support authorized revocation with a reason and actor.
-   Preserve issuance, verification, revocation and other important
    event history without silently overwriting it.
-   Implement and evaluate all four required anomaly scenarios.
-   Keep ground-truth labels separate from verification inputs.
-   Generate the required baseline data volumes with a fixed seed and
    configurable scale.
-   Validate primary keys, foreign keys, enums, date ordering, lifecycle
    transitions, duplicate identifiers and derived values.
-   Export CSV, JSON and SQL seed/schema data.
-   Document setup, schema, generator invocation, seed,
    source/provenance, validation and evaluation.
-   Provide measurable results based on actual test runs.
-   Provide a usable interface for demonstrating the main workflow.

### 3.2 Non-goals unless time remains

-   Blockchain or distributed ledger.
-   Machine-learning-based credential decisions.
-   Microservices or event streaming infrastructure.
-   Complex notification systems.
-   Unnecessary external integrations.
-   Elaborate visual design that does not improve the core
    demonstration.
-   Real student or institutional data when synthetic data is
    sufficient.

## 4. Time and delivery constraints

The developer is working solo and has 70 hours across three days. The
plan must prioritize correctness and integration over optional features.
The intended approach is: 1. Define rules and acceptance criteria. 2.
Bootstrap the app and database. 3. Build a minimal complete credential
lifecycle. 4. Build the deterministic generator and anomaly evaluation.
5. Build the React interface against real APIs. 6. Run full-scale data
validation and tests. 7. Finalize exports, documentation, and
demonstration.

Do not assume 70 hours of uninterrupted productive coding. Protect sleep
and breaks. If the schedule slips, reduce visual polish and optional
features before cutting mandatory requirements, integrity checks, or
testing.

## 5. Actors and access expectations

These are the intended role responsibilities. They may be implemented as
role-based permissions in one application; separate applications are not
required.

### Learner

-   View own completion records.
-   View and retrieve own issued credentials.
-   Share a credential identifier or verification link.

### Instructor

-   Create or update permitted assessment/completion evidence.
-   View completion eligibility.
-   Cannot issue/revoke credentials unless explicitly granted additional
    authority.

### Academic administrator

-   Manage credential rules within authorized scope.
-   Review eligibility and issuance exceptions.
-   Perform or authorize issuance and revocation according to policy.

### Support staff

-   Inspect verification failures and relevant history.
-   Investigate disputes and escalate anomalies.
-   Cannot silently change credential status or erase audit history.

### Platform administrator

-   Manage technical configuration and user/role access.
-   Monitor system health and data-quality outcomes.
-   Administrative privileges must not be presented as proof that
    historical events cannot be tampered with.

### Third-party verifier

-   May be an unauthenticated public verification endpoint for a
    credential ID or verification URL.
-   Receives only the minimum information necessary to establish
    authenticity and current status.
-   Cannot edit learner records, issue credentials, or revoke
    credentials.

**Security requirement:** Enforce permissions on the backend, not only
by hiding frontend controls. Do not expose secrets, private keys,
unnecessary personal information, or internal ground-truth labels
through public endpoints.

## 6. Core end-to-end workflow

1.  Create master data: learners, courses, credential rules and issuers.
2.  Record a learner's completion and assessment evidence.
3.  Evaluate eligibility against the applicable rule version.
4.  If eligible, create a unique credential and trusted integrity
    metadata in a database transaction.
5.  Record the issuance audit event.
6.  Accept a third-party verification request.
7.  Verify credential existence, issuance eligibility/provenance,
    payload integrity, issuer authenticity according to the selected
    mechanism, and current revocation status.
8.  Record the request and result, including failed verification
    attempts.
9.  If an authorized administrator revokes the credential, record a
    revocation event and audit event without deleting the original
    issuance or prior verification history.
10. Subsequent verification requests must reflect the current revocation
    status.
11. Run validation/evaluation against independent ground truth and
    report actual metrics.

## 7. Business rules

The rules below are the baseline behavior. Any unresolved policy choices
are identified as assumptions and must be documented before
implementation.

### 7.1 Eligibility and issuance

-   A credential may be issued only when all mandatory conditions in the
    applicable CredentialRule pass.
-   Completion evidence must reference existing learner and course
    records.
-   Completion must be final/complete, and required assessment criteria
    must pass.
-   Rule effective dates/version must be respected. Do not silently
    apply a later rule to historical evidence without an explicit
    policy.
-   Credential IDs must be unique and immutable.
-   A normal issuance attempt must not create a second credential for
    the same completion unless a documented reissue policy explicitly
    permits it.
-   Issuance, associated metadata and its audit event should be
    committed atomically or fail together.
-   Failed issuance attempts should return a clear reason and may be
    recorded as an audit event where useful.
-   Derived eligibility and status values must be computed from source
    records/rules, not independently randomized.

### 7.2 Credential lifecycle

Suggested states/results: - `VALID` --- credential exists, issuance is
valid, integrity and issuer checks pass, and it is not revoked. -
`REVOKED` --- a valid credential has a current recorded revocation. -
`TAMPERED` --- integrity validation fails. - `NOT_FOUND` --- no
credential matches the submitted identifier. - `INVALID_ISSUANCE` ---
credential exists but its issuance violates required rules, such as
being issued before completion.

These are verification outcomes, not necessarily all database lifecycle
states. Store credential state and verification decision separately
where appropriate. Define and test a consistent precedence when multiple
conditions fail. A safe default is to avoid ever returning `VALID` if
any required check fails. The exact displayed result for a credential
that is both revoked and tampered must be documented and tested.

### 7.3 Revocation

-   Only an authorized actor may revoke a credential.
-   A revocation must reference an existing credential, include a
    reason, actor and timestamp, and generate an audit event.
-   Do not delete the credential or rewrite the issuance date.
-   Verification must consult current authoritative revocation state,
    not stale cached state.
-   Repeated revocation attempts must be handled idempotently or
    rejected clearly.
-   Reinstatement is out of scope unless explicitly designed and
    documented. Do not implicitly turn a revoked credential back into a
    valid one.

### 7.4 Verification

-   Verification uses a stable credential identifier or verification
    URL/token, not learner name alone.
-   Record the request timestamp, requested credential reference where
    available, result, reason code and relevant integrity check outcome.
-   Do not expose ground truth to the verification service.
-   Do not return `VALID` if the credential is missing, issuance is
    invalid, integrity fails, issuer authentication fails, or revocation
    is active.
-   Verification should be deterministic for the same authoritative
    state and submitted payload.
-   Public output should disclose only the minimum information
    necessary.

### 7.5 Audit history

-   Record important actions such as issuance, verification, revocation,
    rule changes and relevant administrative changes.
-   Each event should include a unique event ID, event type, timestamp,
    actor or system identity when available, target entity/reference,
    and structured details.
-   Ordinary application flows must not update or delete prior audit
    events.
-   Preserve previous verification requests even if the credential is
    later revoked.
-   Use database permissions and application-level controls to protect
    audit records. A normal table alone is not an absolute guarantee
    against a sufficiently privileged database administrator.

## 8. Data model and relationships

Every entity requires a primary key. Every relationship requires an
appropriate foreign key and documented cardinality. Use bridge tables
for genuine many-to-many relationships. Validate joins and preserve
event history.

### 8.1 Learner

Represents a learner. Likely fields: internal primary key, immutable
public learner ID, display name, optional contact fields, status,
created timestamp. Names may be duplicated; do not use names as unique
identity keys.

### 8.2 Course

Represents a course or course version. Likely fields: primary key,
public course ID, title, version, status, created timestamp.

### 8.3 CredentialRule

Defines the eligibility policy. Likely fields: primary key, course
reference or applicable scope, rule version, minimum assessment score,
completion requirements, effective-from/effective-to timestamps, active
status, rule configuration. Rules must be versioned or otherwise
traceable so the applied policy can be established later.

### 8.4 CompletionRecord

Stores a learner's course completion and assessment evidence. Likely
fields: primary key, learner foreign key, course foreign key, applicable
rule reference/version where appropriate, assessment score,
attendance/completion evidence, completion status, completion timestamp,
source/reference metadata. Validate score/percentage ranges and date
consistency. One learner can have multiple completion records across
courses or attempts, according to the documented model.

### 8.5 Credential

Represents an issued credential. Likely fields: primary key, immutable
public credential ID, completion foreign key, issuer foreign key,
rule/version reference or issuance snapshot, issued timestamp,
payload/canonicalization version, payload hash, signature metadata if
used, current lifecycle status where needed. Enforce public credential
ID uniqueness. Use a uniqueness constraint to prevent unintended
duplicate issuance for the same completion under the chosen policy.

### 8.6 Issuer

Represents the organization or authorized issuer. Likely fields: primary
key, stable issuer ID, name, status, version/configuration history,
public-key metadata if digital signatures are used. Issuer changes must
not silently invalidate historical credentials. Preserve the issuer
identity/configuration relevant at issuance time.

### 8.7 VerificationRequest

Represents every verification attempt. Likely fields: primary key,
public verification ID, credential reference where resolvable, request
timestamp, outcome, reason code, integrity result, requester category or
privacy-safe metadata. A failed lookup may not have a credential foreign
key; model this as an optional relationship where appropriate.

### 8.8 Revocation

Represents a revocation event. Likely fields: primary key, credential
foreign key, revocation sequence/event ID, reason, actor, timestamp,
status/effective date if needed. A credential can have no revocation
event or one/more recorded attempts/events depending on the final model.
Define whether the table stores successful revocations only or also
attempted actions.

### 8.9 AuditEvent

Represents a historical event. Likely fields: primary key, event ID,
event type, actor ID/type, target entity/type and identifier, occurred
timestamp, structured details, correlation/request ID. Relationships to
actor records may be optional if actors are not modeled as a separate
entity. Avoid polymorphic foreign-key designs that falsely imply
database-enforced integrity; document the chosen approach.

### 8.10 Relationship expectations

At minimum, document and enforce: - Learner 1:N CompletionRecord. -
Course 1:N CompletionRecord. - Course/rule scope 1:N CredentialRule
where rules are course-specific. - CompletionRecord 0:1 Credential under
a one-credential-per-completion policy. - Issuer 1:N Credential. -
Credential 1:N VerificationRequest. - Credential 0:N
Revocation/audit-related events according to the chosen event model. -
AuditEvent records relevant issuance, verification, revocation and
administrative changes. - If learners and courses require explicit
enrollment records or other many-to-many links, use a bridge table
rather than storing lists of IDs in a field.

Finalize exact cardinalities, optional relationships and uniqueness
constraints in the ER diagram/data dictionary before scaling data
generation.

## 9. ID conventions

The challenge gives these examples: - Credential: `CRD-2026-000001` -
Learner: `LRN-000001` - Completion: `CMP-<learner-id>-<course-id>` -
Verification: `VER-2026-000001` - Revocation: `REV-<credential-id>-01`

Use consistent, immutable, zero-padded IDs. The challenge's
completion/revocation examples are patterns; settle on exact normalized
formats in the data dictionary. For example, a course could use
`CRS-000001`, and a completion ID could be `CMP-LRN-000001-CRS-000001`.
Do not change the format midway through generation. Keep database
primary keys separate from public IDs if useful, and enforce uniqueness
on public IDs.

Duplicate-ID anomaly handling must not weaken normal database
constraints. Test it through a controlled malformed import/fixture or
validation scenario and label it in ground truth.

## 10. Integrity and authenticity design

### Baseline option

Use a canonical credential payload and SHA-256 digest. Canonicalization
must be deterministic: fixed field set, stable field
ordering/serialization, consistent date/time formatting, and documented
encoding/version. Recompute the digest during verification and compare
it against a trusted reference.

### Security limitation

A hash by itself does not prove who issued a credential. If an attacker
can alter both the payload and the trusted hash, a simple comparison may
not detect the change. If issuer authenticity is required, use a digital
signature (for example, an asymmetric signing key and corresponding
public key) and protect the private key appropriately.

Choose the smallest implementation that provides a defensible integrity
story within the deadline. Never claim that hashing alone proves issuer
identity or that the system is tamper-proof.

### Required integrity tests

-   Unchanged canonical payload passes the integrity check.
-   A changed signed/hashed field fails the integrity check.
-   Unknown or malformed credential data fails safely.
-   A test fixture simulating the required "altered payload not
    detected" defect is correctly flagged by the evaluation harness.
-   The verification service does not use anomaly labels or ground-truth
    fields to decide its result.

## 11. Synthetic-data specification

### 11.1 Required baseline volumes

-   20,000 learners.
-   1,000 courses.
-   10,000 credentials.
-   5,000 verification requests.
-   Generate related completion, rule, issuer, revocation and audit
    records according to documented distributions and lifecycle rules.

These counts are targets for the baseline dataset. They do not justify
issuing credentials to ineligible completions. Generate enough valid
completion candidates to support the credential target, then issue only
where rules pass. Document any special relationship between baseline
data and deliberate anomaly fixtures so all exported counts can be
reconciled.

### 11.2 Determinism and scale

-   Fixed default seed: `20261022`.
-   The seed and scale/configuration must be explicit
    command-line/configuration inputs.
-   Starter and full datasets must use the same generation logic.
-   Same seed, configuration, generator version and dependency
    environment should reproduce the same logical records and exported
    outputs.
-   Avoid current-time-dependent fields unless a fixed reference time is
    injected.
-   Sort exports deterministically and normalize serialization before
    checksum calculation.
-   Generate records in dependency order; do not generate child
    references to nonexistent parents.

### 11.3 Generation order

1.  Learner, Course, Issuer and CredentialRule master records.
2.  CompletionRecord and assessment evidence.
3.  Eligibility outcomes calculated from documented rules.
4.  Credential records for eligible completions only.
5.  Revocation and VerificationRequest events.
6.  AuditEvent history corresponding to the generated actions.
7.  Controlled anomaly fixtures and separate ground truth.
8.  CSV/JSON/SQL exports and validation reports.

### 11.4 Realistic variation

Include realistic variation in course participation, assessment scores,
completion states, dates, verification outcomes, revocations, duplicate
learner names and issuer changes. Use documented distributions and
constraints. Do not independently randomize outcomes that should be
derived from source records.

### 11.5 Four required anomaly types

1.  **Credential issued before completion:** Issue timestamp precedes
    completion timestamp or completion evidence is not yet available.
    Expected result: flag as `INVALID_ISSUANCE`, not `VALID`.
2.  **Duplicate credential ID:** Two malformed/imported records share a
    supposedly unique public ID. Expected result: normal writes reject
    the duplicate; validation identifies and reports the malformed
    fixture.
3.  **Revoked credential verifies as active:** A revocation event exists
    but the test case's buggy/stale verification result says active.
    Expected result from the correct implementation: `REVOKED`.
4.  **Altered payload hash not detected:** Payload content is changed
    while the test case models a faulty integrity-check result. Expected
    result from the correct implementation: `TAMPERED`.

Keep anomaly fixtures identifiable using `issue_type` and/or
`ground_truth` in the evaluation dataset, not as trusted verification
inputs. Where an anomaly violates a database constraint, isolate it in a
malformed-import fixture or test dataset instead of corrupting the valid
production-like baseline tables.

### 11.6 Ground truth

Create a separate `ground_truth.csv` or JSON file containing at least: -
Stable case/record identifier. - `issue_type` or expected-label field. -
Expected decision/outcome. - Reason for the expected decision. -
Optional severity/category and source fixture ID.

The verification algorithm must not read these labels. The evaluation
script may read them to compare expected and actual results.

### 11.7 Export package

Produce CSV, JSON and SQL schema/seed exports as appropriate, plus: -
README and exact generation command. - Data dictionary and schema/ER
diagram. - Fixed seed and scale configuration. - Generator
version/configuration information. - Source manifest (for synthetic
data, document that data is synthetic and explain the generation method;
for external sources, include URL, version, retrieval date, license,
attribution, transformations and discarded fields). - Validation
summary. - Row counts and checksums. - Reproducibility comparison
report.

## 12. Validation and evaluation

### 12.1 Data validation

Check: - Primary-key uniqueness. - Public-ID uniqueness in normal
tables. - Foreign-key integrity and valid joins. - Required fields and
allowed enum values. - Numeric ranges and date ordering. - Credential
issuance eligibility. - Completion/credential/issuer consistency. -
Revocation lifecycle consistency. - Duplicate-ID anomaly detection in
controlled fixtures. - Reconciliation of exported row counts and derived
totals. - Deterministic output across two runs with the same
configuration.

### 12.2 Functional tests

At minimum: - Eligible completion can be issued. - Ineligible completion
is rejected with a reason. - Duplicate issuance is prevented. - Correct
credential verifies as valid. - Unknown credential returns
`NOT_FOUND`. - Revoked credential returns `REVOKED`. - Altered payload
returns `TAMPERED`. - Pre-completion issuance returns
`INVALID_ISSUANCE`. - Duplicate ID is rejected/reported. - Identity
matching does not rely on name alone. - Unauthorized user cannot
issue/revoke. - Failed verification is recorded. - Audit history is not
overwritten by subsequent events. - Repeated revocation attempts behave
consistently. - API errors do not leave partial issuance/revocation
changes.

### 12.3 Metrics

Calculate from actual outcomes, not hardcoded values: - Issuance
decision accuracy against rules/ground truth. - Verification accuracy. -
Revocation detection rate. - Tampering detection rate. - False
acceptance rate. - False rejection rate. - Duplicate-ID detection
count/rate. - Foreign-key/integrity error count. - Dataset row counts. -
Generation and validation runtime. - Verification latency or throughput
if time permits. - Reproducibility/checksum match.

Report denominators alongside rates. A system that rejects every
credential is not accurate just because it rejects all revoked
credentials; test both valid and invalid cases.

## 13. Proposed technology architecture

### Frontend

-   React.
-   A small set of screens: dashboard, completion/issuance, public
    verification, revocation management, audit/validation results.
-   All meaningful data and decisions must come from real API responses,
    not hardcoded mock values.

### Backend

-   Python + FastAPI.
-   SQLAlchemy for persistence.
-   Alembic for schema migrations.
-   Pydantic schemas for API input/output validation.
-   Pytest for automated tests.
-   Separate service modules for eligibility, issuance, verification,
    revocation and audit.
-   Keep business logic out of route handlers where practical.

### Database

-   PostgreSQL.
-   Foreign keys, unique constraints, check constraints and indexes
    where appropriate.
-   Transactions for state-changing workflows.
-   Append-only application behavior for audit events.
-   Use migrations rather than manual schema drift.

### Data generation and evaluation

-   Python scripts using the same documented business rules where
    practical.
-   Deterministic pseudorandom generation with an explicit seed.
-   Bulk inserts/efficient loading for full volume.
-   Independent validation/evaluation scripts.

### Avoid unnecessary infrastructure

Do not add Redis, Kafka, microservices, blockchain, ML, or external
services without a demonstrated requirement. Use a simple deployable
architecture that is easy to explain to judges.

## 14. API surface (initial proposal)

Exact routes and request/response schemas must be finalized in
`API_SPEC.md`. Suggested resource operations:

-   `GET /health` --- application health.
-   `GET /learners`, `GET /learners/{id}` --- learner lookup.
-   `GET /courses`, `GET /courses/{id}` --- course lookup.
-   `GET /completions/{id}` --- completion details.
-   `POST /credentials/issue` --- evaluate and issue if eligible.
-   `GET /credentials/{credential_id}` --- authorized credential detail.
-   `POST /verify` --- submit a credential ID/payload and receive a
    decision.
-   `POST /credentials/{credential_id}/revoke` --- authorized
    revocation.
-   `GET /credentials/{credential_id}/audit` --- authorized audit
    history.
-   `GET /reports/summary` --- dashboard counts and evaluation summary.
-   Administrative routes for rules, issuers, data validation and role
    administration as needed.

Use consistent HTTP status codes and structured error responses.
Validate inputs, authorize state-changing operations, and avoid exposing
private/internal fields through public verification.

## 15. UI expectations

Minimum practical screens: 1. **Dashboard:**
learner/course/credential/request totals, current revoked count, anomaly
count and evaluation indicators. 2. **Completion and issuance:** inspect
evidence, show eligibility decision and reason, issue only if permitted.
3. **Public verification:** enter credential ID or use a verification
URL; show outcome and safe explanatory reason. 4. **Revocation
management:** authorized revocation with reason and confirmation. 5.
**Audit/data quality:** inspect event history, validation failures,
labelled test anomalies and evaluation summary.

Prioritize clear, reliable workflows over visual complexity. Use
loading, error, empty and success states. Never trust frontend role
restrictions as the only authorization layer.

## 16. Acceptance criteria / definition of done

The project is ready for submission only when: - All nine required
entities and relationships are documented and implemented. - The core
issue → verify → revoke → verify lifecycle works end to end. -
Eligibility is enforced by the backend. - Credential IDs are unique and
stable in normal operation. - Integrity checks behave correctly. -
Revocation status is current during verification. - Audit and
verification histories are preserved. - All four anomaly scenarios have
labelled fixtures and correct expected outcomes. - Ground truth is
separate from verification inputs. - Required baseline volumes are
generated and reconciled. - Validation checks cover keys, joins, dates,
states and derived values. - The same seed/configuration reproduces the
dataset. - CSV/JSON/SQL exports and documentation are present. -
Evaluation metrics are computed from actual outputs. - A reviewer can
run the app using the README. - The final demonstration uses the actual
integrated system.

## 17. Suggested repository layout

``` text
credential-lifecycle/
├── MASTER_SPEC.md
├── README.md
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── db/
│   ├── migrations/
│   └── tests/
├── frontend/
│   └── src/
├── scripts/
│   ├── generate_data.py
│   ├── inject_anomalies.py
│   ├── validate_data.py
│   ├── export_data.py
│   └── evaluate.py
├── data/
│   ├── generated/
│   ├── ground_truth/
│   └── reports/
└── docs/
    ├── REQUIREMENTS.md
    ├── BUSINESS_RULES.md
    ├── ARCHITECTURE.md
    ├── ERD.md
    ├── DATA_DICTIONARY.md
    ├── API_SPEC.md
    ├── TEST_PLAN.md
    ├── IMPLEMENTATION_PLAN.md
    └── DECISIONS.md
```

Do not create empty documents just to match this layout. Create or split
documents when they are useful and keep the master specification as the
high-level context source.

## 18. Coding-agent operating protocol

Any coding agent working on this project must: 1. Read `MASTER_SPEC.md`
and relevant focused documents before implementing a task. 2. Inspect
the current repository and report what already exists before changing
it. 3. Work on one bounded task at a time. 4. State assumptions and
planned files before large changes. 5. Avoid changing business rules,
entity names, ID formats or API contracts without documenting the
decision. 6. Add/update tests for behavior changes. 7. Run relevant
tests and report actual commands/results; never claim tests passed if
they were not run. 8. Avoid destructive changes, real secrets, and
unreviewed database resets. 9. Update implementation status, known
issues and documentation after completing a task. 10. Prefer migrations
and backward-compatible changes when possible. 11. Never use
ground-truth labels as inputs to production verification decisions. 12.
Never silently fabricate validation metrics, generated data counts, or
deployment status.

### Context-recovery prompt for a new agent session

> Read `MASTER_SPEC.md` first. Then inspect the current repository,
> README, implementation plan/status, decision log, relevant code and
> tests. Summarize the project objective, current implementation state,
> completed tasks, failing tests, unresolved decisions and next
> recommended task. Do not rewrite existing code or regenerate files
> until you understand their current state. Follow the master
> specification, make the smallest useful change, run relevant tests,
> and update status/documentation with actual results.

## 19. Assumptions and decisions to finalize

These are design choices, not requirements explicitly fixed by the
challenge. Resolve them early and record decisions in
`docs/DECISIONS.md`.

1.  **Eligibility thresholds:** The challenge does not specify exact
    score or attendance thresholds. Choose and document appropriate
    illustrative thresholds and required completion conditions.
2.  **Rule versioning:** Decide how a credential records the rule
    version/snapshot used at issuance.
3.  **One credential per completion:** Assume one credential per
    eligible completion unless a documented reissue policy is required.
4.  **Issuer authenticity:** Decide whether deterministic hashes are
    sufficient for the demonstrator or whether digital signatures are
    needed. Do not overstate what hashes prove.
5.  **Verification result precedence:** Define the response when
    multiple defects exist.
6.  **Revocation model:** Decide whether only successful revocations are
    stored in `Revocation` and all attempts are stored in `AuditEvent`,
    or whether the model stores multiple revocation-related events.
7.  **Identity/privacy:** Choose stable identifiers and minimal public
    disclosure.
8.  **Anomaly isolation:** Decide whether invalid cases live in a
    separate fixture/import dataset or in specially marked tables. Do
    not weaken production constraints to make anomalies easy to insert.
9.  **Volume reconciliation:** Define how the target of 10,000
    credentials is achieved without issuing credentials for ineligible
    completions.
10. **Deployment:** Decide whether local Docker-based execution is
    sufficient or a hosted deployment is necessary for judging.
11. **Authentication:** Select the minimum secure approach needed to
    distinguish roles and protect issue/revoke operations.
12. **Time budget:** Keep optional features out of the critical path.

## 20. Current implementation status

At the creation of this document: - Requirements understood: initial
draft captured here. - Architecture: proposed, not yet implemented. -
Repository/codebase: not started. - Database schema/migrations: not
started. - Synthetic generator: not started. - Frontend: not started. -
Tests/evaluation: not started. - Deployment/demo: not started.

Update this section as implementation progresses. Do not leave it stale
once coding begins.

------------------------------------------------------------------------

## Final project principle

Build a small, correct, end-to-end credential lifecycle first. Then
scale the dataset, implement and evaluate the required anomalies,
improve the interface, and produce reproducible evidence. Prefer
correctness, traceability, data integrity and demonstrable results over
unnecessary technical complexity.
