from sqlalchemy import Column, String, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class GeometryMaterialConfig(Base):
    """
    Configuration of materials and accessories for a specific geometry and size.
    This allows customizing the material requirements per geometry/size combination.
    """
    __tablename__ = "geometry_material_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    geometry_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    size = Column(String, nullable=False, index=True)  # XS, S, M, L, XL, XXL, or "ALL" for all sizes
    
    # Material requirements
    # Format: [{"material_id": "uuid", "layer_count": 10, "notes": "front panel"}, ...]
    material_requirements = Column(JSONB, nullable=False, default=list)
    
    # Accessories (non-fabric items like velcro, zippers, etc.)
    # Format: [{"material_id": "uuid", "quantity_per_vest": 2.5, "unit": "meters", "notes": "hook velcro"}, ...]
    accessories = Column(JSONB, nullable=False, default=list)
    
    # Custom efficiency factor (overrides default 1.15)
    efficiency_factor = Column(Numeric(5, 2), nullable=True)
    
    # Notes
    notes = Column(String, nullable=True)
