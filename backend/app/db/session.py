"""Foresight AI - Database Engine & Async Session Management."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.logging import logger

# Create async engine with connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initializes database tables during startup."""
    from app.db.base import Base
    # Import all models to register them with Base metadata
    import app.db.models  # noqa: F401
    
    async with engine.begin() as conn:
        logger.info("Initializing database schema...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema initialized successfully.")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency for obtaining transactional async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
