"""Foresight AI - Security Audit Logging ORM Model."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    """Immutable audit trail for operator actions, ML triggers, and security events."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    actor: Mapped[str] = mapped_column(String(100), index=True, nullable=False)  # User email/username, System, or API Key
    actor_user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)  # e.g., AUTH_LOGIN, AUTH_LOGOUT, SCENARIO_EVAL, MODEL_ACTIVATE
    resource: Mapped[str] = mapped_column(String(100), index=True, nullable=False)  # e.g., USER, FORECAST, SCENARIO, TELEMETRY_JOB
    resource_id: Mapped[str] = mapped_column(String(64), nullable=True)
    client_ip: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS", index=True, nullable=False)  # SUCCESS, FAILURE, DENIED
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("idx_audit_action_time", "action", "created_at"),
        Index("idx_audit_user_time", "actor_user_id", "created_at"),
    )

