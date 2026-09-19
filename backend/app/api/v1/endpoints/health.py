"""Foresight AI - System Health & Readiness Endpoints."""

import platform
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK, summary="Liveness Probe")
async def health_check() -> Dict[str, Any]:
    """Returns basic service health, platform details, and timestamp."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "system": platform.system(),
    }


@router.get("/ready", status_code=status.HTTP_200_OK, summary="Readiness Probe")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Verifies database connectivity and essential subsystem availability."""
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    is_ready = db_status == "ok"
    return {
        "status": "ready" if is_ready else "not_ready",
        "database": db_status,
        "active_model_version": settings.ACTIVE_MODEL_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
