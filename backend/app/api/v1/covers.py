from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from uuid import UUID
import uuid
import os

from app.db.session import get_db
from app.db.models.cover import Cover
from app.db.models.geometry import Geometry
from app.api.v1.auth import get_current_active_user, require_write_access
from app.db.models.user import User
from app.core.config import settings
from sqlalchemy.orm.attributes import flag_modified
from app.services.audit import log_action, serialize_model

router = APIRouter()


class CoverCreate(BaseModel):
    cover_code: str
    name: str
    geometry_id: Optional[str] = None
    fabric_type: Optional[str] = None
    fabric_weight_g_m2: Optional[Decimal] = Field(None, ge=0)
    layer_count: Optional[int] = Field(None, ge=0)
    color: Optional[str] = None
    construction_description: Optional[str] = None
    weight_g: Optional[Decimal] = Field(None, ge=0)
    has_molle: bool = False
    molle_config: Optional[list] = None
    has_quick_release: bool = False
    quick_release_type: Optional[str] = None
    has_badana: bool = False
    has_escudo: bool = False
    has_hombreras: bool = False
    fin_height_mm: Optional[Decimal] = Field(None, ge=0)
    fin_width_mm: Optional[Decimal] = Field(None, ge=0)
    available_sizes: Optional[List[str]] = None
    compatible_vest_types: Optional[List[str]] = None
    notes: Optional[str] = None


class CoverUpdate(BaseModel):
    cover_code: Optional[str] = None
    name: Optional[str] = None
    geometry_id: Optional[str] = None
    fabric_type: Optional[str] = None
    fabric_weight_g_m2: Optional[Decimal] = Field(None, ge=0)
    layer_count: Optional[int] = Field(None, ge=0)
    color: Optional[str] = None
    construction_description: Optional[str] = None
    weight_g: Optional[Decimal] = Field(None, ge=0)
    has_molle: Optional[bool] = None
    molle_config: Optional[list] = None
    has_quick_release: Optional[bool] = None
    quick_release_type: Optional[str] = None
    has_badana: Optional[bool] = None
    has_escudo: Optional[bool] = None
    has_hombreras: Optional[bool] = None
    fin_height_mm: Optional[Decimal] = Field(None, ge=0)
    fin_width_mm: Optional[Decimal] = Field(None, ge=0)
    available_sizes: Optional[List[str]] = None
    compatible_vest_types: Optional[List[str]] = None
    notes: Optional[str] = None


class CoverResponse(BaseModel):
    id: str
    cover_code: str
    name: str
    geometry_id: Optional[str]
    geometry_name: Optional[str]
    fabric_type: Optional[str]
    fabric_weight_g_m2: Optional[Decimal]
    layer_count: Optional[int]
    color: Optional[str]
    construction_description: Optional[str]
    weight_g: Optional[Decimal]
    has_molle: bool
    molle_config: Optional[list]
    has_quick_release: bool
    quick_release_type: Optional[str]
    has_badana: bool
    has_escudo: bool
    has_hombreras: bool
    fin_height_mm: Optional[Decimal]
    fin_width_mm: Optional[Decimal]
    available_sizes: Optional[List[str]]
    compatible_vest_types: Optional[List[str]]
    notes: Optional[str]
    pdf_document: Optional[dict] = None
    front_image: Optional[dict] = None
    back_image: Optional[dict] = None

    @classmethod
    def from_orm(cls, obj, geometry_name: Optional[str] = None):
        return cls(
            id=str(obj.id),
            cover_code=obj.cover_code,
            name=obj.name,
            geometry_id=str(obj.geometry_id) if obj.geometry_id else None,
            geometry_name=geometry_name,
            fabric_type=obj.fabric_type,
            fabric_weight_g_m2=obj.fabric_weight_g_m2,
            layer_count=obj.layer_count,
            color=obj.color,
            construction_description=obj.construction_description,
            weight_g=obj.weight_g,
            has_molle=obj.has_molle if obj.has_molle is not None else False,
            molle_config=obj.molle_config,
            has_quick_release=obj.has_quick_release if obj.has_quick_release is not None else False,
            quick_release_type=obj.quick_release_type,
            has_badana=obj.has_badana if obj.has_badana is not None else False,
            has_escudo=obj.has_escudo if obj.has_escudo is not None else False,
            has_hombreras=obj.has_hombreras if obj.has_hombreras is not None else False,
            fin_height_mm=obj.fin_height_mm,
            fin_width_mm=obj.fin_width_mm,
            available_sizes=obj.available_sizes,
            compatible_vest_types=obj.compatible_vest_types,
            notes=obj.notes,
            pdf_document=obj.pdf_document,
            front_image=obj.front_image,
            back_image=obj.back_image,
        )


