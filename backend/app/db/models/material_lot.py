from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class MaterialLot(Base):
    """A supplier lot/shipment of a catalog material."""

    __tablename__ = "material_lots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False, index=True)
    supplier_lot_code = Column(String)
    received_at = Column(DateTime(timezone=True))
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("material_documents.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class MaterialRoll(Base):
    """A single roll within a material lot. Layer assignments reference rolls
    so roll-level variation can be shared across layers cut from the same roll."""

    __tablename__ = "material_rolls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_lot_id = Column(UUID(as_uuid=True), ForeignKey("material_lots.id"), nullable=False, index=True)
    supplier_roll_code = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
