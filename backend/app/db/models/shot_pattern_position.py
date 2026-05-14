from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class ShotPatternPosition(Base):
    __tablename__ = "shot_pattern_positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shot_pattern_id = Column(UUID(as_uuid=True), ForeignKey("shot_patterns.id", ondelete="CASCADE"), nullable=False)
    shot_number = Column(Integer, nullable=False)
    x_normalized = Column(Numeric(5, 4))
    y_normalized = Column(Numeric(5, 4))
    x_mm = Column(Numeric(10, 2))
    y_mm = Column(Numeric(10, 2))
    impact_angle_degrees = Column(Numeric(5, 2), default=0)
    location_label = Column(String)
    notes = Column(String)
