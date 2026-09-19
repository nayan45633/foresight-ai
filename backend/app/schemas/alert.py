"""Foresight AI - Security Alert Schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertResponse(BaseModel):
    id: str
    title: str
    severity: str
    status: str
    predicted_threat: str
    forecast_id: Optional[str] = None
    estimated_time_to_impact_minutes: int
    recommended_mitigation: Optional[str] = None
    context_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertUpdate(BaseModel):
    status: Optional[str] = Field(None, description="OPEN, INVESTIGATING, MITIGATED, FALSE_POSITIVE")
    notes: Optional[str] = None
