from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class RiskSimulationRun(Base):
    """One Monte Carlo execution of a scenario. Persisted so different model
    versions/runs can be compared. result_json contains histograms, event
    estimates, readiness per output, and a calculation_trace for the
    methodology view."""

    __tablename__ = "risk_simulation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id = Column(UUID(as_uuid=True), ForeignKey("risk_scenarios.id"), nullable=False, index=True)
    scenario_hash = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")  # queued|running|completed|failed|canceled
    seed = Column(BigInteger, nullable=False)
    requested_draws = Column(Integer, nullable=False)
    completed_independent_draws = Column(Integer, nullable=False, default=0)

    model_bundle_hash = Column(String, nullable=True)
    data_snapshot_hash = Column(String, nullable=True)
    calibration_version = Column(String, nullable=True)
    feature_contract_version = Column(String, nullable=True)
    runtime_versions_json = Column(JSONB, nullable=True)

    assumptions_json = Column(JSONB, nullable=True)
    readiness_json = Column(JSONB, nullable=True)
    result_json = Column(JSONB, nullable=True)
    failure_reason = Column(String, nullable=True)

    created_by = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
