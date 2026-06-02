from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


class TestSessionBase(BaseModel):
    name: str
    test_date: Optional[date] = None
    lab_name: Optional[str] = None
    protocol: Optional[str] = None
    clay_temperature_c: Optional[Decimal] = None
    ambient_temperature_c: Optional[Decimal] = None
    humidity_percent: Optional[Decimal] = None
    conditioning: Optional[str] = None
    size: Optional[str] = None
    ballistic_limit: Optional[bool] = None
    parent_test_group_id: Optional[UUID] = None
    vest_id: Optional[UUID] = None
    excel_file_path: Optional[str] = None
    notes: Optional[str] = None
    is_official: Optional[bool] = False


class TestSessionCreate(TestSessionBase):
    pass


class TestSessionUpdate(BaseModel):
    name: Optional[str] = None
    test_date: Optional[date] = None
    lab_name: Optional[str] = None
    protocol: Optional[str] = None
    clay_temperature_c: Optional[Decimal] = None
    ambient_temperature_c: Optional[Decimal] = None
    humidity_percent: Optional[Decimal] = None
    conditioning: Optional[str] = None
    size: Optional[str] = None
    ballistic_limit: Optional[bool] = None
    parent_test_group_id: Optional[UUID] = None
    vest_id: Optional[UUID] = None
    excel_file_path: Optional[str] = None
    notes: Optional[str] = None
    is_official: Optional[bool] = None


class TestSessionInDB(TestSessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    vest_name: Optional[str] = None
    vest_code: Optional[str] = None

    class Config:
        from_attributes = True


class TestSession(TestSessionInDB):
    pass
