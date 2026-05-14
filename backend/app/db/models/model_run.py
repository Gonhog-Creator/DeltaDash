from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name = Column(String, nullable=False)
    model_type = Column(String, nullable=False)
    version = Column(String, nullable=False)
    training_started_at = Column(DateTime(timezone=True))
    training_completed_at = Column(DateTime(timezone=True))
    training_row_count = Column(Integer)
    formula = Column(String)
    metrics_json = Column(JSONB)
    artifact_path = Column(String)
    notes = Column(String)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
