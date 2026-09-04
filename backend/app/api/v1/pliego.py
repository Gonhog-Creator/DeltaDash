"""API endpoints for Pliego Técnico matching.

Allows users to upload bid/contract documents (PDF, DOCX), which are then
analyzed by Gemini AI to extract vest requirements and matched against
certified vest models in the database.
"""
import os
import uuid as uuid_mod
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.pliego_document import PliegoDocument
from app.db.models.user import User as UserModel
from app.api.v1.auth import get_current_active_user, require_write_access
from app.core.config import settings

router = APIRouter(redirect_slashes=False)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class PliegoDocumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    original_name: Optional[str] = None
    status: str
    extracted_requirements: Optional[dict] = None
    match_results: Optional[dict] = None
    error_message: Optional[str] = None
    created_by_username: Optional[str] = None
    created_at: str
    updated_at: str


@router.post("/upload", response_model=PliegoDocumentSchema)
def upload_pliego(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Upload a pliego técnico document, extract requirements via AI, and match vests.

    The file is saved to disk, text is extracted, Gemini AI extracts structured
    requirements, and those requirements are matched against certified vests.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file content
    content = file.file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    # Save file to disk
    os.makedirs(settings.pliego_docs_dir, exist_ok=True)
    unique_filename = f"{uuid_mod.uuid4()}{ext}"
    file_path = os.path.join(settings.pliego_docs_dir, unique_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # Create DB record
    doc = PliegoDocument(
        filename=unique_filename,
        file_path=unique_filename,
        original_name=file.filename,
        status="pending",
        created_by_username=current_user.username if hasattr(current_user, "username") else None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run analysis
    try:
        from app.services.pliego_matcher import analyze_pliego

        full_path = os.path.join(settings.pliego_docs_dir, doc.file_path)
        result = analyze_pliego(full_path, db)

        doc.extracted_requirements = result["requirements"]
        doc.match_results = result["match_results"]
        doc.status = "analyzed"
        db.commit()
        db.refresh(doc)

    except Exception as e:
        import traceback
        traceback.print_exc()
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        db.refresh(doc)

    return PliegoDocumentSchema.model_validate({
        **{c.name: getattr(doc, c.name) for c in doc.__table__.columns},
        "id": str(doc.id),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "extracted_requirements": doc.extracted_requirements,
        "match_results": doc.match_results,
    })


@router.get("/documents", response_model=list[PliegoDocumentSchema])
def list_pliego_documents(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """List all uploaded pliego documents."""
    docs = db.query(PliegoDocument).order_by(PliegoDocument.created_at.desc()).all()
    return [
        PliegoDocumentSchema.model_validate({
            **{c.name: getattr(d, c.name) for c in d.__table__.columns},
            "id": str(d.id),
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            "extracted_requirements": d.extracted_requirements,
            "match_results": d.match_results,
        })
        for d in docs
    ]


@router.get("/documents/{doc_id}", response_model=PliegoDocumentSchema)
def get_pliego_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Get a specific pliego document with its analysis results."""
    doc = db.query(PliegoDocument).filter(PliegoDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return PliegoDocumentSchema.model_validate({
        **{c.name: getattr(doc, c.name) for c in doc.__table__.columns},
        "id": str(doc.id),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "extracted_requirements": doc.extracted_requirements,
        "match_results": doc.match_results,
    })


@router.get("/documents/{doc_id}/download")
def download_pliego_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Download the original uploaded file."""
    doc = db.query(PliegoDocument).filter(PliegoDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = os.path.join(settings.pliego_docs_dir, doc.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=doc.original_name or doc.filename,
    )


@router.post("/documents/{doc_id}/retry", response_model=PliegoDocumentSchema)
def retry_pliego_analysis(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access),
):
    """Retry analysis on a previously uploaded pliego document."""
    doc = db.query(PliegoDocument).filter(PliegoDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = os.path.join(settings.pliego_docs_dir, doc.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    doc.status = "pending"
    doc.error_message = None
    db.commit()
    db.refresh(doc)

    try:
        from app.services.pliego_matcher import analyze_pliego

        full_path = os.path.join(settings.pliego_docs_dir, doc.file_path)
        result = analyze_pliego(full_path, db)

        doc.extracted_requirements = result["requirements"]
        doc.match_results = result["match_results"]
        doc.status = "analyzed"
        db.commit()
        db.refresh(doc)

    except Exception as e:
        import traceback
        traceback.print_exc()
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        db.refresh(doc)

    return PliegoDocumentSchema.model_validate({
        **{c.name: getattr(doc, c.name) for c in doc.__table__.columns},
        "id": str(doc.id),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        "extracted_requirements": doc.extracted_requirements,
        "match_results": doc.match_results,
    })


@router.delete("/documents/{doc_id}")
def delete_pliego_document(
    doc_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access),
):
    """Delete a pliego document, its analysis results, and the uploaded file from disk."""
    doc = db.query(PliegoDocument).filter(PliegoDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete the uploaded file from disk
    file_path = os.path.join(settings.pliego_docs_dir, doc.file_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            import logging
            logging.getLogger(__name__).warning(
                f"Failed to delete pliego file {file_path}: {e}"
            )

    # Clear analysis data and delete the DB record
    doc.extracted_requirements = None
    doc.match_results = None
    doc.error_message = None
    db.delete(doc)
    db.commit()
    return {"message": "Document and associated data deleted successfully"}
