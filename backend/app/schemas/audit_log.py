from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Any, Optional


class AuditLogBase(BaseModel):
    user_id: Optional[UUID] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    before_json: dict[str, Any] | None = None
    after_json: dict[str, Any] | None = None


class AuditLogInDB(AuditLogBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLog(AuditLogInDB):
    pass
