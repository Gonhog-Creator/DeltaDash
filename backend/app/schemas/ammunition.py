from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class AmmunitionBase(BaseModel):
    name: str
    caliber: str | None = None
    projectile_type: str | None = None
    projectile_mass_grains: Decimal | None = Field(None, ge=0)
    projectile_mass_grams: Decimal | None = Field(None, ge=0)
    nominal_velocity_fps: Decimal | None = Field(None, ge=0)
    nominal_velocity_m_s: Decimal | None = Field(None, ge=0)
    manufacturer: str | None = None
    lot_number: str | None = None
    standard_reference: str | None = None
    notes: str | None = None


class AmmunitionCreate(AmmunitionBase):
    pass


class AmmunitionUpdate(BaseModel):
    name: str | None = None
    caliber: str | None = None
    projectile_type: str | None = None
    projectile_mass_grains: Decimal | None = Field(None, ge=0)
    projectile_mass_grams: Decimal | None = Field(None, ge=0)
    nominal_velocity_fps: Decimal | None = Field(None, ge=0)
    nominal_velocity_m_s: Decimal | None = Field(None, ge=0)
    manufacturer: str | None = None
    lot_number: str | None = None
    standard_reference: str | None = None
    notes: str | None = None


class AmmunitionInDB(AmmunitionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Ammunition(AmmunitionInDB):
    pass


class AmmunitionListItem(BaseModel):
    id: UUID
    name: str
    caliber: str | None
    projectile_type: str | None
    nominal_velocity_fps: Decimal | None

    class Config:
        from_attributes = True
