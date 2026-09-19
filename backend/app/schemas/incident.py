"""Foresight AI - SOC Incident Investigation Schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IncidentResponse(BaseModel):
    id: str
    title: str
    status: str
    assigned_to: Optional[str] = None
    summary: Optional[str] = None
    indicators_of_compromise: List[Dict[str, Any]]
    timeline_events: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    assigned_to: Optional[str] = None
    summary: Optional[str] = None
    indicators_of_compromise: List[Dict[str, Any]] = Field(default_factory=list)
