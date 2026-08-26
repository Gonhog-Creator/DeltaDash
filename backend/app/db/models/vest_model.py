from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base


class VestModel(Base):
    __tablename__ = "vest_models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True, index=True)
    composition = Column(Text, nullable=True)

    documents = relationship("ModelDocument", back_populates="model", cascade="all, delete-orphan")


class ModelDocument(Base):
    __tablename__ = "model_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_id = Column(UUID(as_uuid=True), ForeignKey("vest_models.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    original_name = Column(String, nullable=True)

    model = relationship("VestModel", back_populates="documents")
