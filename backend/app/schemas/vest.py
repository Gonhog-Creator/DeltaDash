from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional, Dict, List


class ModelDocumentSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)
    id: UUID
    vest_id: UUID
    name: str
    original_name: Optional[str] = None


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
    is_female: Optional[bool] = False
    threat_level: Optional[str] = None
    protection_class: Optional[str] = None
    total_layers: Optional[int] = Field(None, ge=0)
    total_thickness_mm: Optional[Decimal] = Field(None, ge=0)
    sizes: Optional[Dict[str, float]] = None
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    compatible_geometry_ids: Optional[List[str]] = None
    weight_g: Optional[Decimal] = Field(None, ge=0)
    trauma_homologation: Optional[Dict] = None
    flexibility_rating: Optional[bool] = False
    is_panel_sewn: Optional[bool] = None
    size_curve: Optional[Dict] = None
    composition: Optional[str] = None
    is_catalog_model: bool = False
    notes: Optional[str] = None


class VestCreate(VestBase):
    layers: list[VestLayerCreate] = []


class VestUpdate(BaseModel):
    vest_code: Optional[str] = None
    vest_type: Optional[str] = None
    is_female: Optional[bool] = None
    threat_level: Optional[str] = None
    protection_class: Optional[str] = None
    total_layers: Optional[int] = Field(None, ge=0)
    total_thickness_mm: Optional[Decimal] = Field(None, ge=0)
    sizes: Optional[Dict[str, float]] = None
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    compatible_geometry_ids: Optional[List[str]] = None
    weight_g: Optional[Decimal] = Field(None, ge=0)
    trauma_homologation: Optional[Dict] = None
    flexibility_rating: Optional[bool] = None
    is_panel_sewn: Optional[bool] = None
    size_curve: Optional[Dict] = None
    composition: Optional[str] = None
    is_catalog_model: Optional[bool] = None
    notes: Optional[str] = None


class VestInDB(VestBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Vest(VestInDB):
    layers: list[VestLayer] = []
    documents: list[ModelDocumentSchema] = []


class VestListItem(BaseModel):
    id: UUID
    vest_code: str
    vest_type: Optional[str]
    is_female: Optional[bool] = False
    threat_level: Optional[str]
    protection_class: Optional[str]
    total_layers: Optional[int]
    total_thickness_mm: Optional[Decimal]
    sizes: Optional[Dict[str, float]] = None
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    compatible_geometry_ids: Optional[List[str]] = None
    weight_g: Optional[Decimal] = None
    trauma_homologation: Optional[Dict] = None
    flexibility_rating: bool = False
    is_panel_sewn: Optional[bool] = None
    size_curve: Optional[Dict] = None
    created_by_username: Optional[str] = None
    composition: Optional[str] = None
    is_catalog_model: bool = False

    class Config:
        from_attributes = True
