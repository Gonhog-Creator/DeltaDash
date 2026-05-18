from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional


class ShotDataBase(BaseModel):
    test_session_id: UUID
    vest_number: Optional[str] = None
    side: Optional[str] = None
    angle_degrees: Optional[Decimal] = None
    shot_number: str
    protection_level: Optional[str] = None
    caliber: Optional[str] = None
    trauma_mm: Optional[Decimal] = None
    trauma_qualitative: Optional[str] = None
    velocity_m_s: Optional[Decimal] = None
    temperature_c: Optional[Decimal] = None
    humidity_percent: Optional[Decimal] = None


class ShotDataCreate(ShotDataBase):
    pass


class ShotDataInDB(ShotDataBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ShotData(ShotDataInDB):
    pass


class ShotDataUpdate(BaseModel):
    vest_number: Optional[str] = None
    side: Optional[str] = None
    angle_degrees: Optional[Decimal] = None
    shot_number: Optional[str] = None
    protection_level: Optional[str] = None
    caliber: Optional[str] = None
    trauma_mm: Optional[Decimal] = None
    trauma_qualitative: Optional[str] = None
    velocity_m_s: Optional[Decimal] = None
    temperature_c: Optional[Decimal] = None
    humidity_percent: Optional[Decimal] = None
