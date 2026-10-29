"""Web Interface Router for VeriCred.

Serves Jinja2 templates and HTMX partials for:
1. Public Verification Portal (/ & /verify)
2. Credential Registry & Pre-Issuance (/registry)
3. Immutable Audit Ledger (/audit)
4. Cryptographic Anomaly Stress-Test Lab (/anomalies)
"""

import csv
import io
import json
import math
from pathlib import Path
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db_session
from backend.core.rate_limit import verify_rate_limiter
from backend.core.rbac import (
    ROLE_DEFINITIONS,
    Role,
    get_current_actor,
    get_role_context,
    require_role,
    sign_role_cookie,
    validate_relative_redirect,
)
from backend.evaluation import (
    ANOMALY_SCENARIO_META,
    EvaluationRunner,
    get_latest_evaluation_report,
)
from backend.models import (
    AuditEvent,
    CompletionRecord,
    Course,
    Credential,
    Issuer,
    Learner,
    Revocation,
    VerificationRequest,
)
from backend.services.revocation import RevocationService
from backend.services.verification import VerificationService

router = APIRouter(tags=["Web UI"])
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
DEFAULT_PAGE_SIZE = 50


def render_template(
    request: Request,
    name: str,
    context: Optional[Dict[str, Any]] = None,
    actor: Optional[Dict[str, str]] = None,
) -> Response:
    """Helper to render Jinja templates populated with global RBAC role context."""
    ctx = get_role_context(request, actor=actor)
    if context:
        ctx.update(context)
    return templates.TemplateResponse(request=request, name=name, context=ctx)


# =============================================================================
# Auth & Persona Switching (RBAC)
# =============================================================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    actor: Dict[str, str] = Depends(get_current_actor),
):
    """Render the login and persona switcher page."""
    return render_template(
        request=request,
        name="pages/login.html",
        context={"active_page": "login"},
        actor=actor,
    )


@router.get("/role/switch")
@router.post("/role/switch")
async def switch_role(
    role: str = Query(...),
    redirect: Optional[str] = Query(None),
    _actor: Dict[str, str] = Depends(get_current_actor),
):
    """Switch active persona role via HMAC-signed session cookie."""
    if role not in ROLE_DEFINITIONS:
        role = Role.VERIFIER.value
    target_url = validate_relative_redirect(redirect, default="/verify")
    signed_cookie = sign_role_cookie(role)
    response = RedirectResponse(url=target_url, status_code=303)
    response.set_cookie(
        key="vericred_role",
        value=signed_cookie,
        max_age=3600 * 24 * 7,
        httponly=True,
        samesite="lax",
    )
    return response


# =============================================================================
# 1. Public Verification Portal
# =============================================================================

@router.get("/", response_class=HTMLResponse)
@router.get("/verify", response_class=HTMLResponse)
async def verify_page(
    request: Request,
    id: Optional[str] = Query(None),
    actor: Dict[str, str] = Depends(get_current_actor),
):
    """Render the public verification portal."""
    return render_template(
        request=request,
        name="pages/verify.html",
        context={
            "active_page": "verify",
            "sample_valid_id": id or "",
        },
        actor=actor,
    )


