from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID


class AmmunitionConfig(BaseModel):
    ammunition_id: str
    reference_velocity_m_s: float
    velocity_window_m_s: Optional[float] = None  # plus/minus value
    shots_per_panel: int = 6


class ProtocolLevel(BaseModel):
    level_name: str
    ammunition_config: List[AmmunitionConfig]


class ProtocolBase(BaseModel):
    name: str
    description: Optional[str] = None
    levels_config: Optional[List[ProtocolLevel]] = None


class ProtocolCreate(ProtocolBase):
    pass


class ProtocolUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    levels_config: Optional[List[ProtocolLevel]] = None


class Protocol(ProtocolBase):
    id: UUID

    class Config:
        from_attributes = True
