"""Foresight AI - Risk State & Attack Path Transition Database Models."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class RiskStateRecord(Base, TimestampMixin):
    """Persistent historical snapshot of perimeter risk state evaluations with anti-flutter metadata."""
    __tablename__ = "risk_state_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    evaluation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    current_state: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # NORMAL, WATCH, SUSPICIOUS, ELEVATED, CRITICAL
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    max_calibrated_probability: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    triggering_horizon_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active_alert_horizons: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    uncertainty_level: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False)
    evidence_summary: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    top_risk_features: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    attack_path_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_hysteresis_dampened: Mapped[bool] = mapped_column(default=False, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_risk_state_time", "current_state", "timestamp"),
    )


class RiskTransitionRecord(Base, TimestampMixin):
    """Auditable state transition event logging security escalation / de-escalation."""
    __tablename__ = "risk_transition_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    transition_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    forecast_probability: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[str] = mapped_column(String(32), default="LOW", nullable=False)
    triggering_horizon: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    triggering_evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        Index("idx_transition_time_state", "new_state", "timestamp"),
    )
