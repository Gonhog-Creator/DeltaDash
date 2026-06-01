from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional, List


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
    ply_count: Optional[int] = None
    ply_orientations: Optional[List[Decimal]] = None
    areal_density_g_m2: Optional[Decimal] = Field(None, ge=0)
    thickness_mm: Optional[Decimal] = Field(None, ge=0)
    thickness_tolerance_mm: Optional[str] = None
    density_g_cm3: Optional[Decimal] = Field(None, ge=0)
    tensile_strength_mpa: Optional[Decimal] = Field(None, ge=0)
    modulus_gpa: Optional[Decimal] = Field(None, ge=0)
    elongation_longitudinal_percent: Optional[Decimal] = Field(None, ge=0)
    elongation_longitudinal_error_percent: Optional[Decimal] = Field(None, ge=0)
    force_longitudinal_newtons: Optional[Decimal] = Field(None, ge=0)
    force_longitudinal_error_percent: Optional[Decimal] = Field(None, ge=0)
    elongation_transverse_percent: Optional[Decimal] = Field(None, ge=0)
    elongation_transverse_error_percent: Optional[Decimal] = Field(None, ge=0)
    force_transverse_newtons: Optional[Decimal] = Field(None, ge=0)
    force_transverse_error_percent: Optional[Decimal] = Field(None, ge=0)
    stretch_test_length: Optional[str] = None
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
    ply_count: Optional[int] = None
    ply_orientations: Optional[List[Decimal]] = None
    areal_density_g_m2: Optional[Decimal] = Field(None, ge=0)
    thickness_mm: Optional[Decimal] = Field(None, ge=0)
    thickness_tolerance_mm: Optional[str] = None
    density_g_cm3: Optional[Decimal] = Field(None, ge=0)
    tensile_strength_mpa: Optional[Decimal] = Field(None, ge=0)
    modulus_gpa: Optional[Decimal] = Field(None, ge=0)
    elongation_longitudinal_percent: Optional[Decimal] = Field(None, ge=0)
    elongation_longitudinal_error_percent: Optional[Decimal] = Field(None, ge=0)
    force_longitudinal_newtons: Optional[Decimal] = Field(None, ge=0)
    force_longitudinal_error_percent: Optional[Decimal] = Field(None, ge=0)
    elongation_transverse_percent: Optional[Decimal] = Field(None, ge=0)
    elongation_transverse_error_percent: Optional[Decimal] = Field(None, ge=0)
    force_transverse_newtons: Optional[Decimal] = Field(None, ge=0)
    force_transverse_error_percent: Optional[Decimal] = Field(None, ge=0)
    stretch_test_length: Optional[str] = None
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
    ply_count: Optional[int] = None
    ply_orientations: Optional[List[Decimal]] = None
    areal_density_g_m2: Optional[Decimal]
    thickness_mm: Optional[Decimal]
    elongation_longitudinal_percent: Optional[Decimal] = None
    elongation_longitudinal_error_percent: Optional[Decimal] = None
    force_longitudinal_newtons: Optional[Decimal] = None
    force_longitudinal_error_percent: Optional[Decimal] = None
    elongation_transverse_percent: Optional[Decimal] = None
    elongation_transverse_error_percent: Optional[Decimal] = None
    force_transverse_newtons: Optional[Decimal] = None
    force_transverse_error_percent: Optional[Decimal] = None
    stretch_test_length: Optional[str] = None
    material_function: Optional[str]
    created_by_username: Optional[str]
    mss_file_path: Optional[str]
    sds_file_path: Optional[str]

    class Config:
        from_attributes = True
