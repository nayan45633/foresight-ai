"""Foresight AI - Security Alerts & Mitigation Endpoints."""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.alert import SecurityAlert
from app.db.session import get_db
from app.schemas.alert import AlertResponse, AlertUpdate

router = APIRouter()


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Retrieves list of active and historical predictive security alerts."""
    stmt = select(SecurityAlert).order_by(SecurityAlert.created_at.desc()).limit(limit)
    if status_filter:
        stmt = stmt.where(SecurityAlert.status == status_filter.upper())
    if severity:
        stmt = stmt.where(SecurityAlert.severity == severity.upper())
        
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    """Retrieves a single alert with mitigation recommendations."""
    result = await db.execute(select(SecurityAlert).where(SecurityAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: str,
    update_data: AlertUpdate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Updates status or notes for an existing alert."""
    result = await db.execute(select(SecurityAlert).where(SecurityAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
        
    if update_data.status:
        alert.status = update_data.status.upper()
    if update_data.notes:
        alert.context_data = {**alert.context_data, "analyst_notes": update_data.notes}
        
    await db.flush()
    await db.refresh(alert)
    return alert
