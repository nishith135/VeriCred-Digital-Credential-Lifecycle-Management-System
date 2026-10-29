"""Integration tests for VeriCred Web UI and HTMX endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_web_verify_pages_load(api_client: AsyncClient):
    """Verify that public verification views render cleanly."""
    # GET /
    resp_root = await api_client.get("/")
    assert resp_root.status_code == 200
    assert "Public Credential Verification" in resp_root.text

    # GET /verify
    resp_verify = await api_client.get("/verify")
    assert resp_verify.status_code == 200
    assert "Public Credential Verification" in resp_verify.text


@pytest.mark.asyncio
async def test_web_verify_htmx_post(api_client: AsyncClient):
    """Verify that HTMX POST /web/verify returns formatted verification badge."""
    resp = await api_client.post(
        "/web/verify",
        data={"credential_public_id": "CRD-2026-999999"},
    )
    assert resp.status_code == 200
    assert "NOT_FOUND" in resp.text
    assert "Audit ID:" in resp.text
    assert "Security Consensus Checklist" in resp.text


@pytest.mark.asyncio
async def test_web_registry_pages_load(api_client: AsyncClient):
    """Verify that Credential Registry views render cleanly."""
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
    """Verify that Audit Ledger views and export endpoints operate cleanly."""
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
    """Verify that Anomaly Stress-Test Lab renders and executes all scenarios."""
    # GET /anomalies
    resp = await api_client.get("/anomalies")
    assert resp.status_code == 200
    assert "Anomaly Stress-Test Lab" in resp.text
    assert "SIM-REV-094" in resp.text
    assert "SIM-TAMP-882" in resp.text

    # POST /web/anomalies/run-all
    resp_run = await api_client.post("/web/anomalies/run-all")
    assert resp_run.status_code == 200
    assert "TEST PASSED" in resp_run.text
    assert "SIM-COLL-103" in resp_run.text
    assert "SIM-POIS-519" in resp_run.text

    # POST /web/anomalies/run/SIM-TAMP-882
    resp_single = await api_client.post("/web/anomalies/run/SIM-TAMP-882")
    assert resp_single.status_code == 200
    assert "Scenario 04: Altered Payload Hash Mismatch" in resp_single.text
    assert "TAMPERED" in resp_single.text


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

    # 2. Role switch sets cookie
    resp_switch = await api_client.get("/role/switch?role=verifier&redirect=/verify", follow_redirects=False)
    assert resp_switch.status_code == 303
    assert "vericred_role=verifier" in resp_switch.headers.get("set-cookie", "")

    # 3. Verifier persona cannot revoke credentials
    resp_revoke_forbidden = await api_client.post(
        "/web/revocation/revoke",
        data={"credential_public_id": "CRD-2026-000001"},
        cookies={"vericred_role": "verifier"},
    )
    assert resp_revoke_forbidden.status_code == 200
    assert "Access Denied" in resp_revoke_forbidden.headers.get("hx-trigger", "")


@pytest.mark.asyncio
async def test_web_verify_badge_renders_real_holder_program_score_and_revoker(
    api_client: AsyncClient,
    db_session,
    sample_issuer,
    sample_academic_setup,
):
    """Verify verification_badge.html binds payload_snapshot.* and revoked_by_actor_id with zero N/A values."""
    from datetime import datetime, timezone
    from decimal import Decimal
    from backend.models.completion import CompletionRecord
    from backend.services.ids import format_completion_id
    from backend.services.issuance import IssuanceService
    from backend.services.revocation import RevocationService

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

    # 1. Verify active credential via HTMX POST /web/verify
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
    assert "REVOKED" in html_revoked
    assert "Alice Q. Student" in html_revoked
    assert "Advanced Distributed Cryptographic Systems" in html_revoked
    assert "92.5%" in html_revoked
    assert "DEAN-REVOKER-99" in html_revoked
    assert "ACADEMIC_MISCONDUCT" in html_revoked
    assert "N/A" not in html_revoked

