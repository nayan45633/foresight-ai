"""Foresight AI - Test Fixtures & Configuration."""

import asyncio
import os
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Use isolated in-memory or file-based SQLite database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def prepare_database():
    """Initializes tables in test database before each test and cleans up after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def async_client():
    """Provides async HTTP client for integration testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def client(async_client):
    """Alias for async_client."""
    yield async_client


@pytest.fixture
async def db_session():
    """Provides test-bound async database session for direct table assertions."""
    async with TestingSessionLocal() as session:
        yield session

