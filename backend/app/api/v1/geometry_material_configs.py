from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.db.session import get_db
from app.db.models.geometry_material_config import GeometryMaterialConfig
from app.db.models.geometry import Geometry
from app.db.models.material import Material
from app.api.v1.auth import require_admin

router = APIRouter()


class GeometryMaterialConfigCreate(BaseModel):
    geometry_id: str
    size: str
    material_requirements: List[dict]
    accessories: List[dict]
    efficiency_factor: Optional[float] = None
    notes: Optional[str] = None


class GeometryMaterialConfigUpdate(BaseModel):
    material_requirements: Optional[List[dict]] = None
    accessories: Optional[List[dict]] = None
    efficiency_factor: Optional[float] = None
    notes: Optional[str] = None


class GeometryMaterialConfigResponse(BaseModel):
    id: str
    geometry_id: str
    geometry_name: str
    size: str
    material_requirements: List[dict]
    accessories: List[dict]
    efficiency_factor: Optional[float]
    notes: Optional[str]

    @classmethod
    def from_orm(cls, obj, geometry_name: str):
        return cls(
            id=str(obj.id),
            geometry_id=str(obj.geometry_id),
            geometry_name=geometry_name,
            size=obj.size,
            material_requirements=obj.material_requirements,
            accessories=obj.accessories,
            efficiency_factor=float(obj.efficiency_factor) if obj.efficiency_factor else None,
            notes=obj.notes
        )


@router.get("/", response_model=List[GeometryMaterialConfigResponse])
def get_geometry_material_configs(
    geometry_id: Optional[str] = None,
    size: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get all geometry material configurations, optionally filtered by geometry_id and size."""
    query = db.query(GeometryMaterialConfig)
    
    if geometry_id:
        query = query.filter(GeometryMaterialConfig.geometry_id == uuid.UUID(geometry_id))
    if size:
        query = query.filter(GeometryMaterialConfig.size == size)
    
    configs = query.all()
    
    # Fetch geometry names
    result = []
    for config in configs:
        geometry = db.query(Geometry).filter(Geometry.id == config.geometry_id).first()
        geometry_name = geometry.name if geometry else "Unknown"
        result.append(GeometryMaterialConfigResponse.from_orm(config, geometry_name))
    
    return result


@router.get("/{config_id}", response_model=GeometryMaterialConfigResponse)
def get_geometry_material_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get a specific geometry material configuration by ID."""
    config = db.query(GeometryMaterialConfig).filter(GeometryMaterialConfig.id == uuid.UUID(config_id)).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    geometry = db.query(Geometry).filter(Geometry.id == config.geometry_id).first()
    geometry_name = geometry.name if geometry else "Unknown"
    
    return GeometryMaterialConfigResponse.from_orm(config, geometry_name)


@router.post("/", response_model=GeometryMaterialConfigResponse)
def create_geometry_material_config(
    config: GeometryMaterialConfigCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Create a new geometry material configuration."""
    # Validate geometry exists
    geometry = db.query(Geometry).filter(Geometry.id == uuid.UUID(config.geometry_id)).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")
    
    # Check if config already exists for this geometry/size combination
    existing = db.query(GeometryMaterialConfig).filter(
        GeometryMaterialConfig.geometry_id == uuid.UUID(config.geometry_id),
        GeometryMaterialConfig.size == config.size
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Configuration already exists for this geometry and size")
    
    # Validate material IDs exist
    for req in config.material_requirements:
        if "material_id" in req:
            material = db.query(Material).filter(Material.id == uuid.UUID(req["material_id"])).first()
            if not material:
                raise HTTPException(status_code=400, detail=f"Material {req['material_id']} not found")
    
    for acc in config.accessories:
        if "material_id" in acc:
            material = db.query(Material).filter(Material.id == uuid.UUID(acc["material_id"])).first()
            if not material:
                raise HTTPException(status_code=400, detail=f"Material {acc['material_id']} not found")
    
    new_config = GeometryMaterialConfig(
        geometry_id=uuid.UUID(config.geometry_id),
        size=config.size,
        material_requirements=config.material_requirements,
        accessories=config.accessories,
        efficiency_factor=config.efficiency_factor,
        notes=config.notes
    )
    
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    
    return GeometryMaterialConfigResponse.from_orm(new_config, geometry.name)


@router.put("/{config_id}", response_model=GeometryMaterialConfigResponse)
def update_geometry_material_config(
    config_id: str,
    config_update: GeometryMaterialConfigUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Update an existing geometry material configuration."""
    config = db.query(GeometryMaterialConfig).filter(GeometryMaterialConfig.id == uuid.UUID(config_id)).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    if config_update.material_requirements is not None:
        # Validate material IDs exist
        for req in config_update.material_requirements:
            if "material_id" in req:
                material = db.query(Material).filter(Material.id == uuid.UUID(req["material_id"])).first()
                if not material:
                    raise HTTPException(status_code=400, detail=f"Material {req['material_id']} not found")
        config.material_requirements = config_update.material_requirements
    
    if config_update.accessories is not None:
        # Validate material IDs exist
        for acc in config_update.accessories:
            if "material_id" in acc:
                material = db.query(Material).filter(Material.id == uuid.UUID(acc["material_id"])).first()
                if not material:
                    raise HTTPException(status_code=400, detail=f"Material {acc['material_id']} not found")
        config.accessories = config_update.accessories
    
    if config_update.efficiency_factor is not None:
        config.efficiency_factor = config_update.efficiency_factor
    
    if config_update.notes is not None:
        config.notes = config_update.notes
    
    db.commit()
    db.refresh(config)
    
    geometry = db.query(Geometry).filter(Geometry.id == config.geometry_id).first()
    geometry_name = geometry.name if geometry else "Unknown"
    
    return GeometryMaterialConfigResponse.from_orm(config, geometry_name)


@router.delete("/{config_id}")
def delete_geometry_material_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Delete a geometry material configuration."""
    config = db.query(GeometryMaterialConfig).filter(GeometryMaterialConfig.id == uuid.UUID(config_id)).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    db.delete(config)
    db.commit()
    
    return {"message": "Configuration deleted successfully"}
