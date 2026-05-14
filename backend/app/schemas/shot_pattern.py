from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class ShotPatternPositionBase(BaseModel):
    shot_number: int
    x_normalized: Decimal | None = None
    y_normalized: Decimal | None = None
    x_mm: Decimal | None = None
    y_mm: Decimal | None = None
    impact_angle_degrees: Decimal = 0
    location_label: str | None = None
    notes: str | None = None


class ShotPatternPositionCreate(ShotPatternPositionBase):
    pass


class ShotPatternPosition(ShotPatternPositionBase):
    id: UUID
    shot_pattern_id: UUID

    class Config:
        from_attributes = True


class ShotPatternBase(BaseModel):
    name: str
    vest_type: str | None = None
    protocol: str | None = None
    description: str | None = None


class ShotPatternCreate(ShotPatternBase):
    positions: list[ShotPatternPositionCreate] = []


class ShotPatternUpdate(BaseModel):
    name: str | None = None
    vest_type: str | None = None
    protocol: str | None = None
    description: str | None = None


class ShotPatternInDB(ShotPatternBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ShotPattern(ShotPatternInDB):
    positions: list[ShotPatternPosition] = []
