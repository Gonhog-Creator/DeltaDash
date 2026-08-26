from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from uuid import UUID
import uuid

from app.db.session import get_db
from app.db.models.cover import Cover
from app.db.models.geometry import Geometry
from app.api.v1.auth import get_current_active_user, require_write_access
from app.db.models.user import User

router = APIRouter()


class CoverCreate(BaseModel):
    cover_code: str
    name: str
    geometry_id: Optional[str] = None
    fabric_type: Optional[str] = None
    fabric_weight_g_m2: Optional[Decimal] = Field(None, ge=0)
    layer_count: Optional[int] = Field(None, ge=0)
    weight_g: Optional[Decimal] = Field(None, ge=0)
    has_molle: bool = False
    molle_config: Optional[list] = None
    has_quick_release: bool = False
    quick_release_type: Optional[str] = None
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
    weight_g: Optional[Decimal] = Field(None, ge=0)
    has_molle: Optional[bool] = None
    molle_config: Optional[list] = None
    has_quick_release: Optional[bool] = None
    quick_release_type: Optional[str] = None
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
    weight_g: Optional[Decimal]
    has_molle: bool
    molle_config: Optional[list]
    has_quick_release: bool
    quick_release_type: Optional[str]
    fin_height_mm: Optional[Decimal]
    fin_width_mm: Optional[Decimal]
    available_sizes: Optional[List[str]]
    compatible_vest_types: Optional[List[str]]
    notes: Optional[str]

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
            weight_g=obj.weight_g,
            has_molle=obj.has_molle if obj.has_molle is not None else False,
            molle_config=obj.molle_config,
            has_quick_release=obj.has_quick_release if obj.has_quick_release is not None else False,
            quick_release_type=obj.quick_release_type,
            fin_height_mm=obj.fin_height_mm,
            fin_width_mm=obj.fin_width_mm,
            available_sizes=obj.available_sizes,
            compatible_vest_types=obj.compatible_vest_types,
            notes=obj.notes,
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

    db.delete(cover)
    db.commit()
    return {"message": "Cover deleted successfully"}
