"""Foresight AI - Core Dependencies & Authorization Guards."""

from datetime import datetime, timezone
from typing import Callable, List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models.audit import AuditLog
from app.db.models.user import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependency that decodes and validates bearer tokens from request authorization header."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or malformed authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Ensure token is an access token if token_type claim exists
    if payload.get("type") and payload["type"] != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type: expected access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or inactive",
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensures current user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    return current_user


def require_roles(allowed_roles: List[str]) -> Callable:
    """Factory that enforces role-based access control (RBAC)."""
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.is_superuser:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires one of roles {allowed_roles}, current role is '{current_user.role}'",
            )
        return current_user
    return role_checker


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Guarantees caller has admin or superuser privileges."""
    if not (current_user.is_superuser or current_user.role == "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required",
        )
    return current_user


async def get_current_analyst_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Guarantees caller has analyst or admin privileges."""
    if not (current_user.is_superuser or current_user.role in ["analyst", "admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or administrative privileges required",
        )
    return current_user


async def create_audit_entry(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    actor_username: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "SUCCESS",
    details: Optional[dict] = None,
) -> AuditLog:
    """Helper function to record persistent security and operational audit logs."""
    entry = AuditLog(
        actor=actor_username or actor_user_id or "SYSTEM",
        actor_user_id=actor_user_id,
        action=action,
        resource=resource_type,
        resource_id=resource_id,
        client_ip=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
        status=status,
        details=details or {},
    )
    db.add(entry)
    return entry

