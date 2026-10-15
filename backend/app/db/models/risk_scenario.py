from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class RiskScenario(Base):
    """Immutable scenario definition. Editing creates a new revision.
    population_mode: 'accepted_units' | 'pre_qc'."""

    __tablename__ = "risk_scenarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    design_id = Column(UUID(as_uuid=True), ForeignKey("vests.id"), nullable=False)
    design_revision = Column(Integer, nullable=True)
    protocol_revision_id = Column(UUID(as_uuid=True), ForeignKey("protocol_revisions.id"), nullable=True)
    model_version = Column(String, nullable=False)
    feature_contract_version = Column(String, nullable=True)

    layer_snapshot_json = Column(JSONB, nullable=False)
    distribution_snapshot_json = Column(JSONB, nullable=False, default=dict)
    dependency_snapshot_json = Column(JSONB, nullable=False, default=dict)
    outcome_rule_json = Column(JSONB, nullable=False, default=dict)
    near_worst_event_json = Column(JSONB, nullable=True)

    population_mode = Column(String, nullable=False, default="accepted_units")
    population_size = Column(Integer, nullable=False, default=1000)
    layer_counts_locked = Column(Boolean, nullable=False, default=True)

    revision = Column(Integer, nullable=False, default=1)
    content_hash = Column(String, nullable=False)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
