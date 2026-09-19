"""Foresight AI - Forecast Schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.ml.contracts import ForecastResult, ThreatSeverityEnum


class ForecastQueryFilter(BaseModel):
    min_probability: Optional[float] = Field(default=0.0, ge=0.0, le=1.0)
    severity: Optional[ThreatSeverityEnum] = None
    horizon_minutes: Optional[int] = None
    limit: int = Field(default=50, ge=1, le=500)


class MultiHorizonForecastResponse(BaseModel):
    timestamp: datetime
    target_entity: str
    anomaly_score: float
    horizons: List[ForecastResult]
