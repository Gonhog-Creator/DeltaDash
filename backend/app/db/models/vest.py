from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, func, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class Vest(Base):
    __tablename__ = "vests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vest_code = Column(String, nullable=False, index=True)
    vest_type = Column(String)
    threat_level = Column(String)
    protection_class = Column(String)
    total_layers = Column(Integer)
    total_thickness_mm = Column(Numeric(10, 3))
    sizes = Column(JSON)
    construction_notes = Column(String)
    stitch_pattern = Column(String)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to layers
    layers = relationship("VestLayer", backref="vest", cascade="all, delete-orphan", order_by="VestLayer.layer_index")
