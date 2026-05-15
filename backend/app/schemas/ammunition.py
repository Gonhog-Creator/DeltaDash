from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class AmmunitionBase(BaseModel):
    name: str
    caliber: Optional[str] = None
    caliber_unit: str  # 'mm' or 'inches' - required
    caliber_diameter_mm: Optional[Decimal] = Field(None, ge=0)
    caliber_length_mm: Optional[Decimal] = Field(None, ge=0)
    caliber_inch: Optional[Decimal] = Field(None, ge=0)
    projectile_type: Optional[str] = None
    projectile_mass_grains: Decimal = Field(..., gt=0)  # required
    projectile_mass_grams: Optional[Decimal] = Field(None, ge=0)
    nominal_velocity_fps: Decimal = Field(..., gt=0)  # required
    nominal_velocity_m_s: Optional[Decimal] = Field(None, ge=0)
    manufacturer: Optional[str] = None
    lot_number: Optional[str] = None
    standard_reference: Optional[str] = None
    notes: Optional[str] = None


class AmmunitionCreate(AmmunitionBase):
    pass


class AmmunitionUpdate(BaseModel):
    name: Optional[str] = None
    caliber: Optional[str] = None
    caliber_unit: Optional[str] = None  # 'mm' or 'inches'
    caliber_diameter_mm: Optional[Decimal] = Field(None, ge=0)
    caliber_length_mm: Optional[Decimal] = Field(None, ge=0)
    caliber_inch: Optional[Decimal] = Field(None, ge=0)
    projectile_type: Optional[str] = None
    projectile_mass_grains: Optional[Decimal] = Field(None, ge=0)
    projectile_mass_grams: Optional[Decimal] = Field(None, ge=0)
    nominal_velocity_fps: Optional[Decimal] = Field(None, ge=0)
    nominal_velocity_m_s: Optional[Decimal] = Field(None, ge=0)
    manufacturer: Optional[str] = None
    lot_number: Optional[str] = None
    standard_reference: Optional[str] = None
    notes: Optional[str] = None


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
    caliber: Optional[str]
    caliber_unit: Optional[str]
    caliber_diameter_mm: Optional[Decimal]
    caliber_length_mm: Optional[Decimal]
    caliber_inch: Optional[Decimal]
    projectile_type: Optional[str]
    projectile_mass_grains: Optional[Decimal]
    nominal_velocity_fps: Optional[Decimal]
    manufacturer: Optional[str]

    class Config:
        from_attributes = True
