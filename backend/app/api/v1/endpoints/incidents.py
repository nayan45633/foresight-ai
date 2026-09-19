"""Foresight AI - SOC Incident Investigation Endpoints."""

from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.alert import IncidentCase
from app.db.session import get_db
from app.schemas.incident import IncidentCreate, IncidentResponse

router = APIRouter()


@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Retrieves list of ongoing SOC incident investigation cases."""
    result = await db.execute(select(IncidentCase).order_by(IncidentCase.created_at.desc()).limit(limit))
    return result.scalars().all()


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    incident_in: IncidentCreate,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Creates a new incident case for tracking threat investigation."""
    case = IncidentCase(
        title=incident_in.title,
        status="ACTIVE",
        assigned_to=incident_in.assigned_to,
        summary=incident_in.summary,
        indicators_of_compromise=incident_in.indicators_of_compromise,
        timeline_events=[],
    )
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return case


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: str, db: AsyncSession = Depends(get_db)) -> Any:
    """Retrieves full investigation timeline and IOCs for an incident."""
    result = await db.execute(select(IncidentCase).where(IncidentCase.id == incident_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident case not found")
    return case
