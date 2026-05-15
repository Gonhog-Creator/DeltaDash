from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
import uuid
from pathlib import Path

from app.db.session import get_db
from app.db.models import Material as MaterialModel
from app.db.models.user import User as UserModel
from app.api.v1.auth import get_current_active_user
from app.schemas.material import MaterialCreate, MaterialUpdate, Material as MaterialSchema, MaterialListItem
from app.core.config import settings

router = APIRouter(redirect_slashes=False)


@router.get("/", response_model=List[MaterialListItem])
def list_materials(
    skip: int = 0,
    limit: int = 100,
    material_class: Optional[str] = None,
    manufacturer: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    query = db.query(MaterialModel)
    
    if material_class:
        query = query.filter(MaterialModel.material_class == material_class)
    if manufacturer:
        query = query.filter(MaterialModel.manufacturer.ilike(f"%{manufacturer}%"))
    
    materials = query.offset(skip).limit(limit).all()
    return materials


@router.post("/", response_model=MaterialSchema, status_code=status.HTTP_201_CREATED)
def create_material(
    name: str = Form(...),
    material_class: Optional[str] = Form(None),
    manufacturer: Optional[str] = Form(None),
    areal_density_g_m2: Optional[float] = Form(None),
    thickness_mm: Optional[float] = Form(None),
    material_function: Optional[str] = Form(None),
    mss_file: Optional[UploadFile] = File(None),
    sds_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    material_data = {
        'name': name,
        'material_class': material_class,
        'manufacturer': manufacturer,
        'areal_density_g_m2': areal_density_g_m2,
        'thickness_mm': thickness_mm,
        'material_function': material_function,
        'created_by_username': current_user.username,
    }

    os.makedirs(settings.MATERIAL_DOCS_DIR, exist_ok=True)

    if mss_file:
        file_ext = Path(mss_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.MATERIAL_DOCS_DIR, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(mss_file.file.read())
        material_data['mss_file_path'] = unique_filename

    if sds_file:
        file_ext = Path(sds_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.MATERIAL_DOCS_DIR, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(sds_file.file.read())
        material_data['sds_file_path'] = unique_filename

    db_material = MaterialModel(**material_data)
    db.add(db_material)
    db.commit()
    db.refresh(db_material)
    return db_material


@router.get("/{material_id}", response_model=MaterialSchema)
def get_material(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.patch("/{material_id}", response_model=MaterialSchema)
def update_material(
    material_id: str,
    material_update: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
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
    current_user: UserModel = Depends(get_current_active_user)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    db.delete(material)
    db.commit()


@router.post("/{material_id}/upload", response_model=MaterialSchema)
def upload_material_file(
    material_id: str,
    mss_file: Optional[UploadFile] = File(None),
    sds_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    os.makedirs(settings.MATERIAL_DOCS_DIR, exist_ok=True)

    if mss_file:
        file_ext = Path(mss_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.MATERIAL_DOCS_DIR, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(mss_file.file.read())
        material.mss_file_path = unique_filename

    if sds_file:
        file_ext = Path(sds_file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.MATERIAL_DOCS_DIR, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(sds_file.file.read())
        material.sds_file_path = unique_filename

    db.commit()
    db.refresh(material)
    return material


@router.get("/{material_id}/download/{file_type}")
def download_material_file(
    material_id: str,
    file_type: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    if file_type == 'mss':
        file_path = material.mss_file_path
    elif file_type == 'sds':
        file_path = material.sds_file_path
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    full_path = os.path.join(settings.MATERIAL_DOCS_DIR, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(full_path, filename=file_path)
