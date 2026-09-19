"""Foresight AI - Proactive Alerts & SOC Incident Management Models."""

import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class SecurityAlert(Base, TimestampMixin):
    """Proactive early-warning alert triggered by high-risk attack forecast."""
    __tablename__ = "security_alerts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True, nullable=False)  # OPEN, INVESTIGATING, MITIGATED, FALSE_POSITIVE
    predicted_threat: Mapped[str] = mapped_column(String(100), nullable=False)
    forecast_id: Mapped[str] = mapped_column(String(36), nullable=True)
    estimated_time_to_impact_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_mitigation: Mapped[str] = mapped_column(String(1000), nullable=True)
    context_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class IncidentCase(Base, TimestampMixin):
    """SOC investigation case tracking linked telemetry, forecasts, and human remediation."""
    __tablename__ = "incident_cases"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True, nullable=False)
    assigned_to: Mapped[str] = mapped_column(String(100), nullable=True)
    summary: Mapped[str] = mapped_column(String(2000), nullable=True)
    indicators_of_compromise: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    timeline_events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
