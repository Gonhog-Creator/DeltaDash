from pydantic import BaseModel
from datetime import datetime, date
from uuid import UUID
from decimal import Decimal


class TestSessionBase(BaseModel):
    name: str
    test_date: date | None = None
    lab_name: str | None = None
    operator: str | None = None
    protocol: str | None = None
    clay_temperature_c: Decimal | None = None
    ambient_temperature_c: Decimal | None = None
    humidity_percent: Decimal | None = None
    conditioning: str | None = None
    notes: str | None = None


class TestSessionCreate(TestSessionBase):
    pass


class TestSessionUpdate(BaseModel):
    name: str | None = None
    test_date: date | None = None
    lab_name: str | None = None
    operator: str | None = None
    protocol: str | None = None
    clay_temperature_c: Decimal | None = None
    ambient_temperature_c: Decimal | None = None
    humidity_percent: Decimal | None = None
    conditioning: str | None = None
    notes: str | None = None


class TestSessionInDB(TestSessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestSession(TestSessionInDB):
    pass
