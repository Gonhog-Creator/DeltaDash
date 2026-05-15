from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class ShotData(Base):
    __tablename__ = "shot_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey('test_sessions.id'), nullable=False)
    
    vest_number = Column(String)
    side = Column(String)
    angle_degrees = Column(Numeric(5, 2))
    shot_number = Column(String)
    protection_level = Column(String)
    caliber = Column(String)
    trauma_mm = Column(Numeric(10, 2))
    trauma_qualitative = Column(String)
    velocity_m_s = Column(Numeric(10, 2))
    
    temperature_c = Column(Numeric(5, 2))
    humidity_percent = Column(Numeric(5, 2))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
