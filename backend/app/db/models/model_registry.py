"""Foresight AI - Model Registry & Artifact Versioning Database Model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import DateTime, Float, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ModelVersionRecord(Base, TimestampMixin):
    """Authoritative registry of forecasting model artifacts, calibration curves, and validation health."""
    __tablename__ = "model_registry"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    version_tag: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    model_architecture: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True, nullable=False)  # ACTIVE, CANDIDATE, RETIRED, ARCHIVED
    feature_schema_version: Mapped[str] = mapped_column(String(32), default="v1.0.0", nullable=False)
    calibration_version: Mapped[str] = mapped_column(String(50), nullable=False)
    conformal_version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Statistical validation metrics
    brier_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_calibration_error: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    f1_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    precision_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roc_auc_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    conformal_target_coverage: Mapped[float] = mapped_column(Float, default=0.90, nullable=False)
    conformal_empirical_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    hyperparameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metrics_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    artifact_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    trained_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_registry_status_time", "status", "created_at"),
    )