@router.get("/", response_model=List[CoverResponse])
def list_covers(
    geometry_id: Optional[str] = None,
    vest_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all covers, optionally filtered by geometry or compatible vest type."""
    query = db.query(Cover)
    if geometry_id:
        query = query.filter(Cover.geometry_id == uuid.UUID(geometry_id))

    covers = query.all()

    results = []
    for cover in covers:
        geometry_name = None
        if cover.geometry_id:
            geom = db.query(Geometry).filter(Geometry.id == cover.geometry_id).first()
            geometry_name = geom.name if geom else None
        results.append(CoverResponse.from_orm(cover, geometry_name))

    if vest_type:
        results = [r for r in results if r.compatible_vest_types and vest_type in r.compatible_vest_types]

    return results


@router.get("/{cover_id}", response_model=CoverResponse)
def get_cover(
    cover_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a specific cover by ID."""
    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    geometry_name = None
    if cover.geometry_id:
        geom = db.query(Geometry).filter(Geometry.id == cover.geometry_id).first()
        geometry_name = geom.name if geom else None
    return CoverResponse.from_orm(cover, geometry_name)


@router.post("/", response_model=CoverResponse)
def create_cover(
    cover: CoverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Create a new cover (editor or admin only)."""
    if cover.geometry_id:
        geometry = db.query(Geometry).filter(Geometry.id == uuid.UUID(cover.geometry_id)).first()
        if not geometry:
            raise HTTPException(status_code=400, detail="Geometry not found")

    data = cover.model_dump()
    if data.get("geometry_id"):
        data["geometry_id"] = uuid.UUID(data["geometry_id"])

    db_cover = Cover(**data)
    db.add(db_cover)
    db.commit()
    db.refresh(db_cover)
    log_action(db, current_user, "create", "cover", db_cover.id, after=serialize_model(db_cover))
    db.commit()

    geometry_name = None
    if db_cover.geometry_id:
        geom = db.query(Geometry).filter(Geometry.id == db_cover.geometry_id).first()
        geometry_name = geom.name if geom else None
    return CoverResponse.from_orm(db_cover, geometry_name)


@router.put("/{cover_id}", response_model=CoverResponse)
def update_cover(
    cover_id: str,
    cover_update: CoverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Update a cover (editor or admin only)."""
    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    before = serialize_model(cover)

    if cover_update.geometry_id is not None:
        if cover_update.geometry_id:
            geometry = db.query(Geometry).filter(Geometry.id == uuid.UUID(cover_update.geometry_id)).first()
            if not geometry:
                raise HTTPException(status_code=400, detail="Geometry not found")
            cover.geometry_id = uuid.UUID(cover_update.geometry_id)
        else:
            cover.geometry_id = None

    update_data = cover_update.model_dump(exclude_unset=True, exclude={"geometry_id"})
    for key, value in update_data.items():
        setattr(cover, key, value)

    db.commit()
    db.refresh(cover)
    log_action(db, current_user, "update", "cover", cover.id, before=before, after=serialize_model(cover))
    db.commit()

    geometry_name = None
    if cover.geometry_id:
        geom = db.query(Geometry).filter(Geometry.id == cover.geometry_id).first()
        geometry_name = geom.name if geom else None
    return CoverResponse.from_orm(cover, geometry_name)


@router.delete("/{cover_id}")
def delete_cover(
    cover_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Delete a cover (editor or admin only)."""
    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    log_action(db, current_user, "delete", "cover", cover.id, before=serialize_model(cover))
    db.delete(cover)
    db.commit()
    return {"message": "Cover deleted successfully"}


# --- PDF (ficha técnica) endpoints ---

@router.post("/{cover_id}/upload-pdf", response_model=CoverResponse)
def upload_cover_pdf(
    cover_id: str,
    pdf_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Upload a PDF (ficha técnica) for a cover."""
    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    if not pdf_file.filename or not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    os.makedirs(settings.cover_docs_dir, exist_ok=True)

    ext = os.path.splitext(pdf_file.filename)[1].lower() or '.pdf'
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.cover_docs_dir, unique_filename)

    old_entry = cover.pdf_document or {}
    if old_entry.get('path'):
        old_full_path = os.path.join(settings.cover_docs_dir, old_entry['path'])
        if os.path.exists(old_full_path):
            os.remove(old_full_path)

    with open(file_path, 'wb') as f:
        f.write(pdf_file.file.read())

    cover.pdf_document = {
        'path': unique_filename,
        'original_name': pdf_file.filename,
    }
    flag_modified(cover, 'pdf_document')

    db.commit()
    db.refresh(cover)

    geometry_name = None
    if cover.geometry_id:
        geom = db.query(Geometry).filter(Geometry.id == cover.geometry_id).first()
        geometry_name = geom.name if geom else None
    return CoverResponse.from_orm(cover, geometry_name)


@router.get("/{cover_id}/download-pdf")
def download_cover_pdf(
    cover_id: str,
    db: Session = Depends(get_db),
):
    """Download the PDF for a cover. Publicly accessible so it can be used in <a> tags and file sync."""
    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    entry = cover.pdf_document or {}
    if not entry.get('path'):
        raise HTTPException(status_code=404, detail="PDF not found for this cover")

    full_path = os.path.join(settings.cover_docs_dir, entry['path'])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")

    download_filename = entry.get('original_name') or entry['path']
    return FileResponse(full_path, filename=download_filename)


@router.delete("/{cover_id}/delete-pdf", response_model=CoverResponse)
def delete_cover_pdf(
    cover_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Delete the PDF for a cover."""
    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    entry = cover.pdf_document or {}
    if entry.get('path'):
        full_path = os.path.join(settings.cover_docs_dir, entry['path'])
        if os.path.exists(full_path):
            os.remove(full_path)
        cover.pdf_document = None
        flag_modified(cover, 'pdf_document')
        db.commit()
        db.refresh(cover)

    geometry_name = None
    if cover.geometry_id:
        geom = db.query(Geometry).filter(Geometry.id == cover.geometry_id).first()
        geometry_name = geom.name if geom else None
    return CoverResponse.from_orm(cover, geometry_name)


# --- Cover image endpoints (front / back) ---

ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}


def _upload_cover_image(cover, image_file, field_name, db):
    """Helper to upload a cover image (front or back)."""
    if not image_file.filename:
        raise HTTPException(status_code=400, detail="No image file provided")

    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Only image files are allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    os.makedirs(settings.cover_images_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.cover_images_dir, unique_filename)

    old_entry = getattr(cover, field_name) or {}
    if old_entry.get('path'):
        old_full_path = os.path.join(settings.cover_images_dir, old_entry['path'])
        if os.path.exists(old_full_path):
            os.remove(old_full_path)

    with open(file_path, 'wb') as f:
        f.write(image_file.file.read())

    setattr(cover, field_name, {
        'path': unique_filename,
        'original_name': image_file.filename,
    })
    flag_modified(cover, field_name)


def _delete_cover_image(cover, field_name, db):
    """Helper to delete a cover image (front or back)."""
    entry = getattr(cover, field_name) or {}
    if entry.get('path'):
        full_path = os.path.join(settings.cover_images_dir, entry['path'])
        if os.path.exists(full_path):
            os.remove(full_path)
        setattr(cover, field_name, None)
        flag_modified(cover, field_name)


def _cover_geometry_name(db, cover):
    if cover.geometry_id:
        geom = db.query(Geometry).filter(Geometry.id == cover.geometry_id).first()
        return geom.name if geom else None
    return None


@router.post("/{cover_id}/upload-image/{side}", response_model=CoverResponse)
def upload_cover_image(
    cover_id: str,
    side: str,
    image_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Upload a front or back image for a cover. side must be 'front' or 'back'."""
    if side not in ('front', 'back'):
        raise HTTPException(status_code=400, detail="side must be 'front' or 'back'")

    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    field_name = f"{side}_image"
    _upload_cover_image(cover, image_file, field_name, db)

    db.commit()
    db.refresh(cover)
    return CoverResponse.from_orm(cover, _cover_geometry_name(db, cover))


@router.get("/{cover_id}/download-image/{side}")
def download_cover_image(
    cover_id: str,
    side: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Download a front or back image for a cover. Publicly accessible so it can be used in <img> tags."""
    if side not in ('front', 'back'):
        raise HTTPException(status_code=400, detail="side must be 'front' or 'back'")

    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    entry = getattr(cover, f"{side}_image") or {}
    if not entry.get('path'):
        raise HTTPException(status_code=404, detail=f"{side} image not found for this cover")

    full_path = os.path.join(settings.cover_images_dir, entry['path'])
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk")

    ext = os.path.splitext(full_path)[1].lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    origin = request.headers.get("origin", "*")
    with open(full_path, "rb") as f:
        data = f.read()
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.delete("/{cover_id}/delete-image/{side}", response_model=CoverResponse)
def delete_cover_image(
    cover_id: str,
    side: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    """Delete a front or back image for a cover."""
    if side not in ('front', 'back'):
        raise HTTPException(status_code=400, detail="side must be 'front' or 'back'")

    cover = db.query(Cover).filter(Cover.id == uuid.UUID(cover_id)).first()
    if not cover:
        raise HTTPException(status_code=404, detail="Cover not found")

    _delete_cover_image(cover, f"{side}_image", db)

    db.commit()
    db.refresh(cover)
    return CoverResponse.from_orm(cover, _cover_geometry_name(db, cover))
