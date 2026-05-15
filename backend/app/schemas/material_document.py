from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class MaterialDocumentBase(BaseModel):
    material_id: Optional[UUID] = None
    document_type: Optional[str] = None
    original_filename: str
    stored_path: str
    parsed_text: Optional[str] = None
    manufacturer_detected: Optional[str] = None
    extraction_confidence: Optional[Decimal] = None
    uploaded_by: Optional[UUID] = None


class MaterialDocumentCreate(MaterialDocumentBase):
    pass


class MaterialDocumentInDB(MaterialDocumentBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialDocument(MaterialDocumentInDB):
    pass
