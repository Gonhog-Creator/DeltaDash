from sqlalchemy import Column, String, Numeric, Boolean, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_run_id = Column(UUID(as_uuid=True), ForeignKey("model_runs.id"), nullable=True)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    input_json = Column(JSONB, nullable=False)
    predicted_bfd_mm = Column(Numeric(10, 2))
    prediction_interval_low_mm = Column(Numeric(10, 2))
    prediction_interval_high_mm = Column(Numeric(10, 2))
    probability_bfd_gt_44 = Column(Numeric(5, 4))
    probability_penetration = Column(Numeric(5, 4))
    extrapolation_warning = Column(Boolean, default=False)
    comparable_shot_count = Column(Integer)
    output_json = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
