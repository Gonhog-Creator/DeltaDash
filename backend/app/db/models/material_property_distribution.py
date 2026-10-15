from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class MaterialPropertyDistribution(Base):
    """A fitted or assumed distribution over a material property for a given
    population scope (lot / roll / coupon).

    family: empirical_bootstrap | normal | truncated_normal | lognormal |
            uniform | triangular | constant
    parameters_json: e.g. {"mu": ..., "sigma": ..., "lower": ..., "upper": ...}
    provenance: 'measured' | 'assumed' | 'report_derived'
    population_scope: 'lot' | 'roll' | 'coupon' | 'accepted_units' | 'pre_qc'
    """

    __tablename__ = "material_property_distributions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id = Column(UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False, index=True)
    spec_id = Column(UUID(as_uuid=True), ForeignKey("material_property_specs.id"), nullable=True)
    property_key = Column(String, nullable=False)
    direction = Column(String, nullable=False, default="none")
    unit = Column(String, nullable=False)

    population_scope = Column(String, nullable=False, default="accepted_units")
    family = Column(String, nullable=False)
    parameters_json = Column(JSONB, nullable=False, default=dict)
    latent_correlation_group = Column(String, nullable=True)

    provenance = Column(String, nullable=False, default="assumed")
    measurement_ids = Column(JSONB, nullable=True)
    fit_diagnostics_json = Column(JSONB, nullable=True)
    sample_count = Column(Integer, nullable=True)
    group_count = Column(Integer, nullable=True)

    effective_from = Column(DateTime(timezone=True))
    effective_to = Column(DateTime(timezone=True))
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)
    review_status = Column(String, nullable=False, default="unreviewed")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
