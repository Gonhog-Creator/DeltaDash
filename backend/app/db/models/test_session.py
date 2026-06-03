from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class TestSession(Base):
    __tablename__ = "test_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    test_date = Column(Date)
    lab_name = Column(String)
    protocol = Column(String)
    clay_temperature_c = Column(Numeric(5, 2))
    ambient_temperature_c = Column(Numeric(5, 2))
    humidity_percent = Column(Numeric(5, 2))
    conditioning = Column(String)
    size = Column(String)
    ballistic_limit = Column(Boolean, default=False)
    parent_test_group_id = Column(UUID(as_uuid=True), ForeignKey('test_sessions.id'), nullable=True)
    vest_id = Column(UUID(as_uuid=True), ForeignKey('vests.id'), nullable=True)
    excel_file_path = Column(String)
    notes = Column(String)
    is_official = Column(Boolean, default=False)
    certification_number = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
