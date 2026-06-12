from sqlalchemy import Column, String, Numeric, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class Geometry(Base):
    __tablename__ = "geometries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)  # e.g., "DELTA II", "STOP III"
    description = Column(String)
    vest_type = Column(String, index=True)  # e.g., "Soft", "Hard", "Hybrid"
    
    # Surface areas by size (in m²)
    # Format: {"XS": {"front": 0.152, "back": 0.155}, "S": {"front": 0.152, "back": 0.155}, ...}
    surface_areas = Column(JSON, nullable=False)
    
    # Available sizes for this geometry
    available_sizes = Column(JSON, nullable=False)  # ["XS", "S", "M", "L", "XL", "XXL"]
    
    # Whether this geometry includes hard plates
    includes_hard_plates = Column(Boolean, default=False)
    
    # Outer carrier fabric (for the vest cover)
    outer_carrier_material_id = Column(UUID(as_uuid=True), nullable=True)
    outer_carrier_layer_count = Column(Integer, nullable=True)
    
    # Notes
    notes = Column(String)
