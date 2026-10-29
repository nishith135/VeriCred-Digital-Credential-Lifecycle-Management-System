"""Pytest configuration and isolated test database fixtures.

Enforces strict database isolation:
- Refuses to run unless the resolved database name ends with '_test' (e.g. credential_test_db).
- Automatically creates credential_test_db if missing and runs `alembic upgrade head` once per session.
- Truncates all 9 tables (RESTART IDENTITY CASCADE) between tests so every test is independent.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import subprocess
import sys
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import backend.core.database as db_module
from backend.core.config import settings
from backend.core.database import get_db_session
from backend.core.security import generate_ed25519_keypair
from backend.main import app
from backend.models import (
    CompletionRecord,
    Course,
    CredentialRule,
    Issuer,
    Learner,
)
from backend.services.ids import (
    AUDIT_EVENT_SEQUENCE,
    CREDENTIAL_SEQUENCE,
    VERIFICATION_SEQUENCE,
    format_course_id,
    format_issuer_id,
    format_learner_id,
)

TRUNCATE_ALL_TABLES_SQL = text(
    "TRUNCATE TABLE audit_events, verification_requests, revocations, "
    "credentials, completion_records, credential_rules, learners, "
    "courses, issuers RESTART IDENTITY CASCADE;"
)

RESET_PUBLIC_SEQUENCES_SQL = text(
    f"SELECT setval('{CREDENTIAL_SEQUENCE}', 1, false), "
    f"setval('{VERIFICATION_SEQUENCE}', 1, false), "
    f"setval('{AUDIT_EVENT_SEQUENCE}', 1, false);"
)


def _resolve_test_db_urls() -> tuple[str, str]:
    """Resolve async and sync test database URLs, honoring explicit environment overrides."""
    if "TEST_DATABASE_URL" in os.environ:
        async_url = os.environ["TEST_DATABASE_URL"]
    elif "DATABASE_URL" in os.environ:
        async_url = os.environ["DATABASE_URL"]
    else:
        async_url = settings.TEST_DATABASE_URL

    if "TEST_DATABASE_URL_SYNC" in os.environ:
        sync_url = os.environ["TEST_DATABASE_URL_SYNC"]
    elif "SYNC_DATABASE_URL" in os.environ:
        sync_url = os.environ["SYNC_DATABASE_URL"]
    elif "TEST_DATABASE_URL" in os.environ or "DATABASE_URL" in os.environ:
        sync_url = async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace(
            "postgresql://", "postgresql+psycopg2://"
        )
    else:
        sync_url = settings.TEST_DATABASE_URL_SYNC

    return async_url, sync_url


def _assert_safe_test_db(url_str: str) -> str:
    """Abort pytest immediately if the resolved database name does not end with '_test'."""
    parsed = make_url(url_str)
    db_name = (parsed.database or "").strip()
    # Strip optional trailing '_db' so 'credential_test_db' resolves to 'credential_test'
    normalized_name = db_name[:-3] if db_name.endswith("_db") else db_name

    if db_name == "credential_db" or not normalized_name.endswith("_test"):
        pytest.exit(
            f"SAFETY GUARD ABORT: Refusing to run pytest against database '{db_name}'. "
            "Test suite database name must end with '_test' (e.g. 'credential_test_db') and must never be 'credential_db'.",
            returncode=1,
        )
    return db_name


def _ensure_test_database_exists(sync_url_str: str) -> None:
    """Create the isolated test database if it does not already exist."""
    target_url = make_url(sync_url_str)
    db_name = _assert_safe_test_db(sync_url_str)
    admin_url = target_url.set(database="postgres")

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


def pytest_configure(config: pytest.Config) -> None:
    """Enforce database safety guard before test collection and execution."""
    async_url, sync_url = _resolve_test_db_urls()
    _assert_safe_test_db(async_url)
    _assert_safe_test_db(sync_url)


TEST_ASYNC_DATABASE_URL, TEST_SYNC_DATABASE_URL = _resolve_test_db_urls()

test_async_engine = create_async_engine(
    TEST_ASYNC_DATABASE_URL,
    poolclass=NullPool,
)

test_async_session_factory = async_sessionmaker(
    bind=test_async_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)

test_sync_engine = create_engine(
    TEST_SYNC_DATABASE_URL,
    poolclass=NullPool,
)

test_sync_session_factory = sessionmaker(
    bind=test_sync_engine,
    autoflush=False,
    expire_on_commit=False,
)

# Rebind core database module engines to the isolated test database
db_module.async_engine = test_async_engine
db_module.async_session_factory = test_async_session_factory
db_module.sync_engine = test_sync_engine
db_module.sync_session_factory = test_sync_session_factory


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create credential_test_db if missing and apply Alembic migrations once per session."""
    _assert_safe_test_db(TEST_ASYNC_DATABASE_URL)
    _assert_safe_test_db(TEST_SYNC_DATABASE_URL)
    _ensure_test_database_exists(TEST_SYNC_DATABASE_URL)

    env = {
        **os.environ,
        "DATABASE_URL": TEST_ASYNC_DATABASE_URL,
        "SYNC_DATABASE_URL": TEST_SYNC_DATABASE_URL,
    }
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.exit(
            f"Failed to run 'alembic upgrade head' on test database:\n{result.stderr}\n{result.stdout}",
            returncode=1,
        )

    yield

    test_sync_engine.dispose()


