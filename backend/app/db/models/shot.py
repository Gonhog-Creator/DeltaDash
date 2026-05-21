from sqlalchemy import Column, String, Numeric, Boolean, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class Shot(Base):
    __tablename__ = "shots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey("test_sessions.id"), nullable=True)
    vest_id = Column(UUID(as_uuid=True), ForeignKey("vests.id"), nullable=True)
    panel_id = Column(UUID(as_uuid=True), ForeignKey("armor_panels.id"), nullable=True)
    ammunition_id = Column(UUID(as_uuid=True), ForeignKey("ammunition.id"), nullable=True)
    shot_pattern_position_id = Column(UUID(as_uuid=True), ForeignKey("shot_pattern_positions.id"), nullable=True)
    shot_number = Column(Integer)
    measured_velocity_fps = Column(Numeric(10, 2))
    measured_velocity_m_s = Column(Numeric(10, 2))
    impact_angle_degrees = Column(Numeric(5, 2))
    bfd_mm = Column(Numeric(10, 2))
    penetration = Column(Boolean)
    partial_penetration = Column(Boolean)
    trauma_score = Column(Numeric(5, 2))
    pass_fail = Column(String)
    distance_m = Column(Numeric(10, 2))
    yaw_observed = Column(Boolean)
    edge_hit = Column(Boolean)
    anomaly_flag = Column(Boolean, default=False)
    anomaly_notes = Column(String)
    raw_source_file = Column(String)
    raw_row_number = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
