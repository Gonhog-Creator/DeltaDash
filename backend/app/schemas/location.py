from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class LocationBase(BaseModel):
    name: str
    address: Optional[str] = None


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class Location(LocationBase):
    id: UUID

    class Config:
        from_attributes = True
