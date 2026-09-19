"""Foresight AI - Security, Hashing and JWT Token Management."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import bcrypt
import jwt
from app.core.config import settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash."""
    plain_bytes = plain_password.encode("utf-8")
    # Truncate to 72 bytes as per bcrypt specification
    plain_bytes = plain_bytes[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Generates a secure salted bcrypt hash for a given password."""
    password_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def create_access_token(
    subject: Union[str, Any],
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a signed JSON Web Token (JWT) with expiration and subject claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    import uuid
    to_encode: Dict[str, Any] = {
        "exp": expire,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "sub": str(subject),
        "type": "access",
    }
    if claims:
        to_encode.update(claims)
        
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    claims: Optional[Dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a signed long-lived refresh token with expiration and subject claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
    import uuid
    to_encode: Dict[str, Any] = {
        "exp": expire,
        "iat": now,
        "jti": uuid.uuid4().hex,
        "sub": str(subject),
        "type": "refresh",
    }
    if claims:
        to_encode.update(claims)
        
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates a JWT token signature and expiration."""
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded
    except jwt.PyJWTError:
        return None


def hash_token(token: str) -> str:
    """Computes a SHA-256 hash of a token string for indexed session storage."""
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

