from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class ShotBase(BaseModel):
    test_session_id: Optional[UUID] = None
    panel_id: Optional[UUID] = None
    ammunition_id: Optional[UUID] = None
    shot_pattern_position_id: Optional[UUID] = None
    shot_number: Optional[int] = None
    measured_velocity_fps: Optional[Decimal] = Field(None, ge=0)
    measured_velocity_m_s: Optional[Decimal] = Field(None, ge=0)
    impact_angle_degrees: Optional[Decimal] = None
    bfd_mm: Optional[Decimal] = Field(None, ge=0)
    penetration: Optional[bool] = None
    partial_penetration: Optional[bool] = None
    trauma_score: Optional[Decimal] = None
    pass_fail: Optional[str] = None
    distance_m: Optional[Decimal] = Field(None, ge=0)
    yaw_observed: Optional[bool] = None
    edge_hit: Optional[bool] = None
    anomaly_flag: bool = False
    anomaly_notes: Optional[str] = None
    raw_source_file: Optional[str] = None
    raw_row_number: Optional[int] = None


class ShotCreate(ShotBase):
    pass


class ShotUpdate(BaseModel):
    test_session_id: Optional[UUID] = None
    panel_id: Optional[UUID] = None
    ammunition_id: Optional[UUID] = None
    shot_pattern_position_id: Optional[UUID] = None
    shot_number: Optional[int] = None
    measured_velocity_fps: Optional[Decimal] = Field(None, ge=0)
    measured_velocity_m_s: Optional[Decimal] = Field(None, ge=0)
    impact_angle_degrees: Optional[Decimal] = None
    bfd_mm: Optional[Decimal] = Field(None, ge=0)
    penetration: Optional[bool] = None
    partial_penetration: Optional[bool] = None
    trauma_score: Optional[Decimal] = None
    pass_fail: Optional[str] = None
    distance_m: Optional[Decimal] = Field(None, ge=0)
    yaw_observed: Optional[bool] = None
    edge_hit: Optional[bool] = None
    anomaly_flag: Optional[bool] = None
    anomaly_notes: Optional[str] = None
    raw_source_file: Optional[str] = None
    raw_row_number: Optional[int] = None


class ShotInDB(ShotBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Shot(ShotInDB):
    pass
