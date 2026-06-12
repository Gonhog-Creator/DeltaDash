from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.db.models.geometry import Geometry
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User

router = APIRouter()


class GeometryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    vest_type: Optional[str] = None
    surface_areas: dict
    available_sizes: List[str]
    includes_hard_plates: bool = False
    notes: Optional[str] = None


class GeometryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    vest_type: Optional[str] = None
    surface_areas: Optional[dict] = None
    available_sizes: Optional[List[str]] = None
    includes_hard_plates: Optional[bool] = None
    notes: Optional[str] = None


class GeometryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    vest_type: Optional[str]
    surface_areas: dict
    available_sizes: List[str]
    includes_hard_plates: bool
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
            notes=obj.notes
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    geometries = query.all()
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
