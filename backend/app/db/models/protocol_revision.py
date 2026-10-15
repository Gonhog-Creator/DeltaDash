from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class ProtocolRevision(Base):
    """Immutable, versioned interpretation of a protocol level's exposure plan:
    which ammunition, velocity bounds (and whether the window is symmetric or
    one-sided), shot pattern, conditioning, and outcome decision rules.

    shots_json: [{shot_number, panel_assignment, side, angle_degrees,
                  ammunition_id, velocity_lower_m_s, velocity_upper_m_s,
                  window_interpretation: 'symmetric'|'lower_only'|'upper_only',
                  conditioning}]
    outcome_rule_json: {bfd_threshold_mm, operator, penetration_criterion,
                        reshoot_rules}
    """

    __tablename__ = "protocol_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    protocol_id = Column(UUID(as_uuid=True), ForeignKey("protocols.id"), nullable=False, index=True)
    level = Column(String, nullable=False)
    revision = Column(Integer, nullable=False, default=1)
    rule_source = Column(String)
    review_status = Column(String, nullable=False, default="unreviewed")
    shots_json = Column(JSONB, nullable=True)
    outcome_rule_json = Column(JSONB, nullable=True)
    content_hash = Column(String, nullable=True)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
