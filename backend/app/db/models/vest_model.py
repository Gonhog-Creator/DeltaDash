from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class ModelDocument(Base):
    __tablename__ = "model_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vest_id = Column(UUID(as_uuid=True), ForeignKey("vests.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    original_name = Column(String, nullable=True)

    vest = relationship("Vest", back_populates="documents")
