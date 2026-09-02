from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional
from pydantic import BaseModel
from pathlib import Path
import os
import uuid

from app.db.session import SessionLocal
from app.db.models.geometry import Geometry
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User
from app.core.config import settings
from app.services.geometry_excel_service import (
    export_geometries_to_excel,
    import_geometries_from_excel,
)

router = APIRouter()


class GeometryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    vest_type: Optional[str] = None
    surface_areas: dict
    available_sizes: List[str]
    includes_hard_plates: bool = False
    is_approved: bool = False
    size_measurements: Optional[dict] = None
    pdf_document: Optional[dict] = None
    image_url: Optional[str] = None
    compatibility: Optional[str] = None
    notes: Optional[str] = None


class GeometryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    vest_type: Optional[str] = None
    surface_areas: Optional[dict] = None
    available_sizes: Optional[List[str]] = None
    includes_hard_plates: Optional[bool] = None
    is_approved: Optional[bool] = None
    size_measurements: Optional[dict] = None
    pdf_document: Optional[dict] = None
    image_url: Optional[str] = None
    compatibility: Optional[str] = None
    notes: Optional[str] = None


class GeometryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    vest_type: Optional[str]
    surface_areas: dict
    available_sizes: List[str]
    includes_hard_plates: bool
    is_approved: bool = False
    size_measurements: Optional[dict] = None
    pdf_document: Optional[dict] = None
    image_url: Optional[str] = None
    compatibility: Optional[str] = None
    notes: Optional[str]

    @classmethod
    def from_orm(cls, obj):
        return cls(
            id=str(obj.id),
            name=obj.name,
            description=obj.description,
            vest_type=obj.vest_type,
            surface_areas=obj.surface_areas,
            available_sizes=obj.available_sizes,
            includes_hard_plates=obj.includes_hard_plates,
            is_approved=obj.is_approved if obj.is_approved is not None else False,
            size_measurements=obj.size_measurements,
            pdf_document=obj.pdf_document,
            image_url=obj.image_url,
            compatibility=obj.compatibility,
            notes=obj.notes
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/download-excel")
def download_geometries_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Download the master geometries Excel workbook for editing."""

    try:
        output = export_geometries_to_excel(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export geometries: {str(e)}")

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=geometries.xlsx"}
    )


@router.post("/upload-excel")
def upload_geometries_excel(
    excel_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload the master geometries Excel workbook and upsert all geometries."""

    ext = os.path.splitext(excel_file.filename or "")[1].lower()
    if ext not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are allowed")

    file_path = os.path.join(settings.geometry_docs_dir, f"geometries_upload_{uuid.uuid4()}{ext}")
    os.makedirs(settings.geometry_docs_dir, exist_ok=True)
    try:
        with open(file_path, "wb") as f:
            f.write(excel_file.file.read())
        geometries = import_geometries_from_excel(file_path, db)
        return {"message": f"Imported {len(geometries)} geometries", "count": len(geometries)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import geometries: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@router.get("/", response_model=List[GeometryResponse])
def get_geometries(
    vest_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all geometries, optionally filtered by vest type"""
    query = db.query(Geometry)
    if vest_type:
        query = query.filter(Geometry.vest_type == vest_type)
    geometries = query.order_by(Geometry.name).all()
    return [GeometryResponse.from_orm(g) for g in geometries]


@router.get("/{geometry_id}", response_model=GeometryResponse)
def get_geometry(
    geometry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific geometry by ID"""
    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")
    return GeometryResponse.from_orm(geometry)


@router.post("/", response_model=GeometryResponse)
def create_geometry(
    geometry: GeometryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new geometry (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db_geometry = Geometry(**geometry.model_dump())
    db.add(db_geometry)
    db.commit()
    db.refresh(db_geometry)
    return GeometryResponse.from_orm(db_geometry)


@router.put("/{geometry_id}", response_model=GeometryResponse)
def update_geometry(
    geometry_id: str,
    geometry: GeometryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update a geometry (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db_geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not db_geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")
    
    update_data = geometry.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_geometry, key, value)
    
    db.commit()
    db.refresh(db_geometry)
    return GeometryResponse.from_orm(db_geometry)


@router.delete("/{geometry_id}")
def delete_geometry(
    geometry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a geometry (admin only)"""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    db_geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not db_geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")
    
    db.delete(db_geometry)
    db.commit()
    return {"message": "Geometry deleted successfully"}


@router.post("/{geometry_id}/upload-pdf", response_model=GeometryResponse)
def upload_geometry_pdf(
    geometry_id: str,
    pdf_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload a single PDF for a geometry (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")

    if not pdf_file.filename or not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    os.makedirs(settings.geometry_docs_dir, exist_ok=True)

    # Build unique filename while preserving extension
    ext = os.path.splitext(pdf_file.filename)[1].lower() or '.pdf'
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.geometry_docs_dir, unique_filename)

    # Remove old geometry PDF if present
    old_entry = geometry.pdf_document or {}
    if old_entry.get('path'):
        old_full_path = os.path.join(settings.geometry_docs_dir, old_entry['path'])
        if os.path.exists(old_full_path):
            os.remove(old_full_path)

    with open(file_path, 'wb') as f:
        f.write(pdf_file.file.read())

    geometry.pdf_document = {
        'path': unique_filename,
        'original_name': pdf_file.filename,
    }
    flag_modified(geometry, 'pdf_document')

    db.commit()
    db.refresh(geometry)
    return GeometryResponse.from_orm(geometry)


@router.get("/{geometry_id}/download-pdf")
def download_geometry_pdf(
    geometry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Download the single PDF for a geometry."""
    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")

    entry = geometry.pdf_document or {}
    if not entry.get('path'):
        raise HTTPException(status_code=404, detail="PDF not found for this geometry")

    full_path = os.path.join(settings.geometry_docs_dir, entry['path'])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    download_filename = entry.get('original_name') or entry['path']
    return FileResponse(full_path, filename=download_filename)


@router.delete("/{geometry_id}/delete-pdf", response_model=GeometryResponse)
def delete_geometry_pdf(
    geometry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete the single PDF for a geometry (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")

    entry = geometry.pdf_document or {}
    if entry.get('path'):
        full_path = os.path.join(settings.geometry_docs_dir, entry['path'])
        if os.path.exists(full_path):
            os.remove(full_path)
        geometry.pdf_document = None
        flag_modified(geometry, 'pdf_document')
        db.commit()
        db.refresh(geometry)

    return GeometryResponse.from_orm(geometry)


ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def _geometry_image_path(geometry_id: str) -> Optional[Path]:
    """Return the first file matching the geometry ID in the images directory."""
    images_dir = Path(settings.geometry_images_dir)
    if not images_dir.exists():
        return None
    matches = list(images_dir.glob(f"{geometry_id}.*"))
    return matches[0] if matches else None


@router.post("/{geometry_id}/upload-image", response_model=GeometryResponse)
def upload_geometry_image(
    geometry_id: str,
    image_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Upload an image for a geometry (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")

    if not image_file.filename:
        raise HTTPException(status_code=400, detail="No image file provided")

    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only image files are allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    os.makedirs(settings.geometry_images_dir, exist_ok=True)

    # Remove any previously uploaded image for this geometry
    for old_file in Path(settings.geometry_images_dir).glob(f"{geometry_id}.*"):
        old_file.unlink(missing_ok=True)

    file_path = Path(settings.geometry_images_dir) / f"{geometry_id}{ext}"
    with open(file_path, 'wb') as f:
        f.write(image_file.file.read())

    geometry.image_url = f"/api/v1/geometries/{geometry_id}/image"
    db.commit()
    db.refresh(geometry)
    return GeometryResponse.from_orm(geometry)


@router.get("/{geometry_id}/image")
def download_geometry_image(
    geometry_id: str,
    db: Session = Depends(get_db)
):
    """Download the uploaded image for a geometry. Publicly accessible so it can be used in <img> tags."""
    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")

    file_path = _geometry_image_path(geometry_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found for this geometry")

    return FileResponse(file_path)


@router.delete("/{geometry_id}/delete-image", response_model=GeometryResponse)
def delete_geometry_image(
    geometry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete the uploaded image for a geometry (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    geometry = db.query(Geometry).filter(Geometry.id == geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")

    file_path = _geometry_image_path(geometry_id)
    if file_path and file_path.exists():
        file_path.unlink(missing_ok=True)

    geometry.image_url = None
    db.commit()
    db.refresh(geometry)

    return GeometryResponse.from_orm(geometry)
