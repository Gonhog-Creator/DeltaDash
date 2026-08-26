from sqlalchemy import Column, String, Numeric, Boolean, DateTime, ForeignKey, func, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class Cover(Base):
    """Vest cover (Funda) model — represents the outer carrier of a vest."""
    __tablename__ = "covers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cover_code = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)

    # Link to geometry (a cover is designed for a specific geometral)
    geometry_id = Column(UUID(as_uuid=True), ForeignKey("geometries.id"), nullable=True)

    # Fabric characteristics
    fabric_type = Column(String, nullable=True)  # e.g., "Cordura 500D", "NyCo"
    fabric_weight_g_m2 = Column(Numeric(10, 2), nullable=True)
    layer_count = Column(Integer, nullable=True)

    # Cover weight (total, including fabric + accessories)
    weight_g = Column(Numeric(10, 2), nullable=True)

    # Molle configuration
    has_molle = Column(Boolean, default=False)
    # e.g., [{"location": "front", "rows": 3, "columns": 6}, {"location": "back", "rows": 4, "columns": 6}]
    molle_config = Column(JSON, nullable=True)

    # Quick release (sueltos rápidos)
    has_quick_release = Column(Boolean, default=False)
    quick_release_type = Column(String, nullable=True)  # e.g., "Tubo", "Cinta", "Ladder"

    # Fin/aleta dimensions
    fin_height_mm = Column(Numeric(10, 2), nullable=True)
    fin_width_mm = Column(Numeric(10, 2), nullable=True)

    # Available sizes for this cover
    # e.g., ["S", "M", "L", "XL"]
    available_sizes = Column(JSON, nullable=True)

    # Compatible vest types
    # e.g., ["Soft", "Hybrid"]
    compatible_vest_types = Column(JSON, nullable=True)

    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to geometry
    geometry = relationship("Geometry", backref="covers")
