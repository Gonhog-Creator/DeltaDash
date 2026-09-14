from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from uuid import UUID
from decimal import Decimal


class ManualEntryShot(BaseModel):
    shot_number: str
    side: Optional[str] = None
    vest_number: Optional[str] = None
    angle_degrees: Optional[Decimal] = None
    caliber: Optional[str] = None
    velocity_m_s: Optional[Decimal] = None
    trauma_mm: Optional[Decimal] = None
    trauma_qualitative: Optional[str] = None
    protection_level: Optional[str] = None
    temperature_c: Optional[Decimal] = None
    humidity_percent: Optional[Decimal] = None


class ManualEntryVestTab(BaseModel):
    vest_number: Optional[str] = None
    size: Optional[str] = None
    conditioning: Optional[str] = None
    ballistic_limit: Optional[bool] = False
    shots: List[ManualEntryShot] = []


class ManualEntryRequest(BaseModel):
    name: str
    test_date: Optional[date] = None
    lab_name: Optional[str] = None
    protocol: Optional[str] = None
    clay_temperature_c: Optional[Decimal] = None
    ambient_temperature_c: Optional[Decimal] = None
    humidity_percent: Optional[Decimal] = None
    vest_id: Optional[str] = None
    geometry_id: str
    is_official: Optional[bool] = False
    certification_number: Optional[str] = None
    notes: Optional[str] = None
    protection_level: Optional[str] = None
    vest_tabs: List[ManualEntryVestTab] = []


class ManualEntryResponse(BaseModel):
    parent_session_id: str
    child_session_ids: List[str] = []
    total_shots: int
