from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Optional


class ArmorPanelLayerBase(BaseModel):
    material_id: UUID | None = None
    orientation_degrees: Decimal | None = None
    layer_count: int = 1
    notes: str | None = None


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
    test_session_id: UUID | None = None
    vest_type: str | None = None
    panel_shape: str | None = None
    panel_width_mm: Decimal | None = Field(None, ge=0)
    panel_height_mm: Decimal | None = Field(None, ge=0)
    panel_thickness_mm: Decimal | None = Field(None, ge=0)
    total_layers: int | None = Field(None, ge=0)
    total_areal_density_g_m2: Decimal | None = Field(None, ge=0)
    total_mass_g: Decimal | None = Field(None, ge=0)
    construction_notes: str | None = None
    stitch_pattern: str | None = None
    curvature: str | None = None
    backing_material: str | None = None


class ArmorPanelCreate(ArmorPanelBase):
    layers: list[ArmorPanelLayerCreate] = []


class ArmorPanelUpdate(BaseModel):
    panel_code: str | None = None
    vest_type: str | None = None
    panel_shape: str | None = None
    panel_width_mm: Decimal | None = Field(None, ge=0)
    panel_height_mm: Decimal | None = Field(None, ge=0)
    panel_thickness_mm: Decimal | None = Field(None, ge=0)
    total_layers: int | None = Field(None, ge=0)
    total_areal_density_g_m2: Decimal | None = Field(None, ge=0)
    total_mass_g: Decimal | None = Field(None, ge=0)
    construction_notes: str | None = None
    stitch_pattern: str | None = None
    curvature: str | None = None
    backing_material: str | None = None


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
    vest_type: str | None
    total_layers: int | None
    total_areal_density_g_m2: Decimal | None

    class Config:
        from_attributes = True
