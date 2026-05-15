from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class ProtocolBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProtocolCreate(ProtocolBase):
    pass


class ProtocolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class Protocol(ProtocolBase):
    id: UUID

    class Config:
        from_attributes = True
