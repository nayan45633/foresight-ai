"""Foresight AI - Central API v1 Router."""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    alerts,
    audit,
    auth,
    counterfactual,
    forecast,
    health,
    incidents,
    model,
    monitoring,
    risk,
    telemetry,
)

api_router = APIRouter()

# Register core endpoint domains
api_router.include_router(health.router, tags=["System Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Identity"])
api_router.include_router(audit.router, prefix="/audit", tags=["Security Audit Logs"])
api_router.include_router(telemetry.router, prefix="/telemetry", tags=["Telemetry Ingestion"])
api_router.include_router(forecast.router, prefix="/forecast", tags=["Attack Forecasting"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["Security Alerts"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["SOC Incidents"])
api_router.include_router(model.router, prefix="/model", tags=["ML Model Registry"])
api_router.include_router(counterfactual.router, prefix="/model/counterfactual", tags=["Counterfactual What-If"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk State & Attack Path"])
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["Model Monitoring & Observability"])


