from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class ShotPatternPositionBase(BaseModel):
    shot_number: int
    x_normalized: Optional[Decimal] = None
    y_normalized: Optional[Decimal] = None
    x_mm: Optional[Decimal] = None
    y_mm: Optional[Decimal] = None
    impact_angle_degrees: Decimal = 0
    location_label: Optional[str] = None
    notes: Optional[str] = None


class ShotPatternPositionCreate(ShotPatternPositionBase):
    pass


class ShotPatternPosition(ShotPatternPositionBase):
    id: UUID
    shot_pattern_id: UUID

    class Config:
        from_attributes = True


class ShotPatternBase(BaseModel):
    name: str
    vest_type: Optional[str] = None
    protocol: Optional[str] = None
    description: Optional[str] = None


class ShotPatternCreate(ShotPatternBase):
    positions: list[ShotPatternPositionCreate] = []


class ShotPatternUpdate(BaseModel):
    name: Optional[str] = None
    vest_type: Optional[str] = None
    protocol: Optional[str] = None
    description: Optional[str] = None


class ShotPatternInDB(ShotPatternBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ShotPattern(ShotPatternInDB):
    positions: list[ShotPatternPosition] = []
