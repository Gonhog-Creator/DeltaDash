from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Any


class AuditLogBase(BaseModel):
    user_id: UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: UUID | None = None
    before_json: dict[str, Any] | None = None
    after_json: dict[str, Any] | None = None


class AuditLogInDB(AuditLogBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLog(AuditLogInDB):
    pass
