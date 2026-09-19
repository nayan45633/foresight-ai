"""Foresight AI - Authentication & Identity Endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    create_audit_entry,
    get_current_admin_user,
    get_current_user,
    oauth2_scheme,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.db.models.session import AuthSession
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    Token,
    UserCreate,
    UserResponse,
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Registers a new SOC user account with salted password hashing."""
    # Check if username or email exists
    existing = await db.execute(
        select(User).where((User.email == user_in.email) | (User.username == user_in.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists",
        )
        
    db_user = User(
        email=user_in.email,
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role if user_in.role in ["admin", "analyst", "user"] else "analyst",
        is_active=True,
    )
    db.add(db_user)
    await db.commit()
    return db_user


@router.post("/login", response_model=Token)
async def login(
    login_req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Authenticates credentials, updates login timestamp, issues access + refresh tokens and records session."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    result = await db.execute(
        select(User).where(
            (User.username == login_req.username_or_email) | (User.email == login_req.username_or_email)
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(login_req.password, user.hashed_password):
        if user:
            await create_audit_entry(
                db=db,
                action="LOGIN_FAILED",
                resource_type="AUTH",
                resource_id=user.id,
                actor_user_id=user.id,
                actor_username=user.username,
                client_ip=client_ip,
                status="FAILURE",
                details={"reason": "Invalid password"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive or suspended user account",
        )
        
    now = datetime.now(timezone.utc)
    user.last_login_at = now

    # Issue access and refresh tokens
    access_token = create_access_token(
        subject=user.id,
        claims={"role": user.role, "username": user.username}
    )
    refresh_token = create_refresh_token(
        subject=user.id,
        claims={"role": user.role, "username": user.username}
    )
    
    # Store session record with hashed token
    refresh_hash = hash_token(refresh_token)
    session_record = AuthSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        client_ip=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_revoked=False,
    )
    db.add(session_record)

    await create_audit_entry(
        db=db,
        action="LOGIN_SUCCESS",
        resource_type="AUTH",
        resource_id=session_record.id,
        actor_user_id=user.id,
        actor_username=user.username,
        client_ip=client_ip,
        status="SUCCESS",
        details={"role": user.role},
    )

    await db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    refresh_in: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """Validates refresh token against persistent active sessions and performs rotation."""
    token_str = refresh_in.refresh_token
    payload = decode_access_token(token_str)
    if not payload or payload.get("type") != "refresh" or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = payload["sub"]
    token_hash = hash_token(token_str)
    
    # Query database for session
    result = await db.execute(
        select(AuthSession).where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.user_id == user_id
        )
    )
    session_record = result.scalar_one_or_none()
    
    now = datetime.now(timezone.utc)
    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or already terminated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if session_record.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    expires_at = session_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at < now:
        session_record.is_revoked = True
        session_record.revoked_at = now
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user or not user.is_active:
        session_record.is_revoked = True
        session_record.revoked_at = now
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account inactive or removed",
        )

    # Rotate refresh token: revoke current session and issue new session
    session_record.is_revoked = True
    session_record.revoked_at = now

    new_access_token = create_access_token(
        subject=user.id,
        claims={"role": user.role, "username": user.username}
    )
    new_refresh_token = create_refresh_token(
        subject=user.id,
        claims={"role": user.role, "username": user.username}
    )
    
    client_ip = request.client.host if request.client else session_record.client_ip
    user_agent = request.headers.get("user-agent") or session_record.user_agent

    new_session = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(new_refresh_token),
        client_ip=client_ip,
        user_agent=user_agent[:500] if user_agent else None,
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        is_revoked=False,
    )
    db.add(new_session)
    await db.commit()

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    logout_req: Optional[LogoutRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Revokes active authentication session(s) and logs audit event."""
    now = datetime.now(timezone.utc)
    if logout_req and logout_req.refresh_token:
        # Revoke specific session
        t_hash = hash_token(logout_req.refresh_token)
        await db.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == current_user.id,
                AuthSession.refresh_token_hash == t_hash
            )
            .values(is_revoked=True, revoked_at=now)
        )
    else:
        # Revoke all active sessions for this user
        await db.execute(
            update(AuthSession)
            .where(
                AuthSession.user_id == current_user.id,
                AuthSession.is_revoked == False
            )
            .values(is_revoked=True, revoked_at=now)
        )
        
    await create_audit_entry(
        db=db,
        action="LOGOUT",
        resource_type="AUTH",
        resource_id=current_user.id,
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        status="SUCCESS",
        details={"message": "Sessions revoked successfully"},
    )
    await db.commit()

    return {"message": "Successfully logged out and session revoked", "user": current_user.username}


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Retrieves the authenticated user profile."""
    return current_user


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Admin-only endpoint to list registered system users."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()
