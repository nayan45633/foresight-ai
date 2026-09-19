"""Foresight AI - Main FastAPI Application Entrypoint.

Cybersecurity AI platform for network attack forecasting.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.middleware.errors import setup_exception_handlers
from app.api.middleware.logging import RequestLoggingMiddleware
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.security import SecurityHeadersMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager: sets up loggers, caches, and database schemas."""
    setup_logging(log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger.info(f"Starting {settings.PROJECT_NAME} in [{settings.ENVIRONMENT}] mode...")
    
    # Initialize database tables
    try:
        await init_db()
        logger.info("Database connection established and verified.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME} cleanly...")


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    description="Foresight AI Defensive Intelligence Engine — Multi-Horizon Network Attack Forecasting",
    version="1.0.0",
    lifespan=lifespan,
)

# Register Structured Error Handlers
setup_exception_handlers(app)

# Custom Middlewares (Ordered by execution flow)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, rate_limit_per_minute=300)
app.add_middleware(SecurityHeadersMiddleware)

# Cross-Origin Resource Sharing (CORS)
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Mount API V1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["System Root"])
async def root():
    """System entry point directing operators to API documentation."""
    return {
        "name": settings.PROJECT_NAME,
        "status": "online",
        "docs_url": f"{settings.API_V1_STR}/docs",
        "health_url": f"{settings.API_V1_STR}/health",
        "version": "1.0.0",
    }
