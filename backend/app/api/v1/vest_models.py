from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
import os
import uuid

from app.db.session import SessionLocal
from app.db.models.vest_model import VestModel, ModelDocument
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User
from app.core.config import settings

router = APIRouter()


class VestModelCreate(BaseModel):
    name: str
    composition: Optional[str] = None


class VestModelUpdate(BaseModel):
    name: Optional[str] = None
    composition: Optional[str] = None


class ModelDocumentResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: str
    model_id: str
    name: str
    original_name: Optional[str]

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            model_id=str(obj.model_id),
            name=obj.name,
            original_name=obj.original_name,
        )


class VestModelResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    id: str
    name: str
    composition: Optional[str]
    documents: List[ModelDocumentResponse] = []

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            name=obj.name,
            composition=obj.composition,
            documents=[ModelDocumentResponse.from_orm(d) for d in (obj.documents or [])],
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[VestModelResponse])
def list_vest_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    models = db.query(VestModel).order_by(VestModel.name).all()
    return [VestModelResponse.from_orm(m) for m in models]


@router.post("/", response_model=VestModelResponse)
def create_vest_model(
    model: VestModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    existing = db.query(VestModel).filter(VestModel.name == model.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A model with this name already exists")

    db_model = VestModel(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return VestModelResponse.from_orm(db_model)


@router.put("/{model_id}", response_model=VestModelResponse)
def update_vest_model(
    model_id: str,
    model: VestModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    db_model = db.query(VestModel).filter(VestModel.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")

    update_data = model.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_model, key, value)

    db.commit()
    db.refresh(db_model)
    return VestModelResponse.from_orm(db_model)


@router.delete("/{model_id}")
def delete_vest_model(
    model_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    db_model = db.query(VestModel).filter(VestModel.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")

    for doc in (db_model.documents or []):
        full_path = os.path.join(settings.model_docs_dir, doc.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)

    db.delete(db_model)
    db.commit()
    return {"message": "Model deleted successfully"}


@router.post("/{model_id}/documents", response_model=ModelDocumentResponse)
def upload_document(
    model_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    db_model = db.query(VestModel).filter(VestModel.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    os.makedirs(settings.model_docs_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1].lower() or ''
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.model_docs_dir, unique_filename)

    with open(file_path, 'wb') as f:
        f.write(file.file.read())

    doc = ModelDocument(
        model_id=db_model.id,
        name=file.filename,
        file_path=unique_filename,
        original_name=file.filename,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return ModelDocumentResponse.from_orm(doc)


@router.get("/{model_id}/documents/{doc_id}/download")
def download_document(
    model_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    doc = db.query(ModelDocument).filter(
        ModelDocument.id == doc_id,
        ModelDocument.model_id == model_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    full_path = os.path.join(settings.model_docs_dir, doc.file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(full_path, filename=doc.original_name or doc.name)


@router.delete("/{model_id}/documents/{doc_id}")
def delete_document(
    model_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    doc = db.query(ModelDocument).filter(
        ModelDocument.id == doc_id,
        ModelDocument.model_id == model_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    full_path = os.path.join(settings.model_docs_dir, doc.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)

    db.delete(doc)
    db.commit()
    return {"message": "Document deleted successfully"}
