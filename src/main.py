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

from src.core.config import settings
from src.core.database import async_engine
from src.core.exceptions import DomainException, domain_exception_handler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown hooks."""
    # Startup: ensure static directories exist
    os.makedirs("src/static/css", exist_ok=True)
    os.makedirs("src/static/js", exist_ok=True)
    os.makedirs("src/templates/pages", exist_ok=True)
    os.makedirs("src/templates/partials", exist_ok=True)
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

    # Static assets
    app.mount("/static", StaticFiles(directory="src/static"), name="static")

    # Domain Exception Handling
    app.add_exception_handler(DomainException, domain_exception_handler)

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
templates = Jinja2Templates(directory="src/templates")
