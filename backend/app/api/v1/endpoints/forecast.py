"""Foresight AI - Attack Forecasting & Multi-Horizon Prediction Endpoints."""

from datetime import datetime, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.forecast import AttackForecast
from app.db.session import get_db
from app.ml.contracts import (
    FeatureContribution,
    ForecastHorizonPrediction,
    ForecastResult,
    ThreatSeverityEnum,
    UncertaintyEstimate,
)
from app.schemas.forecast import MultiHorizonForecastResponse

router = APIRouter()


def _model_to_forecast_result(db_obj: AttackForecast) -> ForecastResult:
    """Helper converting ORM model to strictly typed ForecastResult contract."""
    severity = ThreatSeverityEnum.LOW
    if db_obj.risk_level in ThreatSeverityEnum._value2member_map_:
        severity = ThreatSeverityEnum(db_obj.risk_level)

    uncertainty_dict = db_obj.uncertainty_metrics or {}
    uncertainty = UncertaintyEstimate(
        credible_interval_lower=uncertainty_dict.get("credible_interval_lower", max(0.0, db_obj.probability - 0.1)),
        credible_interval_upper=uncertainty_dict.get("credible_interval_upper", min(1.0, db_obj.probability + 0.1)),
        confidence_level=uncertainty_dict.get("confidence_level", 0.95),
        epistemic_uncertainty=uncertainty_dict.get("epistemic_uncertainty", 0.05),
        aleatoric_uncertainty=uncertainty_dict.get("aleatoric_uncertainty", 0.05),
    )

    contributions = [
        FeatureContribution(**item) if isinstance(item, dict) else item
        for item in (db_obj.feature_contributions or [])
    ]

    return ForecastResult(
        id=db_obj.id,
        timestamp=db_obj.forecast_timestamp,
        forecast=ForecastHorizonPrediction(
            threat=db_obj.predicted_threat,
            probability=db_obj.probability,
            confidence=db_obj.confidence,
            horizon_minutes=db_obj.horizon_minutes,
            severity=severity,
        ),
        anomaly_score=db_obj.anomaly_score,
        uncertainty=uncertainty,
        model_version=db_obj.model_version,
        feature_contributions=contributions,
        target_entity=db_obj.target_asset,
    )


@router.get("/current", response_model=Optional[ForecastResult])
async def get_current_forecast(db: AsyncSession = Depends(get_db)) -> Any:
    """Retrieves the latest generated temporal attack forecast."""
    result = await db.execute(
        select(AttackForecast).order_by(AttackForecast.forecast_timestamp.desc()).limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return None
    return _model_to_forecast_result(latest)


@router.get("/multi-horizon", response_model=MultiHorizonForecastResponse)
async def get_multi_horizon_forecast(
    target_entity: str = Query(default="GLOBAL_PERIMETER"),
    db: AsyncSession = Depends(get_db)
) -> MultiHorizonForecastResponse:
    """Retrieves current forecasts across multiple horizons (5m, 15m, 30m, 60m)."""
    result = await db.execute(
        select(AttackForecast)
        .where(AttackForecast.target_asset == target_entity)
        .order_by(AttackForecast.forecast_timestamp.desc())
        .limit(4)
    )
    forecasts = result.scalars().all()
    
    results = [_model_to_forecast_result(f) for f in forecasts]
    latest_anomaly = results[0].anomaly_score if results else 0.0

    return MultiHorizonForecastResponse(
        timestamp=datetime.now(timezone.utc),
        target_entity=target_entity,
        anomaly_score=latest_anomaly,
        horizons=results,
    )


@router.get("/history", response_model=List[ForecastResult])
async def get_forecast_history(
    limit: int = Query(default=50, ge=1, le=500),
    severity: Optional[ThreatSeverityEnum] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Retrieves historical forecasts for temporal sequence audits."""
    stmt = select(AttackForecast).order_by(AttackForecast.forecast_timestamp.desc()).limit(limit)
    if severity:
        stmt = stmt.where(AttackForecast.risk_level == severity.value)
        
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [_model_to_forecast_result(f) for f in records]


@router.get("/{forecast_id}", response_model=ForecastResult)
async def get_forecast_by_id(
    forecast_id: str,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Retrieves a specific forecast by ID with full explainability attribution."""
    result = await db.execute(
        select(AttackForecast).where(AttackForecast.id == forecast_id)
    )
    forecast = result.scalar_one_or_none()
    if not forecast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Forecast not found")
    return _model_to_forecast_result(forecast)
