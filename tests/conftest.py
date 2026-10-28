"""Pytest configuration and test database fixtures."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.database import Base, get_db_session
from src.core.security import generate_ed25519_keypair
from src.main import app
from src.models import (
    CompletionRecord,
    Course,
    CredentialRule,
    Issuer,
    Learner,
)

from sqlalchemy.pool import NullPool

# Use test engine connected to credential_db with NullPool for per-test event loop isolation
test_async_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
)

test_async_session_factory = async_sessionmaker(
    bind=test_async_engine,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession,
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session per test, rolling back on teardown."""
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


from uuid import uuid4

@pytest_asyncio.fixture
async def sample_issuer(db_session: AsyncSession):
    """Seed a valid, active Issuer."""
    priv_pem, pub_pem = generate_ed25519_keypair()
    uid = uuid4().hex[:8].upper()
    issuer = Issuer(
        public_id=f"ISS-TEST-{uid}",
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
    uid = uuid4().hex[:8].upper()
    course = Course(
        public_id=f"CRS-{uid}",
        title="Advanced Distributed Cryptographic Systems",
        version="1.0",
        status="ACTIVE",
    )
    learner = Learner(
        public_id=f"LRN-{uid}",
        full_name="Alice Q. Student",
        email=f"alice.{uid}@university.edu",
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
