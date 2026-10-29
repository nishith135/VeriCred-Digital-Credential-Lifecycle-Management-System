"""Comprehensive tests for server-side RBAC, signed cookies, PII redaction, and rate limiting.

Covers Acceptance Checks (a) through (g):
a. Parametrized permission matrix across all 22 route/method endpoints x {verifier, auditor, registrar}.
b. Cookie tamper test + ?role= query-parameter ignore test + open-redirect protection on /role/switch.
c. POST /api/v1/revocation/revoke role enforcement (403/403/200) and server-enforced actor_id traceability.
d. Public verifier JSON and HTML badge PII redaction vs. full registrar response for active and revoked credentials.
e. Sidebar navigation links per role and removal of sidebar footer Persona link.
f. Sliding-window rate limiter (31st request within a minute returns 429 with Retry-After).
g. /registry as verifier -> 403 page; /registry as auditor -> 200 with zero Revoke buttons.
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
import re
from typing import Any

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.rate_limit import verify_rate_limiter
from backend.core.rbac import sign_role_cookie
from backend.models.audit import AuditEvent
from backend.models.completion import CompletionRecord
from backend.models.revocation import Revocation
from backend.services.ids import format_completion_id
from backend.services.issuance import IssuanceService
from backend.services.revocation import RevocationService


def _apply_role(client: AsyncClient, role: str, use_bearer_for_api: bool = False) -> dict[str, str]:
    """Configure client cookie or Bearer header for the given role."""
    client.cookies.clear()
    if use_bearer_for_api:
        if role == "registrar":
            return {"Authorization": f"Bearer {settings.REGISTRAR_API_KEY}"}
        if role == "auditor":
            return {"Authorization": f"Bearer {settings.AUDITOR_API_KEY}"}
        return {}
    if role in ("registrar", "auditor", "verifier"):
        client.cookies.set("vericred_role", sign_role_cookie(role))
    return {}


ROUTE_MATRIX_CASES = [
    # Public routes (any role allowed)
    ("GET", "/", {"verifier": 200, "auditor": 200, "registrar": 200}),
    ("GET", "/verify", {"verifier": 200, "auditor": 200, "registrar": 200}),
    ("GET", "/login", {"verifier": 200, "auditor": 200, "registrar": 200}),
    ("GET", "/health", {"verifier": 200, "auditor": 200, "registrar": 200}),
    ("POST", "/web/verify", {"verifier": 200, "auditor": 200, "registrar": 200}),
    ("POST", "/api/v1/verification/verify", {"verifier": 200, "auditor": 200, "registrar": 200}),
    ("GET", "/role/switch", {"verifier": 303, "auditor": 303, "registrar": 303}),
    ("POST", "/role/switch", {"verifier": 303, "auditor": 303, "registrar": 303}),
    # Staff read routes (registrar + auditor)
    ("GET", "/registry", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/web/registry/table", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/audit", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/web/audit/table", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/web/export/audit", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/anomalies", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("POST", "/web/anomalies/run/SIM-REV-094", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("POST", "/web/anomalies/run-all", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/api/v1/audit/events", {"verifier": 403, "auditor": 200, "registrar": 200}),
    ("GET", "/api/v1/revocation/audit/{id}", {"verifier": 403, "auditor": 200, "registrar": 200}),
    # Registrar-only mutation routes
    ("POST", "/api/v1/issuance/evaluate", {"verifier": 403, "auditor": 403, "registrar": 200}),
    ("POST", "/api/v1/issuance/issue", {"verifier": 403, "auditor": 403, "registrar": 201}),
    ("POST", "/api/v1/revocation/revoke", {"verifier": 403, "auditor": 403, "registrar": 200}),
    ("POST", "/web/revocation/revoke", {"verifier": 403, "auditor": 403, "registrar": 200}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,route_template,expected_map",
    ROUTE_MATRIX_CASES,
    ids=[f"{m} {r}" for m, r, _ in ROUTE_MATRIX_CASES],
)
@pytest.mark.parametrize("role", ["verifier", "auditor", "registrar"])
async def test_permission_matrix_every_route_by_role(
    api_client: AsyncClient,
    db_session: AsyncSession,
    sample_issuer,
    sample_academic_setup,
    method: str,
    route_template: str,
    expected_map: dict[str, int],
    role: str,
):
    """Acceptance Check (a): Verify every route x {verifier, auditor, registrar} matches expected status code."""
    issuer, priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    # Seed an unissued completion (for issuance) and an active credential (for revocation/verification)
    comp_unissued = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("91.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(comp_unissued)
    await db_session.commit()
    await db_session.refresh(comp_unissued)

    cred_public_id = "CRD-2026-000001"
    if route_template in (
        "/api/v1/revocation/revoke",
        "/web/revocation/revoke",
        "/api/v1/revocation/audit/{id}",
    ):
        issued = await IssuanceService.issue_credential(
            db=db_session,
            completion_id=comp_unissued.id,
            issuer_public_id=issuer.public_id,
            issuer_private_key_pem=priv_pem,
            actor_id="SETUP-REGISTRAR",
        )
        cred_public_id = issued.public_id

    url = route_template.replace("{id}", cred_public_id)
    is_api = url.startswith("/api/")
    headers = _apply_role(api_client, role, use_bearer_for_api=is_api)

    if route_template == "/role/switch":
        resp = await api_client.request(
            method, f"{url}?role={role}&redirect=/verify", headers=headers, follow_redirects=False
        )
    elif route_template == "/web/verify":
        resp = await api_client.post(
            url, data={"credential_public_id": cred_public_id}, headers=headers
        )
    elif route_template == "/api/v1/verification/verify":
        resp = await api_client.post(
            url, json={"credential_public_id": cred_public_id}, headers=headers
        )
    elif route_template == "/api/v1/issuance/evaluate":
        resp = await api_client.post(
            url, json={"completion_id": comp_unissued.id}, headers=headers
        )
    elif route_template == "/api/v1/issuance/issue":
        resp = await api_client.post(
            url,
            json={
                "completion_id": comp_unissued.id,
                "issuer_public_id": issuer.public_id,
            },
            headers={**headers, "X-Issuer-Private-Key": priv_pem},
        )
    elif route_template == "/api/v1/revocation/revoke":
        resp = await api_client.post(
            url,
            json={
                "credential_public_id": cred_public_id,
                "actor_id": "IGNORED-CLIENT-ACTOR",
                "reason_code": "ACADEMIC_MISCONDUCT",
            },
            headers=headers,
        )
    elif route_template == "/web/revocation/revoke":
        resp = await api_client.post(
            url,
            data={
                "credential_public_id": cred_public_id,
                "reason_code": "ACADEMIC_MISCONDUCT",
            },
            headers=headers,
        )
    else:
        resp = await api_client.request(method, url, headers=headers)

    expected_status = expected_map[role]
    print(
        f"MATRIX_ROW | {method:4s} {route_template:36s} | role={role:9s} | expected={expected_status} | actual={resp.status_code}"
    )
    assert resp.status_code == expected_status, (
        f"{method} {route_template} as {role}: expected {expected_status}, got {resp.status_code} ({resp.text[:200]})"
    )

    if expected_status == 403 and is_api:
        body = resp.json()
        assert body["error"] == "FORBIDDEN"
        assert body["current_role"] == role
        assert isinstance(body["required_roles"], list)


@pytest.mark.asyncio
async def test_invalid_bearer_api_key_returns_401(api_client: AsyncClient):
    """Verify that presenting an invalid Bearer token returns 401 Unauthorized."""
    resp = await api_client.get(
        "/api/v1/audit/events",
        headers={"Authorization": "Bearer invalid-forged-token-999"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_cookie_tamper_and_query_param_resolve_to_verifier(api_client: AsyncClient):
    """Acceptance Check (b): Hand-edited cookie and ?role= parameter both resolve to verifier."""
    # 1. Unsigned raw role cookie 'registrar' -> resolves to verifier -> 403 on /registry
    api_client.cookies.set("vericred_role", "registrar")
    resp_unsigned = await api_client.get("/registry")
    assert resp_unsigned.status_code == 403

    # 2. Tampered signature cookie 'registrar.<forged_sig>' -> resolves to verifier -> 403 on /registry
    valid_signed = sign_role_cookie("verifier")
    sig_part = valid_signed.split(".", 1)[1]
    api_client.cookies.set("vericred_role", f"registrar.{sig_part}")
    resp_tampered = await api_client.get("/registry")
    assert resp_tampered.status_code == 403

    # 3. ?role=registrar query parameter is ignored completely -> 403 on /registry, 'Public Verifier' on /verify
    api_client.cookies.clear()
    resp_query_reg = await api_client.get("/registry?role=registrar")
    assert resp_query_reg.status_code == 403

    resp_verify_page = await api_client.get("/verify?role=registrar")
    assert resp_verify_page.status_code == 200
    assert 'Role: <strong class="text-white">Public Verifier</strong>' in resp_verify_page.text

    # 4. /role/switch ignores Referer and blocks external redirect URLs
    resp_switch = await api_client.get(
        "/role/switch?role=registrar&redirect=https://evil.example/phish",
        headers={"Referer": "https://evil.example/referer"},
        follow_redirects=False,
    )
    assert resp_switch.status_code == 303
    assert resp_switch.headers["location"] == "/verify"


@pytest.mark.asyncio
async def test_api_revocation_role_enforcement_and_actor_traceability(
    api_client: AsyncClient,
    db_session: AsyncSession,
    sample_issuer,
    sample_academic_setup,
):
    """Acceptance Check (c): POST /api/v1/revocation/revoke as verifier -> 403, auditor -> 403,
    registrar -> 200 and both Revocation row and AuditEvent carry REGISTRAR-001.
    """
    issuer, priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    comp = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("89.00"),
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
        actor_id="REGISTRAR-001",
    )

    payload = {
        "credential_public_id": cred.public_id,
        "actor_id": "CLIENT-SPOOFED-ACTOR-ID",
        "reason_code": "ACADEMIC_MISCONDUCT",
        "notes": "Verified misconduct finding.",
    }

    # 1. Verifier (no credentials) -> 403
    r_verifier = await api_client.post("/api/v1/revocation/revoke", json=payload)
    assert r_verifier.status_code == 403
    assert r_verifier.json()["current_role"] == "verifier"

    # 2. Auditor -> 403
    r_auditor = await api_client.post(
        "/api/v1/revocation/revoke",
        json=payload,
        headers={"Authorization": f"Bearer {settings.AUDITOR_API_KEY}"},
    )
    assert r_auditor.status_code == 403
    assert r_auditor.json()["current_role"] == "auditor"

    # 3. Registrar -> 200
    r_registrar = await api_client.post(
        "/api/v1/revocation/revoke",
        json=payload,
        headers={"Authorization": f"Bearer {settings.REGISTRAR_API_KEY}"},
    )
    assert r_registrar.status_code == 200
    rev_json = r_registrar.json()
    assert rev_json["revoked_by_actor_id"] == "REGISTRAR-001"

    # Verify DB Revocation row and AuditEvent row both store REGISTRAR-001
    rev_row = (
        await db_session.execute(
            select(Revocation).where(Revocation.credential_id == cred.id)
        )
    ).scalar_one()
    assert rev_row.revoked_by_actor_id == "REGISTRAR-001"

    audit_row = (
        await db_session.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "CREDENTIAL_REVOKED",
                AuditEvent.target_entity_id == cred.public_id,
            )
        )
    ).scalar_one()
    assert audit_row.actor_id == "REGISTRAR-001"


@pytest.mark.asyncio
async def test_public_verifier_redaction_vs_registrar_full_response(
    api_client: AsyncClient,
    db_session: AsyncSession,
    sample_issuer,
    sample_academic_setup,
):
    """Acceptance Check (d): Verifier JSON and HTML badge for active AND revoked credentials
    contain none of the forbidden PII/internal fields, whereas Registrar receives full details.
    """
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
        actor_id="REGISTRAR-001",
    )

    forbidden_substrings = [
        learner.full_name,        # "Alice Q. Student"
        learner.email,            # "alice.0001@university.edu"
        learner.public_id,        # "LRN-000001"
        "92.5",                   # assessment score
        "REGISTRAR-001",          # actor_id
        "payload_snapshot",       # raw snapshot key
        "issuer_signature",       # signature field
        cred.issuer_signature[:16],
        "revoked_by_actor_id",
        "PUBLIC-VERIFIER",
    ]

    # --- 1. ACTIVE CREDENTIAL AS PUBLIC VERIFIER (JSON + HTML) ---
    api_client.cookies.clear()
    resp_pub_active = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": cred.public_id},
    )
    assert resp_pub_active.status_code == 200
    raw_pub_active_json = resp_pub_active.text
    pub_active_data = resp_pub_active.json()

    assert set(pub_active_data.keys()) == {
        "credential_public_id",
        "outcome",
        "issuer_name",
        "course_title",
        "issued_at",
        "holder_masked",
        "factors",
    }
    assert pub_active_data["holder_masked"] == "A**** Q**** S****"
    assert pub_active_data["factors"]["payload_hash_matches"] is True
    assert pub_active_data["factors"]["eligibility_valid"] is True

    for forbidden in forbidden_substrings:
        assert forbidden not in raw_pub_active_json, f"Forbidden value '{forbidden}' leaked in active verifier JSON!"

    resp_badge_active = await api_client.post(
        "/web/verify",
        data={"credential_public_id": cred.public_id},
    )
    assert resp_badge_active.status_code == 200
    badge_active_html = resp_badge_active.text
    assert "A**** Q**** S****" in badge_active_html
    assert course.title in badge_active_html
    assert issuer.name in badge_active_html
    for forbidden in forbidden_substrings:
        assert forbidden not in badge_active_html, f"Forbidden value '{forbidden}' leaked in active verifier HTML badge!"

    # --- 2. ACTIVE CREDENTIAL AS REGISTRAR (JSON + HTML) ---
    reg_headers = {"Authorization": f"Bearer {settings.REGISTRAR_API_KEY}"}
    resp_reg_active = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": cred.public_id},
        headers=reg_headers,
    )
    assert resp_reg_active.status_code == 200
    reg_data = resp_reg_active.json()
    assert reg_data["credential_details"]["payload_snapshot"]["learner"]["name"] == "Alice Q. Student"
    assert reg_data["credential_details"]["payload_snapshot"]["assessment"]["score"] == 92.5

    # --- 3. REVOKED CREDENTIAL AS PUBLIC VERIFIER (JSON + HTML) ---
    await RevocationService.revoke_credential(
        db=db_session,
        credential_public_id=cred.public_id,
        actor_id="REGISTRAR-001",
        reason_code="ACADEMIC_MISCONDUCT",
        notes="Internal confidential disciplinary note.",
    )

    api_client.cookies.clear()
    resp_pub_revoked = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": cred.public_id},
    )
    assert resp_pub_revoked.status_code == 200
    raw_pub_revoked_json = resp_pub_revoked.text
    pub_revoked_data = resp_pub_revoked.json()

    assert set(pub_revoked_data.keys()) == {
        "credential_public_id",
        "outcome",
        "issuer_name",
        "course_title",
        "issued_at",
        "holder_masked",
        "factors",
        "revoked_at",
        "reason_code",
    }
    assert pub_revoked_data["outcome"] == "REVOKED"
    assert pub_revoked_data["reason_code"] == "ACADEMIC_MISCONDUCT"
    assert pub_revoked_data["revoked_at"] is not None
    assert "Internal confidential disciplinary note" not in raw_pub_revoked_json
    for forbidden in forbidden_substrings:
        assert forbidden not in raw_pub_revoked_json, f"Forbidden value '{forbidden}' leaked in revoked verifier JSON!"

    resp_badge_revoked = await api_client.post(
        "/web/verify",
        data={"credential_public_id": cred.public_id},
    )
    assert resp_badge_revoked.status_code == 200
    badge_revoked_html = resp_badge_revoked.text
    assert "A**** Q**** S****" in badge_revoked_html
    assert "ACADEMIC_MISCONDUCT" in badge_revoked_html
    assert "Internal confidential disciplinary note" not in badge_revoked_html
    for forbidden in forbidden_substrings:
        assert forbidden not in badge_revoked_html, f"Forbidden value '{forbidden}' leaked in revoked verifier HTML badge!"


def _extract_sidebar_links(html: str) -> list[str]:
    """Extract href values inside <nav ... id="sidebarNav">...</nav>."""
    match = re.search(r'<nav[^>]*id="sidebarNav"[^>]*>(.*?)</nav>', html, re.DOTALL)
    assert match is not None, "sidebarNav not found in HTML"
    return re.findall(r'href="([^"]+)"', match.group(1))


@pytest.mark.asyncio
async def test_sidebar_navigation_links_by_role(api_client: AsyncClient):
    """Acceptance Check (e): Sidebar HTML per role lists exactly the expected links."""
    # 1. Verifier (default)
    api_client.cookies.clear()
    resp_ver = await api_client.get("/verify")
    assert resp_ver.status_code == 200
    assert _extract_sidebar_links(resp_ver.text) == ["/verify"]
    assert 'Role: <strong class="text-white">Public Verifier</strong>' in resp_ver.text
    assert "swap_horiz" not in resp_ver.text  # Sidebar footer Persona link removed
    assert "Login / Auth Page" in resp_ver.text

    # 2. Auditor
    api_client.cookies.set("vericred_role", sign_role_cookie("auditor"))
    resp_aud = await api_client.get("/verify")
    assert resp_aud.status_code == 200
    assert _extract_sidebar_links(resp_aud.text) == ["/verify", "/registry", "/audit", "/anomalies"]
    assert 'Role: <strong class="text-white">Compliance Auditor</strong>' in resp_aud.text

    # 3. Registrar
    api_client.cookies.set("vericred_role", sign_role_cookie("registrar"))
    resp_reg = await api_client.get("/verify")
    assert resp_reg.status_code == 200
    assert _extract_sidebar_links(resp_reg.text) == ["/verify", "/registry", "/audit", "/anomalies"]
    assert 'Role: <strong class="text-white">University Registrar</strong>' in resp_reg.text


@pytest.mark.asyncio
async def test_verification_rate_limiter_returns_429_with_retry_after(api_client: AsyncClient):
    """Acceptance Check (f): Rate limiter returns 429 with Retry-After when limit is exceeded
    (tested both with overridden low limit and with 30 req/min default on 31st request).
    """
    # Part 1: Low overridden limit (3 requests/min -> 4th returns 429)
    verify_rate_limiter.set_limit(3, window_seconds=60)
    for _ in range(3):
        r_ok = await api_client.post(
            "/api/v1/verification/verify",
            json={"credential_public_id": "CRD-2026-999999"},
        )
        assert r_ok.status_code == 200

    r_limited = await api_client.post(
        "/api/v1/verification/verify",
        json={"credential_public_id": "CRD-2026-999999"},
    )
    assert r_limited.status_code == 429
    assert "Retry-After" in r_limited.headers
    assert int(r_limited.headers["Retry-After"]) >= 1

    # Part 2: Default 30 requests/minute -> 31st request returns 429 on POST /web/verify
    verify_rate_limiter.set_limit(30, window_seconds=60)
    for i in range(30):
        r_web_ok = await api_client.post(
            "/web/verify",
            data={"credential_public_id": "CRD-2026-999999"},
        )
        assert r_web_ok.status_code == 200, f"Request {i + 1} failed unexpectedly"

    r_31st = await api_client.post(
        "/web/verify",
        data={"credential_public_id": "CRD-2026-999999"},
    )
    assert r_31st.status_code == 429
    assert "Retry-After" in r_31st.headers


@pytest.mark.asyncio
async def test_registry_forbidden_for_verifier_and_hides_revoke_for_auditor(
    api_client: AsyncClient,
    db_session: AsyncSession,
    sample_issuer,
    sample_academic_setup,
):
    """Acceptance Check (g): /registry as verifier returns 403, /registry as auditor shows no Revoke buttons."""
    issuer, priv_pem = sample_issuer
    course, learner, rule = sample_academic_setup

    comp = CompletionRecord(
        public_id=format_completion_id(learner.public_id, course.public_id),
        learner_id=learner.id,
        course_id=course.id,
        rule_id=rule.id,
        assessment_score=Decimal("90.00"),
        status="COMPLETED",
        completion_timestamp=datetime.now(timezone.utc),
    )
    db_session.add(comp)
    await db_session.commit()
    await db_session.refresh(comp)

    await IssuanceService.issue_credential(
        db=db_session,
        completion_id=comp.id,
        issuer_public_id=issuer.public_id,
        issuer_private_key_pem=priv_pem,
        actor_id="REGISTRAR-001",
    )

    # 1. Verifier -> 403 friendly page with link to switch persona
    api_client.cookies.clear()
    resp_ver = await api_client.get("/registry")
    assert resp_ver.status_code == 403
    assert "Access Restricted for Current Persona" in resp_ver.text
    assert 'href="/login"' in resp_ver.text

    # 2. Auditor -> 200 with zero Revoke buttons or modal
    api_client.cookies.set("vericred_role", sign_role_cookie("auditor"))
    resp_aud = await api_client.get("/registry")
    assert resp_aud.status_code == 200
    assert "openRevokeModal" not in resp_aud.text
    assert "revocationModal" not in resp_aud.text
    assert "Eligibility Invariants" not in resp_aud.text
    assert ">Revoke<" not in resp_aud.text

    # 3. Registrar -> 200 with Revoke button and modal present
    api_client.cookies.set("vericred_role", sign_role_cookie("registrar"))
    resp_reg = await api_client.get("/registry")
    assert resp_reg.status_code == 200
    assert "openRevokeModal" in resp_reg.text
    assert "revocationModal" in resp_reg.text

