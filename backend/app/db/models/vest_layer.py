from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class VestLayer(Base):
    __tablename__ = "vest_layers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vest_id = Column(UUID(as_uuid=True), ForeignKey("vests.id", ondelete="CASCADE"), nullable=False)
    layer_index = Column(Integer, nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=True)
    layer_count = Column(Integer, nullable=False, default=1)
    notes = Column(String)
