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
from app.api.v1.auth import get_current_active_user, require_write_access
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

    materials = query.order_by(MaterialModel.name).offset(skip).limit(limit).all()
    return materials


@router.post("/", response_model=MaterialSchema, status_code=status.HTTP_201_CREATED)
def create_material(
    name: str = Form(...),
    material_class: Optional[str] = Form(None),
    manufacturer: Optional[str] = Form(None),
    areal_density_g_m2: Optional[float] = Form(None),
    thickness_mm: Optional[float] = Form(None),
    thickness_tolerance_mm: Optional[str] = Form(None),
    material_function: Optional[str] = Form(None),
    ply_count: Optional[int] = Form(1),
    ply_orientations: Optional[str] = Form(None),
    elongation_longitudinal_percent: Optional[float] = Form(None),
    elongation_longitudinal_error_percent: Optional[float] = Form(None),
    force_longitudinal_newtons: Optional[float] = Form(None),
    force_longitudinal_error_percent: Optional[float] = Form(None),
    elongation_transverse_percent: Optional[float] = Form(None),
    elongation_transverse_error_percent: Optional[float] = Form(None),
    force_transverse_newtons: Optional[float] = Form(None),
    force_transverse_error_percent: Optional[float] = Form(None),
    stretch_test_length: Optional[str] = Form(None),
    mss_file: Optional[UploadFile] = File(None),
    sds_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    material_data = {
        'name': name,
        'material_class': material_class,
        'manufacturer': manufacturer,
        'areal_density_g_m2': areal_density_g_m2,
        'thickness_mm': thickness_mm,
        'thickness_tolerance_mm': thickness_tolerance_mm,
        'material_function': material_function,
        'ply_count': ply_count,
        'elongation_longitudinal_percent': elongation_longitudinal_percent,
        'elongation_longitudinal_error_percent': elongation_longitudinal_error_percent,
        'force_longitudinal_newtons': force_longitudinal_newtons,
        'force_longitudinal_error_percent': force_longitudinal_error_percent,
        'elongation_transverse_percent': elongation_transverse_percent,
        'elongation_transverse_error_percent': elongation_transverse_error_percent,
        'force_transverse_newtons': force_transverse_newtons,
        'force_transverse_error_percent': force_transverse_error_percent,
        'stretch_test_length': stretch_test_length,
        'created_by_username': current_user.username,
    }

    if ply_orientations:
        try:
            import json
            material_data['ply_orientations'] = json.loads(ply_orientations)
        except (json.JSONDecodeError, TypeError):
            pass

    os.makedirs(settings.material_docs_dir, exist_ok=True)

    if mss_file:
        # Use original filename for storage
        unique_filename = mss_file.filename
        file_path = os.path.join(settings.material_docs_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(mss_file.file.read())
        material_data['mss_file_path'] = unique_filename
        material_data['mss_original_filename'] = mss_file.filename

    if sds_file:
        # Use original filename for storage
        unique_filename = sds_file.filename
        file_path = os.path.join(settings.material_docs_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(sds_file.file.read())
        material_data['sds_file_path'] = unique_filename
        material_data['sds_original_filename'] = sds_file.filename

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
    current_user: UserModel = Depends(require_write_access)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    update_data = material_update.model_dump(exclude_unset=True)
    
    # Convert Decimal values to floats for JSON serialization
    if 'ply_orientations' in update_data and update_data['ply_orientations']:
        update_data['ply_orientations'] = [float(x) for x in update_data['ply_orientations']]
    
    for field, value in update_data.items():
        setattr(material, field, value)
    
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Check if material is referenced by any vest layers
    from app.db.models.vest_layer import VestLayer as VestLayerModel
    vest_layers = db.query(VestLayerModel).filter(VestLayerModel.material_id == material_id).all()
    
    if vest_layers:
        # Clear the material_id from all vest layers that reference this material
        for layer in vest_layers:
            layer.material_id = None
        db.commit()
    
    db.delete(material)
    db.commit()


@router.post("/{material_id}/upload", response_model=MaterialSchema)
def upload_material_file(
    material_id: str,
    mss_file: Optional[UploadFile] = File(None),
    sds_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    os.makedirs(settings.material_docs_dir, exist_ok=True)

    if mss_file:
        # Delete old file if it exists
        if material.mss_file_path:
            old_file_path = os.path.join(settings.material_docs_dir, material.mss_file_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        
        # Use original filename for storage
        unique_filename = mss_file.filename
        file_path = os.path.join(settings.material_docs_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(mss_file.file.read())
        material.mss_file_path = unique_filename
        material.mss_original_filename = mss_file.filename

    if sds_file:
        # Delete old file if it exists
        if material.sds_file_path:
            old_file_path = os.path.join(settings.material_docs_dir, material.sds_file_path)
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        
        # Use original filename for storage
        unique_filename = sds_file.filename
        file_path = os.path.join(settings.material_docs_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(sds_file.file.read())
        material.sds_file_path = unique_filename
        material.sds_original_filename = sds_file.filename

    db.commit()
    db.refresh(material)
    return material


@router.get("/{material_id}/vest-usage")
def get_material_vest_usage(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """Get vests that use this material and layer counts."""
    from app.db.models import Vest, VestLayer
    from collections import defaultdict
    
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    
    # Get all vest layers that use this material
    vest_layers = db.query(VestLayer).filter(VestLayer.material_id == material_id).all()
    
    # Group by vest and sum layer counts
    vest_layer_counts = defaultdict(int)
    vest_info = {}
    for vest_layer in vest_layers:
        vest = db.query(Vest).filter(Vest.id == vest_layer.vest_id).first()
        if vest:
            vest_layer_counts[vest.id] += (vest_layer.layer_count or 1)
            vest_info[vest.id] = {
                "vest_id": vest.id,
                "vest_code": vest.vest_code,
                "vest_name": vest.vest_code,
                "vest_type": vest.vest_type,
                "threat_level": vest.threat_level,
            }
    
    # Build final vest usage list with combined layer counts
    vest_usage = []
    for vest_id, total_layers in vest_layer_counts.items():
        if vest_id in vest_info:
            vest_usage.append({
                **vest_info[vest_id],
                "layer_count": total_layers
            })
    
    return {
        "material_name": material.name,
        "material_class": material.material_class,
        "vest_usage": vest_usage,
        "total_vests": len(vest_usage)
    }


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
        original_filename = material.mss_original_filename
    elif file_type == 'sds':
        file_path = material.sds_file_path
        original_filename = material.sds_original_filename
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")

    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    full_path = os.path.join(settings.material_docs_dir, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Use original filename if available, otherwise use the UUID filename
    download_filename = original_filename if original_filename else file_path

    return FileResponse(full_path, filename=download_filename)


@router.delete("/{material_id}/file/{file_type}", status_code=status.HTTP_204_NO_CONTENT)
def remove_material_file(
    material_id: str,
    file_type: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_write_access)
):
    material = db.query(MaterialModel).filter(MaterialModel.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if file_type == 'mss':
        file_path = material.mss_file_path
        if not file_path:
            raise HTTPException(status_code=404, detail="MSS file not found")
        # Delete file from disk
        full_path = os.path.join(settings.material_docs_dir, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        # Clear database fields
        material.mss_file_path = None
        material.mss_original_filename = None
    elif file_type == 'sds':
        file_path = material.sds_file_path
        if not file_path:
            raise HTTPException(status_code=404, detail="SDS file not found")
        # Delete file from disk
        full_path = os.path.join(settings.material_docs_dir, file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        # Clear database fields
        material.sds_file_path = None
        material.sds_original_filename = None
    else:
        raise HTTPException(status_code=400, detail="Invalid file type")

    db.commit()
