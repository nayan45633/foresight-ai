"""Foresight AI - Authentication Session Database Model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class AuthSession(Base, TimestampMixin):
    """Tracks active and historical user authentication sessions for token revocation."""
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_revoked", "expires_at"),
    )
