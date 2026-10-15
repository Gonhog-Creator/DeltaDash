from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class AsTestedPropertySnapshot(Base):
    """The property value a specific physical panel was built/tested with.
    Immutable once recorded: editing the material catalog must not rewrite
    the as-tested snapshot of a historical panel."""

    __tablename__ = "as_tested_property_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    panel_id = Column(UUID(as_uuid=True), ForeignKey("armor_panels.id"), nullable=False, index=True)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False)
    property_key = Column(String, nullable=False)
    direction = Column(String, nullable=False, default="none")
    value = Column(Numeric(14, 4), nullable=False)
    unit = Column(String, nullable=False)
    measurement_ids = Column(JSONB, nullable=True)
    aggregation_method = Column(String, nullable=True)  # e.g. 'catalog_nominal', 'lot_mean', 'roll_coupon_mean'
    source_quality = Column(String, nullable=True)      # e.g. 'measured', 'report_derived', 'catalog'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
