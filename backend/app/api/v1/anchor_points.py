from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.session import get_db
from app.db.models import AnchorPoint, AnchorPointLayer, Material, Ammunition, User
from app.api.v1.auth import get_current_active_user, require_write_access


router = APIRouter(prefix="/anchor-points", tags=["anchor-points"])


# =============================================================================
# Schemas
# =============================================================================

class AnchorPointLayerCreate(BaseModel):
    material_id: str = Field(..., description="Material ID")
    layer_count: int = Field(..., ge=1, description="Number of layers")
    layer_index: int = Field(..., ge=0, description="Order in composition")


class AnchorPointCreate(BaseModel):
    name: str = Field(..., description="Anchor point name")
    description: Optional[str] = Field(None, description="Description")
    ammunition_scope: str = Field("all", description="'all' or 'calibers'")
    caliber_ids: Optional[List[str]] = Field(None, description="List of caliber strings for 'calibers' scope")
    expected_perforated: bool = Field(..., description="Expected perforation outcome")
    expected_bfd_mm: Optional[float] = Field(None, description="Expected BFD if not perforated")
    custom_velocity_mps: Optional[float] = Field(None, description="Custom velocity override")
    layers: List[AnchorPointLayerCreate] = Field(..., description="Material composition")


class AnchorPointUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ammunition_scope: Optional[str] = None
    caliber_ids: Optional[List[str]] = None
    expected_perforated: Optional[bool] = None
    expected_bfd_mm: Optional[float] = None
    custom_velocity_mps: Optional[float] = None
    layers: Optional[List[AnchorPointLayerCreate]] = None
    batch_id: Optional[str] = None


class AnchorPointLayerResponse(BaseModel):
    id: str
    material_id: str
    material_name: str
    layer_count: int
    layer_index: int


class AnchorPointResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    ammunition_scope: str
    caliber_ids: Optional[List[str]]
    expected_perforated: bool
    expected_bfd_mm: Optional[float]
    custom_velocity_mps: Optional[float]
    layers: List[AnchorPointLayerResponse]
    created_by_id: str
    created_by_username: str
    created_at: str
    updated_at: str
    batch_id: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=List[AnchorPointResponse])
