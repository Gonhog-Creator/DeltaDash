from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional


class MaterialBase(BaseModel):
    name: str
    normalized_name: Optional[str] = None
    manufacturer: Optional[str] = None
    supplier: Optional[str] = None
    material_class: Optional[str] = None
    fiber_type: Optional[str] = None
    weave_type: Optional[str] = None
    coating: Optional[str] = None
    color: Optional[str] = None
    areal_density_g_m2: Optional[Decimal] = Field(None, ge=0)
    thickness_mm: Optional[Decimal] = Field(None, ge=0)
    density_g_cm3: Optional[Decimal] = Field(None, ge=0)
    tensile_strength_mpa: Optional[Decimal] = Field(None, ge=0)
    modulus_gpa: Optional[Decimal] = Field(None, ge=0)
    elongation_percent: Optional[Decimal] = Field(None, ge=0)
    material_function: Optional[str] = None
    created_by_username: Optional[str] = None
    mss_file_path: Optional[str] = None
    sds_file_path: Optional[str] = None
    notes: Optional[str] = None
    source_confidence: Optional[str] = None


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    name: Optional[str] = None
    normalized_name: Optional[str] = None
    manufacturer: Optional[str] = None
    supplier: Optional[str] = None
    material_class: Optional[str] = None
    fiber_type: Optional[str] = None
    weave_type: Optional[str] = None
    coating: Optional[str] = None
    color: Optional[str] = None
    areal_density_g_m2: Optional[Decimal] = Field(None, ge=0)
    thickness_mm: Optional[Decimal] = Field(None, ge=0)
    density_g_cm3: Optional[Decimal] = Field(None, ge=0)
    tensile_strength_mpa: Optional[Decimal] = Field(None, ge=0)
    modulus_gpa: Optional[Decimal] = Field(None, ge=0)
    elongation_percent: Optional[Decimal] = Field(None, ge=0)
    material_function: Optional[str] = None
    created_by_username: Optional[str] = None
    mss_file_path: Optional[str] = None
    sds_file_path: Optional[str] = None
    notes: Optional[str] = None
    source_confidence: Optional[str] = None


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
    manufacturer: Optional[str]
    material_class: Optional[str]
    areal_density_g_m2: Optional[Decimal]
    thickness_mm: Optional[Decimal]
    material_function: Optional[str]
    created_by_username: Optional[str]
    mss_file_path: Optional[str]
    sds_file_path: Optional[str]

    class Config:
        from_attributes = True
