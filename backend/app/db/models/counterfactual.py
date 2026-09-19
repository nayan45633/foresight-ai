"""Foresight AI - Counterfactual What-If Scenario Database Model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class CounterfactualScenarioRecord(Base, TimestampMixin):
    """Persistent storage for evaluated What-If model sensitivity scenarios."""
    __tablename__ = "counterfactual_scenarios"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    scenario_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    scenario_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    scientific_disclaimer: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Audit payloads
    requested_perturbations: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    applied_perturbations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    horizon_results: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    baseline_vector_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    counterfactual_vector_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    
    any_decision_flipped: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_risk_reduction: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_risk_elevation: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    execution_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    include_shap: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="counterfactual_scenarios")

    __table_args__ = (
        Index("idx_cf_user_time", "user_id", "timestamp"),
    )
