from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from decimal import Decimal


class MaterialDocumentBase(BaseModel):
    material_id: UUID | None = None
    document_type: str | None = None
    original_filename: str
    stored_path: str
    parsed_text: str | None = None
    manufacturer_detected: str | None = None
    extraction_confidence: Decimal | None = None
    uploaded_by: UUID | None = None


class MaterialDocumentCreate(MaterialDocumentBase):
    pass


class MaterialDocumentInDB(MaterialDocumentBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialDocument(MaterialDocumentInDB):
    pass
