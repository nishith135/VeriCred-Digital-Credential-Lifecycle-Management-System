# Project-Local Workflow: YottaFlex AI Credential Lifecycle Hackathon

## 1. Project Mission

Build a working Digital Credential Lifecycle Management System for the YottaFlex AI candidate project within the official 72-hour submission window.

The project owner is the final decision-maker. AI agents are implementation assistants responsible for executing clearly defined tasks, explaining decisions, and reporting evidence.

The goal is not merely to generate code. The goal is to deliver a working, reproducible, testable system that the project owner understands and can explain during the candidate walkthrough.

Follow the global engineering workflow for general coding, security, planning, testing, and communication rules. This file defines additional project-specific requirements.

## 2. Authoritative Project References

Before meaningful implementation work, consult the relevant existing artifacts:

- `MASTER_SPEC.md`: Original project requirements and business rules.
- `.specify/memory/constitution.md`: Approved engineering principles, once established.
- Spec Kit specification: Approved functional requirements and acceptance criteria.
- Spec Kit plan: Approved architecture and technical decisions.
- Spec Kit tasks: Ordered implementation tasks and dependencies.
- `docs/AI_PROMPT_LOG.md`: AI prompt history and contribution disclosure.
- `docs/DECISIONS.md`: Significant design decisions and trade-offs.
- `docs/TEST_EVIDENCE.md`: Actual verification results.
- `docs/STATUS.md`: Current milestone, remaining time, blockers, and next actions.

Inspect the repository to determine the actual Spec Kit artifact locations. Do not assume that specifications, plans, or tasks are stored in a particular directory.

Do not create duplicate documents when equivalent artifacts already exist.

If references conflict, identify the exact conflict and propose a resolution. Do not silently override approved requirements.

## 3. Mandatory Spec Kit Workflow

Use the installed Spec Kit commands and their actual instructions. Do not invent unsupported commands or assume that every command behaves identically across versions.

Follow this sequence, adapting only when the installed tooling requires it:

1. Inspect the repository and existing instructions.
2. Establish and review the project constitution.
3. Create the functional specification from `MASTER_SPEC.md`.
4. Clarify material ambiguities and record confirmed decisions.
5. Generate the technical implementation plan.
6. Generate dependency-ordered tasks.
7. Run the available checklist and consistency analysis.
8. Resolve critical contradictions before implementation.
9. Implement approved tasks incrementally.
10. Audit the implementation against the specification before submission.

Explain each unfamiliar Spec Kit stage briefly when it is first used.

Do not spend excessive time polishing specifications. Once the mandatory requirements, key architectural decisions, and acceptance criteria are sufficiently clear, move to implementation.

## 4. Project Architecture and Technology

Use the agreed stack unless an approved technical decision changes it:

- Python and FastAPI for the backend.
- PostgreSQL for persistent storage.
- SQLAlchemy and Alembic for database models and migrations.
- Jinja2 templates, HTML/CSS, and HTMX served by FastAPI for the production frontend (Google Stitch used for visual prototyping/design reference; no React or separate Node.js build).
- Pytest for backend testing and integration tests.
- Git and a dedicated public GitHub repository.

Prefer free or locally runnable dependencies and services. Avoid unnecessary infrastructure, complex deployment dependencies, and excessive abstraction.

Before introducing a dependency, explain its purpose and check whether existing functionality can solve the problem adequately.

## 5. Non-Negotiable Business Invariants

Preserve the requirements in `MASTER_SPEC.md` and the approved specification.

At minimum:

- Credentials may be issued only after eligibility requirements pass.
- Eligibility checks and credential issuance must be protected against invalid state changes and concurrency problems.
- Credential identifiers must be unique in valid production data.
- Verification must check payload integrity, issuer authenticity, and current revocation status as specified.
- A deterministic hash alone must not be presented as proof of issuer authenticity.
- Revocation must not erase historical records or audit events.
- Important lifecycle actions, exceptions, and verification decisions must be traceable.
- Identity matching must not rely on a person's name alone.
- Synthetic records must respect valid parent identifiers, foreign keys, data types, enums, dates, and business rules.
- Ground-truth labels must remain separate from operational inputs and verification logic.
- The four mandatory anomaly scenarios must be demonstrable and detected or reported as required by the specification.
- Production database constraints must not be weakened to manufacture anomalies.
- Data generation must be reproducible using the configured seed.
- Required CSV, JSON, and SQL exports must be produced and validated.

Do not assume that a requirement is satisfied merely because a corresponding class, endpoint, or screen exists. Verify the behavior.

## 6. Execution Modes and Approval Boundaries

### Explore

Read files, inspect configuration, review requirements, investigate failures, and propose solutions.

Do not modify files during read-only investigation unless the task explicitly requires it.

### Execute

Implement tasks that are already included in an approved plan and have clear acceptance criteria.

Within the approved scope, agents may make routine implementation decisions without repeatedly asking for approval.

Before implementing a task, identify:
- The task and intended outcome.
- Relevant requirements and dependencies.
- Expected files or components.
- Acceptance criteria and verification steps.

If the task reveals a material requirement conflict, unexpected scope expansion, or significant architectural change, stop and report it.

### Restricted operations

Obtain explicit approval before destructive or irreversible actions, including:
- Deleting or bulk-rewriting important data.
- Destructive database migrations.
- Force-pushing or rewriting Git history.
- Major dependency upgrades.
- Changing critical security boundaries.
- Deploying or altering externally consequential resources.

Never commit secrets or weaken a security control to make implementation easier.

## 7. Agent Ownership and Parallel Execution

Assign one accountable owner to each task.

Parallelize only when task boundaries and dependencies are clear.