@router.post("/web/verify", response_class=HTMLResponse)
async def perform_verification_htmx(
    request: Request,
    credential_public_id: str = Form(...),
    tamper_payload: Optional[str] = Form(None),
    actor: Dict[str, str] = Depends(get_current_actor),
    _rate_limit: None = Depends(verify_rate_limiter),
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX endpoint to perform 4 verification checks on a credential."""
    start_time = time.perf_counter()
    credential_id = credential_public_id.strip()

    # Parse custom payload if provided by the Anomaly Lab tamper inspector
    presented_payload = None
    if tamper_payload and tamper_payload.strip():
        try:
            presented_payload = json.loads(tamper_payload.strip())
        except Exception:
            presented_payload = {"raw_tampered_input": tamper_payload.strip()}

    staff_resp = await VerificationService.verify_credential(
        db=db,
        credential_public_id=credential_id,
        presented_payload=presented_payload,
        requester_ip=request.client.host if request.client else "127.0.0.1",
        actor_id=actor["actor_id"],
    )
    role_resp = VerificationService.select_response_for_role(staff_resp, actor["role"])

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return render_template(
        request=request,
        name="partials/verification_badge.html",
        context={
            "result": role_resp,
            "is_public_view": actor["role"] == Role.VERIFIER.value,
            "latency_ms": f"{elapsed_ms:.1f}",
        },
        actor=actor,
    )


# =============================================================================
# 2. Credential Registry (Server-Side Pagination, Page Size = 50)
# =============================================================================

@router.get("/registry", response_class=HTMLResponse)
async def registry_page(
    request: Request,
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None),
    status: str = Query("ALL"),
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """Render the credential registry management page with server-side pagination."""
    total_issued = (
        await db.execute(select(func.count(Credential.id)))
    ).scalar_one() or 0

    total_active = (
        await db.execute(
            select(func.count(Credential.id)).where(Credential.status == "ACTIVE")
        )
    ).scalar_one() or 0

    total_revoked = (
        await db.execute(select(func.count(Revocation.id)))
    ).scalar_one() or 0

    unique_learners = (
        await db.execute(
            select(func.count(distinct(CompletionRecord.learner_id)))
            .join(Credential, CompletionRecord.id == Credential.completion_id)
        )
    ).scalar_one() or 0

    verifications_count = (
        await db.execute(select(func.count(VerificationRequest.id)))
    ).scalar_one() or 0

    metrics = {
        "total_issued": total_issued,
        "total_active": total_active,
        "active_count": total_active,
        "total_revoked": total_revoked,
        "revoked_count": total_revoked,
        "unique_learners": unique_learners,
        "verifications_count": verifications_count,
    }

    offset = (page - 1) * DEFAULT_PAGE_SIZE
    credentials, total_count = await _query_credentials(
        db,
        search=search,
        status=status,
        limit=DEFAULT_PAGE_SIZE,
        offset=offset,
    )
    total_pages = max(1, math.ceil(total_count / DEFAULT_PAGE_SIZE))

    # Fetch unissued eligible candidates for pre-issuance deck
    cand_stmt = (
        select(CompletionRecord, Learner, Course)
        .join(Learner, CompletionRecord.learner_id == Learner.id)
        .join(Course, CompletionRecord.course_id == Course.id)
        .outerjoin(Credential, Credential.completion_id == CompletionRecord.id)
        .where(
            Credential.id.is_(None),
            CompletionRecord.status == "COMPLETED",
            CompletionRecord.assessment_score >= 80.0,
        )
        .limit(10)
    )
    cand_rows = (await db.execute(cand_stmt)).all()
    candidates = []
    for comp, lnr, crs in cand_rows:
        candidates.append({
            "id": comp.id,
            "learner_id": comp.learner_id,
            "learner_name": lnr.full_name,
            "learner_public_id": lnr.public_id,
            "course_title": crs.title,
            "course_public_id": crs.public_id,
            "assessment_score": float(comp.assessment_score or 0.0),
            "completed_at": comp.completion_timestamp,
        })

    return render_template(
        request=request,
        name="pages/registry.html",
        context={
            "active_page": "registry",
            "metrics": metrics,
            "credentials": credentials,
            "page": page,
            "page_size": DEFAULT_PAGE_SIZE,
            "total_count": total_count,
            "total_pages": total_pages,
            "current_status": status.upper() if status else "ALL",
            "current_search": search or "",
            "eligible_candidates": candidates,
        },
        actor=actor,
    )


@router.get("/web/registry/table", response_class=HTMLResponse)
async def registry_table_htmx(
    request: Request,
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=200),
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX endpoint to return server-paginated credential table rows."""
    offset = (page - 1) * limit
    credentials, total_count = await _query_credentials(
        db, search=search, status=status, limit=limit, offset=offset
    )
    total_pages = max(1, math.ceil(total_count / limit))
    return render_template(
        request=request,
        name="partials/registry_table.html",
        context={
            "credentials": credentials,
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
        actor=actor,
    )


@router.post("/web/revocation/revoke", response_class=HTMLResponse)
async def revoke_credential_htmx(
    request: Request,
    credential_public_id: str = Form(...),
    reason_code: str = Form("ACADEMIC_MISCONDUCT"),
    reason_detail: Optional[str] = Form(None),
    actor: Dict[str, str] = Depends(require_role("registrar")),
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX endpoint to revoke a credential and re-render the updated table rows."""
    try:
        await RevocationService.revoke_credential(
            db=db,
            credential_public_id=credential_public_id.strip(),
            actor_id=actor["actor_id"],
            reason_code=reason_code.strip(),
            notes=reason_detail.strip() if reason_detail else None,
        )
    except Exception as exc:
        credentials, total_count = await _query_credentials(
            db, limit=DEFAULT_PAGE_SIZE, offset=0
        )
        total_pages = max(1, math.ceil(total_count / DEFAULT_PAGE_SIZE))
        resp = render_template(
            request=request,
            name="partials/registry_table.html",
            context={
                "credentials": credentials,
                "page": 1,
                "page_size": DEFAULT_PAGE_SIZE,
                "total_count": total_count,
                "total_pages": total_pages,
            },
            actor=actor,
        )
        resp.headers["HX-Trigger"] = json.dumps({
            "showToast": f"Revocation failed: {str(exc)}"
        })
        return resp

    credentials, total_count = await _query_credentials(
        db, limit=DEFAULT_PAGE_SIZE, offset=0
    )
    total_pages = max(1, math.ceil(total_count / DEFAULT_PAGE_SIZE))
    resp = render_template(
        request=request,
        name="partials/registry_table.html",
        context={
            "credentials": credentials,
            "page": 1,
            "page_size": DEFAULT_PAGE_SIZE,
            "total_count": total_count,
            "total_pages": total_pages,
        },
        actor=actor,
    )
    resp.headers["HX-Trigger"] = json.dumps({
        "showToast": f"Credential {credential_public_id} successfully revoked."
    })
    return resp


async def _query_credentials(
    db: AsyncSession,
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int]:
    """Query credentials and matching SQL row count with filters applied in SQL."""
    filters = []
    if status and status.upper() in ("ACTIVE", "REVOKED"):
        filters.append(Credential.status == status.upper())

    has_search = bool(search and search.strip())
    if has_search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                Credential.public_id.ilike(term),
                Learner.full_name.ilike(term),
                Learner.public_id.ilike(term),
                Course.title.ilike(term),
                Course.public_id.ilike(term),
                Credential.canonical_payload_hash.ilike(term),
            )
        )

    if has_search:
        count_stmt = (
            select(func.count(Credential.id))
            .join(CompletionRecord, Credential.completion_id == CompletionRecord.id)
            .join(Learner, CompletionRecord.learner_id == Learner.id)
            .join(Course, CompletionRecord.course_id == Course.id)
            .where(*filters)
        )
    else:
        count_stmt = select(func.count(Credential.id)).where(*filters)

    total_count = int((await db.execute(count_stmt)).scalar_one() or 0)

    stmt = (
        select(Credential, CompletionRecord, Learner, Course, Issuer)
        .join(CompletionRecord, Credential.completion_id == CompletionRecord.id)
        .join(Learner, CompletionRecord.learner_id == Learner.id)
        .join(Course, CompletionRecord.course_id == Course.id)
        .join(Issuer, Credential.issuer_id == Issuer.id)
        .where(*filters)
        .order_by(Credential.issued_at.desc(), Credential.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    creds = []
    for cred, comp, lnr, crs, iss in rows:
        creds.append({
            "id": cred.id,
            "public_id": cred.public_id,
            "canonical_payload_hash": cred.canonical_payload_hash,
            "learner_name": lnr.full_name,
            "learner_public_id": lnr.public_id,
            "course_title": crs.title,
            "course_public_id": crs.public_id,
            "assessment_score": float(comp.assessment_score or 0.0),
            "status": cred.status,
            "issuer_name": iss.name,
            "issued_at": cred.issued_at,
        })
    return creds, total_count


# =============================================================================
# 3. Immutable Audit Ledger (Server-Side Pagination, Page Size = 50)
# =============================================================================

@router.get("/audit", response_class=HTMLResponse)
async def audit_page(
    request: Request,
    page: int = Query(1, ge=1),
    event_type: Optional[str] = Query(None),
    target_entity_id: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """Render the immutable audit ledger page with server-side pagination."""
    total_events = (
        await db.execute(select(func.count(AuditEvent.id)))
    ).scalar_one() or 0

    total_issuances = (
        await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "CREDENTIAL_ISSUED"
            )
        )
    ).scalar_one() or 0

    total_revocations = (
        await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type == "CREDENTIAL_REVOKED"
            )
        )
    ).scalar_one() or 0

    total_verifications = (
        await db.execute(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.event_type.like("%VERIFICATION%")
            )
        )
    ).scalar_one() or 0

    offset = (page - 1) * DEFAULT_PAGE_SIZE
    events, total_count = await _query_audit_events(
        db,
        event_type=event_type,
        target_entity_id=target_entity_id,
        actor_id=actor_id,
        limit=DEFAULT_PAGE_SIZE,
        offset=offset,
    )
    total_pages = max(1, math.ceil(total_count / DEFAULT_PAGE_SIZE))

    return render_template(
        request=request,
        name="pages/audit.html",
        context={
            "active_page": "audit",
            "total_events": total_events,
            "total_issuances": total_issuances,
            "total_revocations": total_revocations,
            "total_verifications": total_verifications,
            "events": events,
            "page": page,
            "page_size": DEFAULT_PAGE_SIZE,
            "total_count": total_count,
            "total_pages": total_pages,
        },
        actor=actor,
    )


@router.get("/web/audit/table", response_class=HTMLResponse)
async def audit_table_htmx(
    request: Request,
    event_type: Optional[str] = Query(None),
    target_entity_id: Optional[str] = Query(None),
    actor_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=200),
    offset: Optional[int] = Query(None, ge=0),
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX endpoint to return server-paginated audit event rows."""
    effective_offset = offset if offset is not None else (page - 1) * limit
    effective_page = (effective_offset // limit) + 1 if offset is not None else page
    events, total_count = await _query_audit_events(
        db,
        event_type=event_type,
        target_entity_id=target_entity_id,
        actor_id=actor_id,
        limit=limit,
        offset=effective_offset,
    )
    total_pages = max(1, math.ceil(total_count / limit))
    return render_template(
        request=request,
        name="partials/audit_table.html",
        context={
            "events": events,
            "page": effective_page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
        actor=actor,
    )


@router.get("/web/export/audit")
async def export_audit_ledger(
    format: str = Query("csv", pattern="^(csv|json)$"),
    _actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """Stream all audit events without row limits as CSV or JSON download."""
    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
    events = list((await db.execute(stmt)).scalars().all())

    if format == "csv":
        async def _stream_csv() -> AsyncIterator[str]:
            header_buf = io.StringIO()
            writer = csv.writer(header_buf)
            writer.writerow([
                "event_id",
                "occurred_at_utc",
                "event_type",
                "actor_id",
                "target_entity_type",
                "target_entity_id",
                "details_json",
            ])
            yield header_buf.getvalue()

            chunk_buf = io.StringIO()
            chunk_writer = csv.writer(chunk_buf)
            for idx, e in enumerate(events, start=1):
                chunk_writer.writerow([
                    e.event_id,
                    e.occurred_at.isoformat() if e.occurred_at else "",
                    e.event_type,
                    e.actor_id or "",
                    e.target_entity_type,
                    e.target_entity_id,
                    json.dumps(e.details),
                ])
                if idx % 1000 == 0:
                    yield chunk_buf.getvalue()
                    chunk_buf.seek(0)
                    chunk_buf.truncate(0)
            remaining = chunk_buf.getvalue()
            if remaining:
                yield remaining

        return StreamingResponse(
            _stream_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=vericred_audit_ledger.csv"},
        )
    else:
        async def _stream_json() -> AsyncIterator[str]:
            yield "[\n"
            total = len(events)
            for idx, e in enumerate(events):
                item = {
                    "event_id": e.event_id,
                    "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
                    "event_type": e.event_type,
                    "actor_id": e.actor_id,
                    "target_entity_type": e.target_entity_type,
                    "target_entity_id": e.target_entity_id,
                    "details": e.details,
                }
                suffix = ",\n" if idx < total - 1 else "\n"
                yield json.dumps(item) + suffix
            yield "]\n"

        return StreamingResponse(
            _stream_json(),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=vericred_audit_ledger.json"},
        )


async def _query_audit_events(
    db: AsyncSession,
    event_type: Optional[str] = None,
    target_entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> Tuple[List[AuditEvent], int]:
    """Query audit events and matching SQL row count with filters applied in SQL."""
    filters = []
    if event_type and event_type.strip():
        filters.append(AuditEvent.event_type == event_type.strip())
    if target_entity_id and target_entity_id.strip():
        filters.append(AuditEvent.target_entity_id.ilike(f"%{target_entity_id.strip()}%"))
    if actor_id and actor_id.strip():
        filters.append(AuditEvent.actor_id.ilike(f"%{actor_id.strip()}%"))

    count_stmt = select(func.count(AuditEvent.id)).where(*filters)
    total_count = int((await db.execute(count_stmt)).scalar_one() or 0)

    stmt = (
        select(AuditEvent)
        .where(*filters)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return rows, total_count


# =============================================================================
# 4. Cryptographic Anomaly Stress-Test Lab
# =============================================================================

def _initial_unrun_scenarios() -> List[Dict[str, Any]]:
    """Build initial scenario card placeholders before any evaluation run has been executed."""
    cards: List[Dict[str, Any]] = []
    for scenario_id, meta in ANOMALY_SCENARIO_META.items():
        cards.append(
            {
                "scenario_id": scenario_id,
                "title": meta["title"],
                "description": meta["description"],
                "rule_reference": meta["rule_reference"],
                "example_entity_id": "Not run yet",
                "expected_outcome": meta["expected_outcome"],
                "actual_outcome": "Not run yet",
                "reason_code": "NOT_RUN_YET",
                "passed": None,
                "numerator": 0,
                "denominator": 0,
                "detection_rate_pct": 0.0,
                "elapsed_ms": None,
                "trace": "Not run yet",
            }
        )
    return cards


@router.get("/anomalies", response_class=HTMLResponse)
async def anomalies_page(
    request: Request,
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """Render the anomaly stress-test lab page showing latest evaluation report or 'Not run yet'."""
    active_stmt = select(Credential.public_id).where(Credential.status == "ACTIVE").limit(1)
    sample_valid = (await db.execute(active_stmt)).scalar_one_or_none() or "CRD-2026-000001"

    rev_stmt = select(Credential.public_id).where(Credential.status == "REVOKED").limit(1)
    sample_revoked = (await db.execute(rev_stmt)).scalar_one_or_none() or "CRD-2026-000002"

    report = get_latest_evaluation_report()
    results = report["scenarios"] if report is not None else _initial_unrun_scenarios()
    return render_template(
        request=request,
        name="pages/anomalies.html",
        context={
            "active_page": "anomalies",
            "report": report,
            "results": results,
            "sample_valid_id": sample_valid,
            "sample_revoked_id": sample_revoked,
        },
        actor=actor,
    )


@router.post("/web/anomalies/run/{scenario_id}", response_class=HTMLResponse)
async def run_single_anomaly_htmx(
    request: Request,
    scenario_id: str,
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX endpoint to execute real evaluation for a single anomaly scenario."""
    single = await EvaluationRunner.run_single_scenario(db=db, scenario_id=scenario_id)
    return render_template(
        request=request,
        name="partials/anomaly_result.html",
        context={
            "results": [single["scenario"]],
            "report": single["report"],
            "include_kpi_oob": True,
        },
        actor=actor,
    )


@router.post("/web/anomalies/run-all", response_class=HTMLResponse)
async def run_all_anomalies_htmx(
    request: Request,
    actor: Dict[str, str] = Depends(require_role("registrar", "auditor")),
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX endpoint to execute real evaluation across all 4 anomaly scenarios."""
    report = await EvaluationRunner.run_evaluation(db=db)
    return render_template(
        request=request,
        name="partials/anomaly_result.html",
        context={
            "results": report["scenarios"],
            "report": report,
            "include_kpi_oob": True,
        },
        actor=actor,
    )
