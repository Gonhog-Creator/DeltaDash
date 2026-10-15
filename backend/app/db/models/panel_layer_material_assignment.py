from sqlalchemy import Column, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class PanelLayerMaterialAssignment(Base):
    """Maps a contiguous block of layers of a physical tested panel to the
    material lot/roll it was cut from. This is what lets a roll-level property
    draw be shared across all layers coming from that roll."""

    __tablename__ = "panel_layer_material_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    panel_id = Column(UUID(as_uuid=True), ForeignKey("armor_panels.id"), nullable=False, index=True)
    layer_start = Column(Integer, nullable=False)
    layer_end = Column(Integer, nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False)
    material_lot_id = Column(UUID(as_uuid=True), ForeignKey("material_lots.id"), nullable=True)
    roll_id = Column(UUID(as_uuid=True), ForeignKey("material_rolls.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
