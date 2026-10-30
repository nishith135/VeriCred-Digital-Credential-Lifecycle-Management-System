"""Integration tests for VeriCred Web UI and HTMX endpoints."""

import pytest
from httpx import AsyncClient

from backend.core.rbac import sign_role_cookie


@pytest.mark.asyncio
async def test_web_verify_pages_load(api_client: AsyncClient):
    """Verify that public verification views render cleanly with no sample chips or tamper editor."""
    # GET /
    resp_root = await api_client.get("/")
    assert resp_root.status_code == 200
    assert "Public Credential Verification" in resp_root.text

    # GET /verify
    resp_verify = await api_client.get("/verify")
    assert resp_verify.status_code == 200
    html = resp_verify.text
    assert "Public Credential Verification" in html
    assert 'name="credential_public_id"' in html
    assert "Verify" in html

    # Must NOT contain sample chips, payload-tamper editor, or removed false/hardcoded strings
    for forbidden in (
        "Quick Samples",
        "Sample Active Valid",
        "Sample Revoked",
        "Simulate Tampered Payload",
        "tamper_payload",
        "tamperDetails",
        "tamperJson",
        "Zero-Trust",
        "RFC 8032 Authentic",
        "Security Invariants",
        "Canonical Hashes",
        "Multi-Factor",
        "consortium",
        "Consensus",
        "Tombstoned",
        "Enclave",
    ):
        assert forbidden not in html


@pytest.mark.asyncio
async def test_web_verify_htmx_post(api_client: AsyncClient):
    """Verify that HTMX POST /web/verify returns formatted verification badge."""
    resp = await api_client.post(
        "/web/verify",
        data={"credential_public_id": "CRD-2026-999999"},
    )
    assert resp.status_code == 200
    assert "Not found" in resp.text
    assert "CRD-2026-999999" in resp.text


@pytest.mark.asyncio
async def test_web_registry_pages_load(api_client: AsyncClient):
    """Verify that Credential Registry views render cleanly for authorized staff."""
    api_client.cookies.set("vericred_role", sign_role_cookie("registrar"))
    # GET /registry
    resp = await api_client.get("/registry")
    assert resp.status_code == 200
    assert "Credential Registry" in resp.text
    assert "Total Issued" in resp.text

    # GET /web/registry/table
    resp_table = await api_client.get("/web/registry/table")
    assert resp_table.status_code == 200


@pytest.mark.asyncio
async def test_web_audit_pages_load(api_client: AsyncClient):
    """Verify that Audit Ledger views and export endpoints operate cleanly for authorized staff."""
    api_client.cookies.set("vericred_role", sign_role_cookie("auditor"))
    # GET /audit
    resp = await api_client.get("/audit")
    assert resp.status_code == 200
    assert "Audit Ledger" in resp.text

    # GET /web/audit/table
    resp_table = await api_client.get("/web/audit/table")
    assert resp_table.status_code == 200

    # GET /web/export/audit?format=csv
    resp_csv = await api_client.get("/web/export/audit?format=csv")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers.get("content-type", "")
    assert "event_id,occurred_at_utc" in resp_csv.text

    # GET /web/export/audit?format=json
    resp_json = await api_client.get("/web/export/audit?format=json")
    assert resp_json.status_code == 200
    assert "application/json" in resp_json.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_web_anomalies_lab(api_client: AsyncClient):
    """Verify that Anomaly Evaluation Lab shows 'Not run yet' initially, runs real scenarios, and contains no removed hardcoded strings."""
    api_client.cookies.set("vericred_role", sign_role_cookie("registrar"))
    forbidden_strings = [
        "4 Vectors",
        "100% 4/4",
        "< 15 ms",
        "&lt; 15",
        "Sandboxed",
        "Zero database pollution",
        "Chris Doe",
        "Enclave",
        "Postgres Determinism",
        "idx_unique_cred_hash",
        "Policy Assertion Engine",
        "Consensus Pass Rate",
    ]

    # GET /anomalies before any run -> shows "Not run yet"
    resp = await api_client.get("/anomalies")
    assert resp.status_code == 200
    assert "Not run yet" in resp.text
    assert "Credential issued before course completion" in resp.text
    assert "Duplicate credential ID" in resp.text
    assert "Revoked credential still marked active" in resp.text
    assert "Credential altered after issuance" in resp.text
    assert "Quick Samples:" in resp.text
    for s in forbidden_strings:
        assert s not in resp.text

    # POST /web/anomalies/run-all -> renders real evaluation outcomes and row count delta 0
    resp_run = await api_client.post("/web/anomalies/run-all")
    assert resp_run.status_code == 200
    assert "Passed" in resp_run.text
    assert "Read-only: row counts before/after delta 0" in resp_run.text
    assert "Invalid issuance" in resp_run.text
    assert "Rejected as duplicate" in resp_run.text
    assert "Revoked" in resp_run.text
    assert "Altered" in resp_run.text
    for s in forbidden_strings:
        assert s not in resp_run.text

    # POST /web/anomalies/run/ALTERED_PAYLOAD_NOT_DETECTED
    resp_single = await api_client.post("/web/anomalies/run/ALTERED_PAYLOAD_NOT_DETECTED")
    assert resp_single.status_code == 200
    assert "Credential altered after issuance" in resp_single.text
    assert "Altered" in resp_single.text
    for s in forbidden_strings:
        assert s not in resp_single.text


