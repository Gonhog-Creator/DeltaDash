from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class ModelValidationRun(Base):
    """A grouped, out-of-sample evaluation of a model bundle against an
    immutable split manifest. Metrics here (not training-fit metrics) are what
    probability outputs may rely on."""

    __tablename__ = "model_validation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_version = Column(String, nullable=False, index=True)
    dataset_hash = Column(String, nullable=False)
    split_manifest_hash = Column(String, nullable=False)
    group_definition = Column(String, nullable=False)  # e.g. 'parent_test_group', 'production_lot'
    train_ids = Column(JSONB, nullable=True)
    tuning_ids = Column(JSONB, nullable=True)
    calibration_ids = Column(JSONB, nullable=True)
    test_ids = Column(JSONB, nullable=True)
    real_metrics_json = Column(JSONB, nullable=True)
    synthetic_diagnostics_json = Column(JSONB, nullable=True)
    coverage_json = Column(JSONB, nullable=True)
    support_summary_json = Column(JSONB, nullable=True)
    residual_artifact_path = Column(String, nullable=True)
    classifier_calibration_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
