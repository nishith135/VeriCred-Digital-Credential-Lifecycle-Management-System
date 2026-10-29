"""FastAPI application factory and server entrypoint.

Configures:
- Static file serving (/static)
- Jinja2 template rendering
- Domain exception handlers
- Health check endpoints
- API routing
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.core.config import settings
from backend.core.database import async_engine
from backend.core.exceptions import DomainException, domain_exception_handler
from backend.core.rate_limit import RateLimitExceededError
from backend.core.rbac import (
    RBACForbiddenError,
    RBACUnauthorizedError,
    get_current_actor,
    get_role_context,
)


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    # Startup: ensure frontend static directories exist
    os.makedirs(STATIC_DIR / "css", exist_ok=True)
    os.makedirs(STATIC_DIR / "js", exist_ok=True)
    os.makedirs(TEMPLATES_DIR / "pages", exist_ok=True)
    os.makedirs(TEMPLATES_DIR / "partials", exist_ok=True)
    yield
    # Shutdown: dispose of database engine pools
    await async_engine.dispose()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Tamper-evident academic credential lifecycle system with multi-factor verification.",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static assets (physical and logical separation in frontend/static)
    os.makedirs(STATIC_DIR, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Domain Exception Handling
    app.add_exception_handler(DomainException, domain_exception_handler)

    @app.exception_handler(RBACUnauthorizedError)
    async def rbac_unauthorized_handler(request: Request, exc: RBACUnauthorizedError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={
                "error": "UNAUTHORIZED",
                "message": exc.message,
            },
        )

    @app.exception_handler(RBACForbiddenError)
    async def rbac_forbidden_handler(request: Request, exc: RBACForbiddenError):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "FORBIDDEN",
                    "required_roles": exc.required_roles,
                    "current_role": exc.current_role,
                },
            )
        if request.headers.get("HX-Request") == "true" or request.url.path.startswith("/web/"):
            return templates.TemplateResponse(
                request=request,
                name="partials/forbidden_fragment.html",
                context={
                    "current_role_id": exc.current_role,
                    "required_roles": exc.required_roles,
                },
                status_code=403,
            )
        ctx = get_role_context(request)
        ctx.update(
            {
                "active_page": "forbidden",
                "required_roles": exc.required_roles,
                "current_role_id": exc.current_role,
            }
        )
        return templates.TemplateResponse(
            request=request,
            name="pages/forbidden.html",
            context=ctx,
            status_code=403,
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(request: Request, exc: RateLimitExceededError):
        headers = {"Retry-After": str(exc.retry_after)}
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": str(exc),
                    "retry_after": exc.retry_after,
                },
                headers=headers,
            )
        return HTMLResponse(
            status_code=429,
            content=(
                '<div class="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 '
                'text-amber-300 text-xs font-mono">'
                f"<strong>429 Rate Limit Exceeded:</strong> {exc}"
                "</div>"
            ),
            headers=headers,
        )

    # API Routers
    from backend.api.v1.audit import router as audit_router
    from backend.api.v1.issuance import router as issuance_router
    from backend.api.v1.revocation import router as revocation_router
    from backend.api.v1.verification import router as verification_router
    from backend.api.views.web import router as web_router

    app.include_router(web_router)
    app.include_router(issuance_router)
    app.include_router(verification_router)
    app.include_router(revocation_router)
    app.include_router(audit_router)

    @app.get("/health", tags=["System"])
    async def health_check(
        _actor: dict[str, str] = Depends(get_current_actor),
    ) -> dict[str, str]:
        """System health and environment probe."""
        return {
            "status": "healthy",
            "environment": settings.APP_ENV,
            "version": "1.0.0",
        }

    return app


app = create_app()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
