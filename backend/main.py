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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.core.config import settings
from backend.core.database import async_engine
from backend.core.exceptions import DomainException, domain_exception_handler


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
    async def health_check() -> dict[str, str]:
        """System health and environment probe."""
        return {
            "status": "healthy",
            "environment": settings.APP_ENV,
            "version": "1.0.0",
        }

    return app


app = create_app()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
