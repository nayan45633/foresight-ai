"""Foresight AI - User Account Database Model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User account entity for SOC operators, analysts, and administrators."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="analyst", index=True, nullable=False)  # admin, analyst, user, operator
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    counterfactual_scenarios = relationship("CounterfactualScenarioRecord", back_populates="user", lazy="selectin")
    telemetry_jobs = relationship("TelemetryJob", back_populates="user", lazy="selectin")