def list_anchor_points(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """List all anchor points."""
    anchor_points = db.query(AnchorPoint).order_by(AnchorPoint.created_at.desc()).all()
    
    result = []
    for ap in anchor_points:
        # Get layers with material names
        layers = db.query(AnchorPointLayer, Material).join(
            Material, AnchorPointLayer.material_id == Material.id
        ).filter(AnchorPointLayer.anchor_point_id == ap.id).order_by(AnchorPointLayer.layer_index).all()
        
        layer_responses = []
        for apl, material in layers:
            layer_responses.append(AnchorPointLayerResponse(
                id=str(apl.id),
                material_id=str(apl.material_id),
                material_name=material.name,
                layer_count=apl.layer_count,
                layer_index=apl.layer_index
            ))
        
        # Get creator username
        creator = db.query(User).filter(User.id == ap.created_by_id).first()
        creator_name = creator.username if creator else "Unknown"
        
        result.append(AnchorPointResponse(
            id=str(ap.id),
            name=ap.name,
            description=ap.description,
            ammunition_scope=ap.ammunition_scope,
            caliber_ids=ap.caliber_ids,
            expected_perforated=ap.expected_perforated,
            expected_bfd_mm=float(ap.expected_bfd_mm) if ap.expected_bfd_mm else None,
            custom_velocity_mps=float(ap.custom_velocity_mps) if ap.custom_velocity_mps else None,
            layers=layer_responses,
            created_by_id=str(ap.created_by_id),
            created_by_username=creator_name,
            created_at=ap.created_at.isoformat(),
            updated_at=ap.updated_at.isoformat(),
            batch_id=str(ap.batch_id) if ap.batch_id else None
        ))
    
    return result


@router.get("/{anchor_point_id}", response_model=AnchorPointResponse)
def get_anchor_point(
    anchor_point_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific anchor point."""
    anchor_point = db.query(AnchorPoint).filter(AnchorPoint.id == uuid.UUID(anchor_point_id)).first()
    if not anchor_point:
        raise HTTPException(status_code=404, detail="Anchor point not found")
    
    # Get layers with material names
    layers = db.query(AnchorPointLayer, Material).join(
        Material, AnchorPointLayer.material_id == Material.id
    ).filter(AnchorPointLayer.anchor_point_id == anchor_point.id).order_by(AnchorPointLayer.layer_index).all()
    
    layer_responses = []
    for apl, material in layers:
        layer_responses.append(AnchorPointLayerResponse(
            id=str(apl.id),
            material_id=str(apl.material_id),
            material_name=material.name,
            layer_count=apl.layer_count,
            layer_index=apl.layer_index
        ))
    
    # Get creator username
    creator = db.query(User).filter(User.id == anchor_point.created_by_id).first()
    creator_name = creator.username if creator else "Unknown"

    return AnchorPointResponse(
        id=str(anchor_point.id),
        name=anchor_point.name,
        description=anchor_point.description,
        ammunition_scope=anchor_point.ammunition_scope,
        caliber_ids=anchor_point.caliber_ids,
        expected_perforated=anchor_point.expected_perforated,
        expected_bfd_mm=float(anchor_point.expected_bfd_mm) if anchor_point.expected_bfd_mm else None,
        custom_velocity_mps=float(anchor_point.custom_velocity_mps) if anchor_point.custom_velocity_mps else None,
        layers=layer_responses,
        created_by_id=str(anchor_point.created_by_id),
        created_by_username=creator_name,
        created_at=anchor_point.created_at.isoformat(),
        updated_at=anchor_point.updated_at.isoformat(),
        batch_id=str(anchor_point.batch_id) if anchor_point.batch_id else None
    )


@router.post("/batch", response_model=List[AnchorPointResponse], status_code=status.HTTP_201_CREATED)
def create_anchor_points_batch(
    anchor_point: AnchorPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access)
):
    """Create multiple anchor points - one for each material in the composition."""
    # Validate ammunition scope
    if anchor_point.ammunition_scope not in ['all', 'calibers']:
        raise HTTPException(status_code=400, detail="ammunition_scope must be 'all' or 'calibers'")
    
    # Validate that calibers scope has caliber_ids
    if anchor_point.ammunition_scope == 'calibers' and not anchor_point.caliber_ids:
        raise HTTPException(status_code=400, detail="caliber_ids required for 'calibers' scope")
    
    # Validate that perforated=True doesn't have BFD
    if anchor_point.expected_perforated and anchor_point.expected_bfd_mm is not None:
        raise HTTPException(status_code=400, detail="expected_bfd_mm should be None when expected_perforated is True")
    
    # Validate that perforated=False has BFD
    if not anchor_point.expected_perforated and anchor_point.expected_bfd_mm is None:
        raise HTTPException(status_code=400, detail="expected_bfd_mm required when expected_perforated is False")
    
    # Validate materials exist
    material_ids = [layer.material_id for layer in anchor_point.layers]
    materials = db.query(Material).filter(Material.id.in_([uuid.UUID(mid) for mid in material_ids])).all()
    if len(materials) != len(material_ids):
        raise HTTPException(status_code=400, detail="One or more materials not found")
    
    # Validate caliber ids exist for calibers scope
    if anchor_point.ammunition_scope == 'calibers':
        unique_calibers = db.query(Ammunition.caliber).distinct().filter(Ammunition.caliber.in_(anchor_point.caliber_ids)).all()
        if len(unique_calibers) != len(anchor_point.caliber_ids):
            raise HTTPException(status_code=400, detail="One or more calibers not found")
    elif anchor_point.ammunition_scope == 'all':
        # Populate caliber_ids with all current calibers
        all_calibers = db.query(Ammunition.caliber).distinct().all()
        anchor_point.caliber_ids = [c[0] for c in all_calibers if c[0]]
    
    # Create a separate anchor point for each material layer
    created_anchors = []
    batch_id = uuid.uuid4()  # Generate a single batch ID for all created anchor points
    
    for layer in anchor_point.layers:
        # Find the material for this layer
        material = next((m for m in materials if str(m.id) == layer.material_id), None)
        if not material:
            raise HTTPException(status_code=400, detail=f"Material not found for layer {layer.material_id}")
        
        db_anchor_point = AnchorPoint(
            name=f"{anchor_point.name} - {layer.layer_count}x {material.name}",
            description=anchor_point.description,
            ammunition_scope=anchor_point.ammunition_scope,
            caliber_ids=anchor_point.caliber_ids,
            expected_perforated=anchor_point.expected_perforated,
            expected_bfd_mm=anchor_point.expected_bfd_mm,
            custom_velocity_mps=anchor_point.custom_velocity_mps,
            created_by_id=current_user.id,
            batch_id=batch_id
        )
        db.add(db_anchor_point)
        db.flush()
        
        # Create single layer for this anchor point
        db_layer = AnchorPointLayer(
            anchor_point_id=db_anchor_point.id,
            material_id=uuid.UUID(layer.material_id),
            layer_count=layer.layer_count,
            layer_index=0
        )
        db.add(db_layer)
        
        created_anchors.append(db_anchor_point)
    
    db.commit()
    
    # Return all created anchor points
    result = []
    for db_anchor_point in created_anchors:
        result.append(get_anchor_point(str(db_anchor_point.id), db, current_user))
    
    return result


@router.post("/", response_model=AnchorPointResponse, status_code=status.HTTP_201_CREATED)
def create_anchor_point(
    anchor_point: AnchorPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access)
):
    """Create a new anchor point."""
    # Validate ammunition scope
    if anchor_point.ammunition_scope not in ['all', 'calibers']:
        raise HTTPException(status_code=400, detail="ammunition_scope must be 'all' or 'calibers'")
    
    # Validate that calibers scope has caliber_ids
    if anchor_point.ammunition_scope == 'calibers' and not anchor_point.caliber_ids:
        raise HTTPException(status_code=400, detail="caliber_ids required for 'calibers' scope")
    
    # Validate that perforated=True doesn't have BFD
    if anchor_point.expected_perforated and anchor_point.expected_bfd_mm is not None:
        raise HTTPException(status_code=400, detail="expected_bfd_mm should be None when expected_perforated is True")
    
    # Validate that perforated=False has BFD
    if not anchor_point.expected_perforated and anchor_point.expected_bfd_mm is None:
        raise HTTPException(status_code=400, detail="expected_bfd_mm required when expected_perforated is False")
    
    # Validate materials exist
    material_ids = [layer.material_id for layer in anchor_point.layers]
    materials = db.query(Material).filter(Material.id.in_([uuid.UUID(mid) for mid in material_ids])).all()
    if len(materials) != len(material_ids):
        raise HTTPException(status_code=400, detail="One or more materials not found")
    
    # Validate caliber ids exist for calibers scope
    if anchor_point.ammunition_scope == 'calibers':
        unique_calibers = db.query(Ammunition.caliber).distinct().filter(Ammunition.caliber.in_(anchor_point.caliber_ids)).all()
        if len(unique_calibers) != len(anchor_point.caliber_ids):
            raise HTTPException(status_code=400, detail="One or more calibers not found")
    
    # Create anchor point
    db_anchor_point = AnchorPoint(
        name=anchor_point.name,
        description=anchor_point.description,
        ammunition_scope=anchor_point.ammunition_scope,
        caliber_ids=anchor_point.caliber_ids,
        expected_perforated=anchor_point.expected_perforated,
        expected_bfd_mm=anchor_point.expected_bfd_mm,
        custom_velocity_mps=anchor_point.custom_velocity_mps,
        created_by_id=current_user.id
    )
    db.add(db_anchor_point)
    db.flush()
    
    # Create layers
    for layer in anchor_point.layers:
        db_layer = AnchorPointLayer(
            anchor_point_id=db_anchor_point.id,
            material_id=uuid.UUID(layer.material_id),
            layer_count=layer.layer_count,
            layer_index=layer.layer_index
        )
        db.add(db_layer)
    
    db.commit()
    db.refresh(db_anchor_point)
    
    return get_anchor_point(str(db_anchor_point.id), db, current_user)


@router.put("/{anchor_point_id}", response_model=AnchorPointResponse)
def update_anchor_point(
    anchor_point_id: str,
    anchor_point: AnchorPointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access)
):
    """Update an anchor point."""
    db_anchor_point = db.query(AnchorPoint).filter(AnchorPoint.id == uuid.UUID(anchor_point_id)).first()
    if not db_anchor_point:
        raise HTTPException(status_code=404, detail="Anchor point not found")
    
    update_data = anchor_point.model_dump(exclude_unset=True)
    
    # Handle layers separately
    layers_data = update_data.pop('layers', None)
    
    # Validate ammunition scope if provided
    if 'ammunition_scope' in update_data:
        if update_data['ammunition_scope'] not in ['all', 'calibers']:
            raise HTTPException(status_code=400, detail="ammunition_scope must be 'all' or 'calibers'")
    
    # Validate perforation/BFD consistency
    if 'expected_perforated' in update_data or 'expected_bfd_mm' in update_data:
        perforated = update_data.get('expected_perforated', db_anchor_point.expected_perforated)
        bfd = update_data.get('expected_bfd_mm', db_anchor_point.expected_bfd_mm)
        if perforated and bfd is not None:
            raise HTTPException(status_code=400, detail="expected_bfd_mm should be None when expected_perforated is True")
        if not perforated and bfd is None:
            raise HTTPException(status_code=400, detail="expected_bfd_mm required when expected_perforated is False")
    
    # Validate caliber ids exist for calibers scope
    if 'caliber_ids' in update_data and update_data['caliber_ids'] is not None:
        if update_data.get('ammunition_scope', db_anchor_point.ammunition_scope) == 'calibers':
            unique_calibers = db.query(Ammunition.caliber).distinct().filter(Ammunition.caliber.in_(update_data['caliber_ids'])).all()
            if len(unique_calibers) != len(update_data['caliber_ids']):
                raise HTTPException(status_code=400, detail="One or more calibers not found")
        elif update_data.get('ammunition_scope', db_anchor_point.ammunition_scope) == 'all':
            # Populate caliber_ids with all current calibers
            all_calibers = db.query(Ammunition.caliber).distinct().all()
            update_data['caliber_ids'] = [c[0] for c in all_calibers if c[0]]
    
    # Update fields
    for field, value in update_data.items():
        setattr(db_anchor_point, field, value)
    
    # Update layers if provided
    if layers_data is not None:
        # Delete existing layers
        db.query(AnchorPointLayer).filter(AnchorPointLayer.anchor_point_id == db_anchor_point.id).delete()
        
        # Validate materials exist
        material_ids = [layer.material_id for layer in layers_data]
        materials = db.query(Material).filter(Material.id.in_([uuid.UUID(mid) for mid in material_ids])).all()
        if len(materials) != len(material_ids):
            raise HTTPException(status_code=400, detail="One or more materials not found")
        
        # Create new layers
        for layer in layers_data:
            db_layer = AnchorPointLayer(
                anchor_point_id=db_anchor_point.id,
                material_id=uuid.UUID(layer.material_id),
                layer_count=layer.layer_count,
                layer_index=layer.layer_index
            )
            db.add(db_layer)
    
    db.commit()
    db.refresh(db_anchor_point)
    
    return get_anchor_point(str(db_anchor_point.id), db, current_user)


@router.delete("/{anchor_point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_anchor_point(
    anchor_point_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access)
):
    """Delete an anchor point."""
    db_anchor_point = db.query(AnchorPoint).filter(AnchorPoint.id == uuid.UUID(anchor_point_id)).first()
    if not db_anchor_point:
        raise HTTPException(status_code=404, detail="Anchor point not found")
    
    # Layers will be cascade deleted
    db.delete(db_anchor_point)
    db.commit()
    
    return None
