from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class MaterialPropertySpec(Base):
    """Approved specification/acceptance window for a material property.

    reference_value is the nominal value the limits are expressed against;
    lower_limit/upper_limit are absolute values in `unit` (not offsets).
    """

    __tablename__ = "material_property_specs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False, index=True)
    property_key = Column(String, nullable=False)
    direction = Column(String, nullable=False, default="none")
    unit = Column(String, nullable=False)
    reference_value = Column(Numeric(14, 4))
    lower_limit = Column(Numeric(14, 4))
    upper_limit = Column(Numeric(14, 4))
    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("material_documents.id"), nullable=True)
    approved_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
