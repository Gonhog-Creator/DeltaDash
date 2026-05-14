from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class ArmorPanelLayer(Base):
    __tablename__ = "armor_panel_layers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    panel_id = Column(UUID(as_uuid=True), ForeignKey("armor_panels.id", ondelete="CASCADE"), nullable=False)
    layer_index = Column(Integer, nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=True)
    orientation_degrees = Column(Numeric(5, 2))
    layer_count = Column(Integer, nullable=False, default=1)
    notes = Column(String)
