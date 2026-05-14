from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class MaterialBase(BaseModel):
    name: str
    normalized_name: str | None = None
    manufacturer: str | None = None
    supplier: str | None = None
    material_class: str | None = None
    fiber_type: str | None = None
    weave_type: str | None = None
    coating: str | None = None
    color: str | None = None
    areal_density_g_m2: Decimal | None = Field(None, ge=0)
    thickness_mm: Decimal | None = Field(None, ge=0)
    density_g_cm3: Decimal | None = Field(None, ge=0)
    tensile_strength_mpa: Decimal | None = Field(None, ge=0)
    modulus_gpa: Decimal | None = Field(None, ge=0)
    elongation_percent: Decimal | None = Field(None, ge=0)
    notes: str | None = None
    source_confidence: str | None = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: str | None = None
    normalized_name: str | None = None
    manufacturer: str | None = None
    supplier: str | None = None
    material_class: str | None = None
    fiber_type: str | None = None
    weave_type: str | None = None
    coating: str | None = None
    color: str | None = None
    areal_density_g_m2: Decimal | None = Field(None, ge=0)
    thickness_mm: Decimal | None = Field(None, ge=0)
    density_g_cm3: Decimal | None = Field(None, ge=0)
    tensile_strength_mpa: Decimal | None = Field(None, ge=0)
    modulus_gpa: Decimal | None = Field(None, ge=0)
    elongation_percent: Decimal | None = Field(None, ge=0)
    notes: str | None = None
    source_confidence: str | None = None


class MaterialInDB(MaterialBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Material(MaterialInDB):
    pass


class MaterialListItem(BaseModel):
    id: UUID
    name: str
    manufacturer: str | None
    material_class: str | None
    areal_density_g_m2: Decimal | None
    thickness_mm: Decimal | None

    class Config:
        from_attributes = True
