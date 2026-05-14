from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class ShotPattern(Base):
    __tablename__ = "shot_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    vest_type = Column(String)
    protocol = Column(String)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
