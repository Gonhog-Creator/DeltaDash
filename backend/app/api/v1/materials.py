from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Material
from app.api.v1.auth import get_current_active_user
from app.schemas.user import User
from app.schemas.material import MaterialCreate, MaterialUpdate, Material, MaterialListItem

router = APIRouter()


@router.get("/", response_model=List[MaterialListItem])
def list_materials(
    skip: int = 0,
    limit: int = 100,
    material_class: str | None = None,
    manufacturer: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Material)
    
    if material_class:
        query = query.filter(Material.material_class == material_class)
    if manufacturer:
        query = query.filter(Material.manufacturer.ilike(f"%{manufacturer}%"))
    
    materials = query.offset(skip).limit(limit).all()
    return materials


@router.post("/", response_model=Material, status_code=status.HTTP_201_CREATED)
def create_material(
    material: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_material = Material(**material.model_dump())
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material


@router.get("/{material_id}", response_model=Material)
def get_material(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.patch("/{material_id}", response_model=Material)
def update_material(
    material_id: str,
    material_update: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    update_data = material_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(material, field, value)
    
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    db.delete(material)
    db.commit()
