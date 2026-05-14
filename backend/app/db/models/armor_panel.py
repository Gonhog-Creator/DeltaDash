from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class ArmorPanel(Base):
    __tablename__ = "armor_panels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey("test_sessions.id"), nullable=True)
    panel_code = Column(String, nullable=False, index=True)
    vest_type = Column(String)
    panel_shape = Column(String)
    panel_width_mm = Column(Numeric(10, 2))
    panel_height_mm = Column(Numeric(10, 2))
    panel_thickness_mm = Column(Numeric(10, 3))
    total_layers = Column(Integer)
    total_areal_density_g_m2 = Column(Numeric(10, 2))
    total_mass_g = Column(Numeric(10, 2))
    construction_notes = Column(String)
    stitch_pattern = Column(String)
    curvature = Column(String)
    backing_material = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