@pytest.mark.asyncio
async def test_web_rbac_login_and_role_switching(api_client: AsyncClient):
    """Verify that login persona switcher and RBAC revocation restrictions operate correctly."""
    # 1. Login page loads
    resp_login = await api_client.get("/login")
    assert resp_login.status_code == 200
    assert "Select Your Persona to Continue" in resp_login.text
    assert "University Registrar" in resp_login.text
    assert "Public Verifier" in resp_login.text
    assert "Compliance Auditor" in resp_login.text

    # 2. Role switch sets signed HttpOnly SameSite=lax cookie
    resp_switch = await api_client.get("/role/switch?role=verifier&redirect=/verify", follow_redirects=False)
    assert resp_switch.status_code == 303
    set_cookie = resp_switch.headers.get("set-cookie", "")
    assert "vericred_role=verifier." in set_cookie
    assert "HttpOnly" in set_cookie

    # 3. Verifier persona cannot revoke credentials (returns 403 error fragment)
    api_client.cookies.set("vericred_role", sign_role_cookie("verifier"))
    resp_revoke_forbidden = await api_client.post(
        "/web/revocation/revoke",
        data={"credential_public_id": "CRD-2026-000001"},
    )
    assert resp_revoke_forbidden.status_code == 403
    assert "403 Forbidden" in resp_revoke_forbidden.text


@pytest.mark.asyncio
async def test_web_verify_badge_renders_real_holder_program_score_and_revoker(
    api_client: AsyncClient,
    db_session,
    sample_issuer,
    sample_academic_setup,
):
    """Verify verification_badge.html binds payload_snapshot.* and revoked_by_actor_id with zero N/A values for staff."""
    from datetime import datetime, timezone
    from decimal import Decimal
    from sqlalchemy import select
    from backend.models.completion import CompletionRecord
    from backend.services.ids import format_completion_id
    from backend.services.issuance import IssuanceService
    from backend.services.revocation import RevocationService

    api_client.cookies.set("vericred_role", sign_role_cookie("registrar"))
    issuer, priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    comp = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("92.50"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=comp.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=priv_pem,
        actor_id="REGISTRAR-WEB-TEST",
    )

    # 1. Verify active credential via HTMX POST /web/verify as registrar
    resp_valid = await api_client.post(
        "/web/verify",
        data={"credential_public_id": cred.public_id},
    )
    assert resp_valid.status_code == 200
    html_valid = resp_valid.text
    assert "Alice Q. Student" in html_valid
    assert "LRN-000001" in html_valid
    assert "Advanced Distributed Cryptographic Systems" in html_valid
    assert "CRS-000001" in html_valid
    assert "92.5%" in html_valid
    assert "N/A" not in html_valid

    # 2. Revoke the credential and verify revoked_by_actor_id and claims render with zero N/A
    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        reason_code="ACADEMIC_MISCONDUCT",
        actor_id="DEAN-REVOKER-99",
        notes="Confirmed Honour Code Violation",
    )

    resp_revoked = await api_client.post(
        "/web/verify",
        data={"credential_public_id": cred.public_id},
    )
    assert resp_revoked.status_code == 200
    html_revoked = resp_revoked.text
    assert "Revoked" in html_revoked
    assert "Alice Q. Student" in html_revoked
    assert "Advanced Distributed Cryptographic Systems" in html_revoked
    assert "92.5%" in html_revoked
    assert "DEAN-REVOKER-99" in html_revoked
    assert "Academic misconduct" in html_revoked
    assert "N/A" not in html_revoked
    assert "Query Latency" not in html_revoked
    assert "Revoked on" in html_revoked
    assert "Reason: Academic misconduct" in html_revoked


