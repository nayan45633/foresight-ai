"""Foresight AI - Audit Logging API Schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    actor: str
    actor_user_id: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    details: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
