from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class EvaluationManifest(Base):
    """Immutable snapshot of real shot records usable for evaluation, with the
    grouping keys needed for leakage-safe splits. shot entries carry
    {shot_id, test_session_id, parent_test_group_id, vest_id, duplicate_group_id}
    — IDs are for grouping/audit only, never model features."""

    __tablename__ = "evaluation_manifests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    shot_entries = Column(JSONB, nullable=False)
    content_hash = Column(String, nullable=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