Good candidates for parallel work include:
- Independent synthetic-data generation work after schema agreement.
- Frontend development against approved API contracts.
- Independent test preparation.
- Documentation that does not conflict with active implementation.

Keep a single accountable owner for integration and shared architectural decisions.

Do not let agents independently redesign the same schema, migration, API contract, or shared file.

For each handoff, require the agent to report:
1. What changed.
2. Which files were changed.
3. Which requirements were addressed.
4. What tests or checks were actually run.
5. The actual results.
6. Known limitations and unresolved issues.
7. Any required follow-up work.

Do not assume that agents share memory, conversation history, or access to each other's prompts.

## 8. Incremental Implementation Strategy

Build and verify a minimal end-to-end workflow before expanding the system.

The initial vertical slice should demonstrate:

1. A learner and course exist.
2. Completion and assessment records satisfy eligibility rules.
3. A credential is issued only when eligible.
4. The credential can be verified.
5. The credential can be revoked.
6. Subsequent verification reflects revocation.
7. The lifecycle actions remain auditable.

After the vertical slice works, expand to:
- Remaining entities and business rules.
- Synthetic data at the required scale.
- The four anomaly scenarios.
- Verification and integrity edge cases.
- Required data exports.
- Frontend integration.
- Documentation and demonstration preparation.

Follow the approved Spec Kit task order when it differs for a justified dependency reason.

Do not generate the entire application in one unreviewed operation.

## 9. Mandatory Testing and Evidence

Test critical behavior, including both successful and unsuccessful cases.

At minimum, verify:
- Eligibility boundaries and invalid issuance attempts.
- Unique identifiers and foreign-key integrity.
- Valid and invalid credential verification.
- Payload tampering detection.
- Issuer authenticity checks.
- Current revocation status.
- Audit history preservation.
- Identity mismatches.
- All four required anomaly scenarios.
- Synthetic-data validation and reproducibility.
- Export correctness.
- Frontend-to-backend integration.
- Application setup and execution instructions.

Run relevant tests, checks, and build commands when available.

Record actual commands and results in `docs/TEST_EVIDENCE.md`.

Distinguish clearly between tests that passed, failed, were skipped, or were not run.

Never claim that the application or a feature works unless the relevant behavior has been verified. Explain any environmental limitations that prevent verification.

## 10. Mandatory AI Prompt Logging

Before completing every meaningful task, update `docs/AI_PROMPT_LOG.md` according to the repository's AI disclosure policy.

Capture the exact prompt whenever it is available, along with:
- AI tool and model, if known.
- Purpose.
- Resulting artifacts and changed files.
- Summary of output.
- Actual validation results.
- Important limitations and follow-up work.

Record significant follow-up prompts when they materially affect scope, architecture, implementation, or debugging.

Do not fabricate prompt text, tool access, test results, or user review.

If a prompt submitted in another session or tool is inaccessible, mark it as unavailable and request the original text when needed. Do not claim that the log is complete without checking available records.

Never place secrets or sensitive information in the public prompt log. Redact them appropriately and record that redaction occurred.

The project owner remains responsible for reviewing the prompt history and explaining the actual use of AI in the submission.

## 11. Time and Scope Management

The official submission window is 72 hours from the timestamp specified by YottaFlex AI.

Track:
- Confirmed deadline and time zone.
- Remaining time.
- Current milestone.
- Completed acceptance criteria.
- Blockers and high-risk tasks.
- Next highest-value action.

Maintain a realistic work schedule that includes breaks, integration, testing, documentation, and submission.

Prioritize correctness and a demonstrable core workflow over optional features, visual polish, or elaborate architecture.

If time becomes insufficient, propose specific scope reductions that preserve mandatory requirements. The FAQ permits partial solutions when incomplete work, limitations, deviations, and next steps are disclosed honestly.

Do not sacrifice integrity, security, or honest reporting to meet the deadline.

## 12. Project Documentation

Maintain existing project documentation and create the following only if equivalent artifacts do not already exist:

- `docs/AI_PROMPT_LOG.md`: Prompt history and AI contribution disclosure.
- `docs/DECISIONS.md`: Important decisions, alternatives, rationale, and trade-offs.
- `docs/TEST_EVIDENCE.md`: Verification commands, results, and remaining gaps.
- `docs/STATUS.md`: Current milestone, remaining time, blockers, and next actions.

Update documentation as meaningful changes occur, not just at the end.

Avoid duplicate documentation and do not spend disproportionate time maintaining notes that do not help development, verification, or submission.

## 13. GitHub and Submission Readiness

Use a dedicated public GitHub repository.

Create meaningful commits at stable milestones. Review diffs before committing and keep secrets out of the repository.

Ensure the README explains:
- Project purpose and scope.
- Required dependencies and environment.
- Installation and configuration.
- Database setup and migrations.
- How to run the backend and frontend.
- How to generate and validate synthetic data.
- How to run tests and reproduce important behaviors.
- Known limitations and incomplete requirements.

Before submission, verify:
- The repository is publicly accessible.
- Setup instructions have been followed and tested where feasible.
- Core behavior is demonstrable.
- Required artifacts and data exports exist.
- Prompt history is accurate to the extent available.
- Important design decisions and test evidence are documented.
- No secrets or unauthorized proprietary content are present.
- The demonstration can be explained by the project owner.

## 14. Completion Reporting

At the end of each meaningful task, report:
- Actual changes and affected files.
- Requirements addressed.
- Tests and checks executed, with results.
- Unverified behavior and known limitations.
- Relevant prompt-log and decision-log updates.
- The next recommended action.

Do not report a task as complete merely because code was generated.

Before the final submission, perform a requirements-to-implementation review and report unresolved gaps honestly.

The project owner makes final acceptance decisions.
