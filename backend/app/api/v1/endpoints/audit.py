"""Foresight AI - Audit Logs API Endpoints."""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_analyst_user
from app.db.models.audit import AuditLog
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.audit import AuditLogResponse

router = APIRouter()


@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None, description="Filter by action name"),
    actor: Optional[str] = Query(None, description="Filter by actor username/email"),
    current_user: User = Depends(get_current_analyst_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Retrieves immutable security and operational audit logs for SOC compliance."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        query = query.where(AuditLog.action == action)
    if actor:
        query = query.where(AuditLog.actor == actor)
        
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
