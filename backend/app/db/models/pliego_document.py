from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class PliegoDocument(Base):
    __tablename__ = "pliego_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    original_name = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending, analyzed, failed
    extracted_requirements = Column(JSONB, nullable=True)
    match_results = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by_username = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
