from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class ShotBase(BaseModel):
    test_session_id: UUID | None = None
    panel_id: UUID | None = None
    ammunition_id: UUID | None = None
    shot_pattern_position_id: UUID | None = None
    shot_number: int | None = None
    measured_velocity_fps: Decimal | None = Field(None, ge=0)
    measured_velocity_m_s: Decimal | None = Field(None, ge=0)
    impact_angle_degrees: Decimal | None = None
    bfd_mm: Decimal | None = Field(None, ge=0)
    penetration: bool | None = None
    partial_penetration: bool | None = None
    trauma_score: Decimal | None = None
    pass_fail: str | None = None
    distance_m: Decimal | None = Field(None, ge=0)
    yaw_observed: bool | None = None
    edge_hit: bool | None = None
    anomaly_flag: bool = False
    anomaly_notes: str | None = None
    raw_source_file: str | None = None
    raw_row_number: int | None = None


class ShotCreate(ShotBase):
    pass


class ShotUpdate(BaseModel):
    test_session_id: UUID | None = None
    panel_id: UUID | None = None
    ammunition_id: UUID | None = None
    shot_pattern_position_id: UUID | None = None
    shot_number: int | None = None
    measured_velocity_fps: Decimal | None = Field(None, ge=0)
    measured_velocity_m_s: Decimal | None = Field(None, ge=0)
    impact_angle_degrees: Decimal | None = None
    bfd_mm: Decimal | None = Field(None, ge=0)
    penetration: bool | None = None
    partial_penetration: bool | None = None
    trauma_score: Decimal | None = None
    pass_fail: str | None = None
    distance_m: Decimal | None = Field(None, ge=0)
    yaw_observed: bool | None = None
    edge_hit: bool | None = None
    anomaly_flag: bool | None = None
    anomaly_notes: str | None = None
    raw_source_file: str | None = None
    raw_row_number: int | None = None


class ShotInDB(ShotBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Shot(ShotInDB):
    pass
