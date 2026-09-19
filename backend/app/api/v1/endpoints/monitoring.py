"""Foresight AI - Model Monitoring & Observability API Router (Step 11).

Exposes production monitoring endpoints for composite model health, telemetry data quality,
statistical feature/prediction drift, calibration stability, and forecast performance.
"""

from typing import Any
from fastapi import APIRouter, Depends, status

from app.monitoring.calibration_monitor import CalibrationHealthReport
from app.monitoring.data_quality_monitor import DataQualityReport
from app.monitoring.drift_monitor import DriftReport
from app.monitoring.forecast_monitor import ForecastPerformanceReport
from app.monitoring.model_health import CompositeModelHealthReport
from app.monitoring.monitoring_service import monitoring_service

router = APIRouter()


@router.get("/health", response_model=CompositeModelHealthReport, status_code=status.HTTP_200_OK)
async def get_model_health() -> CompositeModelHealthReport:
    """Retrieves composite model health fusing artifact integrity, data quality, drift, and latency."""
    return monitoring_service.get_composite_model_health()


@router.get("/data-quality", response_model=DataQualityReport, status_code=status.HTTP_200_OK)
async def get_data_quality() -> DataQualityReport:
    """Retrieves empirical data quality, completeness, and schema adherence metrics."""
    return monitoring_service.get_data_quality_report()


@router.get("/drift", response_model=DriftReport, status_code=status.HTTP_200_OK)
async def get_drift_report() -> DriftReport:
    """Retrieves statistical feature drift (PSI/KS) and prediction distribution shift analysis."""
    return monitoring_service.get_drift_report()


@router.get("/calibration", response_model=CalibrationHealthReport, status_code=status.HTTP_200_OK)
async def get_calibration_monitoring() -> CalibrationHealthReport:
    """Retrieves calibration stability, Brier scores, ECE, and empirical conformal coverage."""
    return monitoring_service.get_calibration_report()


@router.get("/performance", response_model=ForecastPerformanceReport, status_code=status.HTTP_200_OK)
async def get_forecast_performance_monitoring() -> ForecastPerformanceReport:
    """Retrieves empirical multi-horizon forecast accuracy and lead-time metrics."""
    return monitoring_service.get_performance_report()