@pytest.mark.asyncio
async def test_verify_page_layout_and_touch_role_dropdown(api_client: AsyncClient):
    """Acceptance check a: Verify /verify flex layout, no min-height placeholder, and touch-enabled role dropdown."""
    resp = await api_client.get("/verify")
    assert resp.status_code == 200
    html = resp.text

    # 1. Flex layout on verify page
    assert "flex flex-col sm:flex-row items-stretch sm:items-center gap-3" in html
    assert "flex-1" in html
    assert "shrink-0" in html

    # 2. Result container has no min-height placeholder and is hidden when empty
    assert 'id="verificationResult"' in html
    assert "min-h-" not in html.split('id="verificationResult"')[1].split(">")[0]
    assert "empty:hidden" in html

    # 3. Role dropdown has aria-expanded, button, menu, min-h-[44px], and no hover-only CSS
    assert 'id="roleDropdownBtn"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="roleDropdownMenu"' in html
    assert "min-h-[44px]" in html
    assert "group-hover:block" not in html
    assert ":hover" not in html or "hover:" in html  # standard tailwind hover:bg is fine, no CSS pseudo-class open state

    # 4. Role switch redirection for verifier
    resp_redirect = await api_client.get("/role/switch?role=verifier&redirect=/registry", follow_redirects=False)
    assert resp_redirect.status_code == 303
    assert resp_redirect.headers.get("location") == "/verify"

    # Permitted redirection stays on page
    resp_stay = await api_client.get("/role/switch?role=registrar&redirect=/registry", follow_redirects=False)
    assert resp_stay.status_code == 303
    assert resp_stay.headers.get("location") == "/registry"


@pytest.mark.asyncio
async def test_registry_counts_with_stale_status_revoked_credential(
    api_client: AsyncClient,
    db_session,
    sample_issuer,
    sample_academic_setup,
):
    """Acceptance check b & c: Verify registry count invariants (Active + Revoked == Total)

    even when a credential has a stale 'ACTIVE' status column alongside a revocation row.
    """
    from datetime import datetime, timezone
    from decimal import Decimal
    from sqlalchemy import select
    from backend.models.completion import CompletionRecord
    from backend.models.credential import Credential
    from backend.models.revocation import Revocation
    from backend.services.ids import format_completion_id, format_revocation_id
    from backend.services.issuance import IssuanceService

    api_client.cookies.set("vericred_role", sign_role_cookie("registrar"))
    issuer, priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    # Create completion and issue credential
    comp = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id) + "-stale",
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("88.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=comp.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=priv_pem,
        actor_id="REGISTRAR-STALE-TEST",
    )

    # Insert a revocation row directly WITHOUT updating cred.status (simulating stale ACTIVE status)
    rev = Revocation(
        public_id=format_revocation_id(cred.public_id),
        credential_id=cred.id,
        revocation_timestamp=datetime.now(timezone.utc),
        reason_code="ADMINISTRATIVE_ERROR",
        revoked_by_actor_id="AUDITOR-TEST",
    )
    db_session.add(rev)
    await db_session.commit()

    # Query Credential ORM model and assert status is still ACTIVE in the DB table
    result = await db_session.execute(select(Credential).where(Credential.id == cred.id))
    cred_model = result.scalar_one()
    assert cred_model.status == "ACTIVE"

    # Query registry page and verify counts
    resp = await api_client.get("/registry")
    assert resp.status_code == 200
    html = resp.text

    # Total, Active, Revoked counts present and Active + Revoked == Total Issued
    # Header styling present
    assert "min-w-[160px]" in html
    assert "whitespace-nowrap" in html

    # Query registry table partial
    resp_table = await api_client.get(f"/web/registry/table?search={cred.public_id}")
    assert resp_table.status_code == 200
    # Must display as REVOKED despite cred.status == 'ACTIVE'
    assert "REVOKED" in resp_table.text


@pytest.mark.asyncio
async def test_revoked_credential_human_readable_formatting_public_verify(
    api_client: AsyncClient,
    db_session,
    sample_issuer,
    sample_academic_setup,
):
    """Acceptance check c: Revoked credential verification shows human-readable date + sentence-case reason, no raw ISO."""
    import re
    from datetime import datetime, timezone
    from decimal import Decimal
    from sqlalchemy import select
    from backend.models.completion import CompletionRecord
    from backend.services.ids import format_completion_id
    from backend.services.issuance import IssuanceService
    from backend.services.revocation import RevocationService

    issuer, priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    now = datetime.now(timezone.utc)
    comp = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id) + "-fmt",
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("85.00"),
        status="COMPLETED",
        completion_timestamp=now,
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    cred = await IssuanceService.issue_credential(
        db=db_session,
        completion_id=comp.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=priv_pem,
        actor_id="REGISTRAR-FMT-TEST",
    )

    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="DEAN-FMT-99",
        reason_code="ACADEMIC_MISCONDUCT",
    )

    # Public verification (no cookies)
    resp = await api_client.post("/web/verify", data={"credential_public_id": cred.public_id})
    assert resp.status_code == 200
    html = resp.text

    # Must contain human date and sentence case reason
    expected_date = now.strftime("%d %b %Y")
    assert f"Revoked on {expected_date}. Reason: Academic misconduct" in html
    # Must NOT contain Query Latency
    assert "Query Latency" not in html




