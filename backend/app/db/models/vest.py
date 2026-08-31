from sqlalchemy import Column, String, Text, Numeric, Integer, DateTime, ForeignKey, func, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class Vest(Base):
    __tablename__ = "vests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vest_code = Column(String, nullable=False, index=True)
    vest_type = Column(String)
    is_female = Column(Boolean, default=False)
    threat_level = Column(String)
    protection_class = Column(String)
    total_layers = Column(Integer)
    total_thickness_mm = Column(Numeric(10, 3))
    sizes = Column(JSON)
    construction_notes = Column(String)
    stitch_pattern = Column(String)

    # Pliego técnico matching fields
    weight_g = Column(Numeric(10, 2), nullable=True)
    trauma_homologation = Column(JSON, nullable=True)  # { "level": "RB3", "backface_mm": 25.0, "ammunition": ".44 MAG", "certified": true }
    flexibility_rating = Column(Boolean, default=False, nullable=False)
    is_panel_sewn = Column(Boolean, nullable=True)
    size_curve = Column(JSON, nullable=True)  # { "S": {"chest_mm": 960, "waist_mm": 860, "length_mm": 480}, ... }

    # Merged from vest_models
    composition = Column(Text, nullable=True)
    is_catalog_model = Column(Boolean, default=False, nullable=False)

    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to layers
    layers = relationship("VestLayer", backref="vest", cascade="all, delete-orphan", order_by="VestLayer.layer_index")
    # Relationship to documents (merged from vest_models)
    documents = relationship("ModelDocument", back_populates="vest", cascade="all, delete-orphan")
