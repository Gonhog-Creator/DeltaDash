from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Boolean, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class MaterialPropertyMeasurement(Base):
    """A single measured material property value with full provenance.

    property_key examples: breaking_force_n_per_cm, tensile_strength_mpa,
    thickness_mm, areal_density_g_m2, elongation_percent, modulus_gpa.
    direction: 'longitudinal', 'transverse', or 'none'.
    uncertainty_kind: 'absolute' (same unit as value), 'relative_percent',
    'percentage_points', 'specification_limit'.
    """

    __tablename__ = "material_property_measurements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False, index=True)
    lot_id = Column(UUID(as_uuid=True), ForeignKey("material_lots.id"), nullable=True, index=True)
    roll_id = Column(UUID(as_uuid=True), ForeignKey("material_rolls.id"), nullable=True, index=True)
    coupon_id = Column(String, nullable=True)
    specimen_position = Column(String, nullable=True)

    property_key = Column(String, nullable=False, index=True)
    direction = Column(String, nullable=False, default="none")
    value = Column(Numeric(14, 4), nullable=False)
    unit = Column(String, nullable=False)
    measured_at = Column(DateTime(timezone=True))
    method = Column(String)

    specimen_width_mm = Column(Numeric(10, 3))
    gauge_length_mm = Column(Numeric(10, 3))
    test_temperature_c = Column(Numeric(5, 2))

    measurement_uncertainty = Column(Numeric(14, 4))
    uncertainty_kind = Column(String)
    coverage_factor = Column(Numeric(6, 3))

    source_document_id = Column(UUID(as_uuid=True), ForeignKey("material_documents.id"), nullable=True)
    source_page = Column(String)
    source_table = Column(String)
    source_row = Column(String)

    is_raw_measurement = Column(Boolean, nullable=False, default=False)
    review_status = Column(String, nullable=False, default="unreviewed")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
