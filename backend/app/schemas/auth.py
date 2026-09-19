"""Foresight AI - Authentication & User API Schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    role: str = Field(default="analyst")


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserResponse(UserBase):
    id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
    role: Optional[str] = None
    token_type: Optional[str] = None


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