@pytest.fixture(autouse=True)
def isolate_and_truncate_tables():
    """Truncate all tables (RESTART IDENTITY CASCADE) and reset sequences before and after every test."""
    from backend.core.rate_limit import verify_rate_limiter
    from backend.evaluation import reset_latest_evaluation_report

    _assert_safe_test_db(TEST_SYNC_DATABASE_URL)
    verify_rate_limiter.set_limit(None)
    reset_latest_evaluation_report()
    with test_sync_engine.begin() as conn:
        conn.execute(TRUNCATE_ALL_TABLES_SQL)
        conn.execute(RESET_PUBLIC_SEQUENCES_SQL)
    yield
    verify_rate_limiter.set_limit(None)
    reset_latest_evaluation_report()
    with test_sync_engine.begin() as conn:
        conn.execute(TRUNCATE_ALL_TABLES_SQL)
        conn.execute(RESET_PUBLIC_SEQUENCES_SQL)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session connected strictly to credential_test_db."""
    async with test_async_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP test client with database dependency override."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_issuer(db_session: AsyncSession):
    """Seed a valid, active Issuer."""
    priv_pem, pub_pem = generate_ed25519_keypair()
    issuer = Issuer(
        public_id=format_issuer_id(1),
        name="State Polytechnic Accreditation Authority",
        public_key_pem=pub_pem,
        status="ACTIVE",
    )
    db_session.add(issuer)
    await db_session.commit()
    await db_session.refresh(issuer)
    return issuer, priv_pem


@pytest_asyncio.fixture
async def sample_academic_setup(db_session: AsyncSession):
    """Seed Course, Learner, and CredentialRule with 80% passing threshold."""
    now = datetime.now(timezone.utc)
    course = Course(
        public_id=format_course_id(1),
        title="Advanced Distributed Cryptographic Systems",
        version="1.0",
        status="ACTIVE",
    )
    learner = Learner(
        public_id=format_learner_id(1),
        full_name="Alice Q. Student",
        email="alice.0001@university.edu",
        status="ACTIVE",
    )
    db_session.add_all([course, learner])
    await db_session.commit()
    await db_session.refresh(course)
    await db_session.refresh(learner)

    rule = CredentialRule(
        course_id=course.id,
        rule_version="1.0",
        min_score=Decimal("80.00"),
        required_completion_status="COMPLETED",
        effective_from=now - timedelta(days=30),
        effective_to=now + timedelta(days=365),
        active=True,
    )
    db_session.add(rule)
    await db_session.commit()
    await db_session.refresh(rule)

    return course, learner, rule
