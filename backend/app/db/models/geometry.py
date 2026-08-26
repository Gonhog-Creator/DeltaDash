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

    # Whether this geometral is approved for production
    is_approved = Column(Boolean, default=False)

    # Detailed size measurements (curva de talles)
    # Format: { "S": {"chest_mm": 960, "waist_mm": 860, "length_mm": 480, "shoulder_mm": 420}, ... }
    size_measurements = Column(JSON, nullable=True)

    # Single geometry PDF (e.g., spec sheet with image and sizing table)
    # Format: {"path": "uuid.pdf", "original_name": "geometry.pdf"}
    pdf_document = Column(JSON, nullable=True)

    # Outer carrier fabric (for the vest cover)
    outer_carrier_material_id = Column(UUID(as_uuid=True), nullable=True)
    outer_carrier_layer_count = Column(Integer, nullable=True)

    # URL or path to the panel diagram image
    image_url = Column(String, nullable=True)

    # Compatibility text (e.g., "Compatible con: STOP II - STOP III - ULTRA STOP III")
    compatibility = Column(String, nullable=True)

    # Notes
    notes = Column(String)
