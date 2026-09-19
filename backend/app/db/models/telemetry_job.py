"""Foresight AI - Telemetry Processing Job Database Model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class TelemetryJob(Base, TimestampMixin):
    """Tracks asynchronous and batch telemetry ingestion jobs with quality metrics."""
    __tablename__ = "telemetry_jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # PCAP, NETFLOW, JSON_BATCH, SIMULATED
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True, nullable=False)  # QUEUED, PROCESSING, COMPLETED, FAILED
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_flow_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_state: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    quality_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    user = relationship("User", back_populates="telemetry_jobs")

    __table_args__ = (
        Index("idx_job_status_created", "status", "created_at"),
    )
