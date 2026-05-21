from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional, Dict


class VestLayerBase(BaseModel):
    material_id: Optional[UUID] = None
    layer_count: int = 1
    notes: Optional[str] = None


class VestLayerCreate(VestLayerBase):
    layer_index: int


class VestLayer(VestLayerBase):
    id: UUID
    vest_id: UUID
    layer_index: int

    class Config:
        from_attributes = True


class VestBase(BaseModel):
    vest_code: str
    vest_type: Optional[str] = None
    threat_level: Optional[str] = None
    protection_class: Optional[str] = None
    total_layers: Optional[int] = Field(None, ge=0)
    total_thickness_mm: Optional[Decimal] = Field(None, ge=0)
    sizes: Optional[Dict[str, float]] = None
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    backing_material: Optional[str] = None
    notes: Optional[str] = None


class VestCreate(VestBase):
    layers: list[VestLayerCreate] = []


class VestUpdate(BaseModel):
    vest_code: Optional[str] = None
    vest_type: Optional[str] = None
    threat_level: Optional[str] = None
    protection_class: Optional[str] = None
    total_layers: Optional[int] = Field(None, ge=0)
    total_thickness_mm: Optional[Decimal] = Field(None, ge=0)
    sizes: Optional[Dict[str, float]] = None
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    backing_material: Optional[str] = None
    notes: Optional[str] = None


class VestInDB(VestBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Vest(VestInDB):
    layers: list[VestLayer] = []


class VestListItem(BaseModel):
    id: UUID
    vest_code: str
    vest_type: Optional[str]
    threat_level: Optional[str]
    protection_class: Optional[str]
    total_layers: Optional[int]
    total_thickness_mm: Optional[Decimal]
    sizes: Optional[Dict[str, float]] = None
    created_by_username: Optional[str] = None

    class Config:
        from_attributes = True
