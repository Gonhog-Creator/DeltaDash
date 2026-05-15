from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional


class ArmorPanelLayerBase(BaseModel):
    material_id: Optional[UUID] = None
    orientation_degrees: Optional[Decimal] = None
    layer_count: int = 1
    notes: Optional[str] = None


class ArmorPanelLayerCreate(ArmorPanelLayerBase):
    layer_index: int


class ArmorPanelLayer(ArmorPanelLayerBase):
    id: UUID
    panel_id: UUID
    layer_index: int

    class Config:
        from_attributes = True


class ArmorPanelBase(BaseModel):
    panel_code: str
    test_session_id: Optional[UUID] = None
    vest_type: Optional[str] = None
    panel_shape: Optional[str] = None
    panel_width_mm: Optional[Decimal] = Field(None, ge=0)
    panel_height_mm: Optional[Decimal] = Field(None, ge=0)
    panel_thickness_mm: Optional[Decimal] = Field(None, ge=0)
    total_layers: Optional[int] = Field(None, ge=0)
    total_areal_density_g_m2: Optional[Decimal] = Field(None, ge=0)
    total_mass_g: Optional[Decimal] = Field(None, ge=0)
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    curvature: Optional[str] = None
    backing_material: Optional[str] = None


class ArmorPanelCreate(ArmorPanelBase):
    layers: list[ArmorPanelLayerCreate] = []


class ArmorPanelUpdate(BaseModel):
    panel_code: Optional[str] = None
    vest_type: Optional[str] = None
    panel_shape: Optional[str] = None
    panel_width_mm: Optional[Decimal] = Field(None, ge=0)
    panel_height_mm: Optional[Decimal] = Field(None, ge=0)
    panel_thickness_mm: Optional[Decimal] = Field(None, ge=0)
    total_layers: Optional[int] = Field(None, ge=0)
    total_areal_density_g_m2: Optional[Decimal] = Field(None, ge=0)
    total_mass_g: Optional[Decimal] = Field(None, ge=0)
    construction_notes: Optional[str] = None
    stitch_pattern: Optional[str] = None
    curvature: Optional[str] = None
    backing_material: Optional[str] = None


class ArmorPanelInDB(ArmorPanelBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArmorPanel(ArmorPanelInDB):
    layers: list[ArmorPanelLayer] = []


class ArmorPanelListItem(BaseModel):
    id: UUID
    panel_code: str
    vest_type: Optional[str]
    total_layers: Optional[int]
    total_areal_density_g_m2: Optional[Decimal]

    class Config:
        from_attributes = True
