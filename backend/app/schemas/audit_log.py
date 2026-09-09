from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Any, Optional


class AuditLogBase(BaseModel):
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    before_json: Optional[dict] = None
    after_json: Optional[dict] = None
    source: Optional[str] = None


class AuditLogInDB(AuditLogBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLog(AuditLogInDB):
    pass
