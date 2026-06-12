from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.db.models.geometry import Geometry
from app.db.models.geometry_material_config import GeometryMaterialConfig
from app.db.models.vest import Vest
from app.db.models.vest_layer import VestLayer
from app.db.models.material import Material
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User

router = APIRouter()


class FabricCalculationRequest(BaseModel):
    vest_id: Optional[str] = None
    custom_vest: Optional[Dict[str, Any]] = None
    geometry_id: str
    size: str
    quantity: int
    efficiency_factor: float = 1.15


class MaterialRequirement(BaseModel):
    material_id: str
    material_name: str
    area_m2: float
    weight_kg: float
    cost: Optional[float] = None
    roll_count: Optional[int] = None


class FabricCalculationResponse(BaseModel):
    total_fabric_area_m2: float
    total_weight_kg: float
    total_cost: Optional[float]
    efficiency_factor: float
    quantity: int
    size: str
    geometry_name: str
    by_material: List[MaterialRequirement]
    breakdown: Dict[str, Any]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/calculate", response_model=FabricCalculationResponse)
def calculate_fabric_requirements(
    request: FabricCalculationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Calculate fabric and material requirements for vest production"""
    
    # Validate inputs
    if not request.vest_id and not request.custom_vest:
        raise HTTPException(status_code=400, detail="Either vest_id or custom_vest must be provided")
    
    if request.efficiency_factor < 1.0:
        raise HTTPException(status_code=400, detail="Efficiency factor must be >= 1.0")
    
    # Get geometry
    geometry = db.query(Geometry).filter(Geometry.id == request.geometry_id).first()
    if not geometry:
        raise HTTPException(status_code=404, detail="Geometry not found")
    
    # Validate size is available for this geometry
    if request.size not in geometry.available_sizes:
        raise HTTPException(
            status_code=400, 
            detail=f"Size {request.size} not available for geometry {geometry.name}. Available sizes: {geometry.available_sizes}"
        )
    
    # Get surface area for the selected size
    size_data = geometry.surface_areas.get(request.size)
    if not size_data:
        raise HTTPException(status_code=400, detail=f"No surface area data for size {request.size}")
    
    # Calculate total panel area (front + back)
    front_area = size_data.get("front", 0)
    back_area = size_data.get("back", 0)
    total_panel_area_per_vest = front_area + back_area
    
    # Check for geometry material configuration (for carrier/accessories)
    geometry_config = db.query(GeometryMaterialConfig).filter(
        GeometryMaterialConfig.geometry_id == request.geometry_id,
        GeometryMaterialConfig.size == request.size
    ).first()
    
    # If no size-specific config, check for "ALL" sizes config
    if not geometry_config:
        geometry_config = db.query(GeometryMaterialConfig).filter(
            GeometryMaterialConfig.geometry_id == request.geometry_id,
            GeometryMaterialConfig.size == "ALL"
        ).first()
    
    # Use config efficiency factor if available, otherwise use request
    efficiency_factor = geometry_config.efficiency_factor if geometry_config and geometry_config.efficiency_factor else request.efficiency_factor
    
    # Get vest composition (ballistic layers with materials)
    # Geometry config is ONLY for carrier/accessories, not ballistic materials
    if request.vest_id:
        vest = db.query(Vest).filter(Vest.id == request.vest_id).first()
        if not vest:
            raise HTTPException(status_code=404, detail="Vest not found")
        
        vest_layers = db.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
    else:
        # Use custom vest
        vest_layers = request.custom_vest.get("layers", [])
    
    # Calculate material requirements (aggregated by material)
    material_totals: Dict[str, Dict[str, float]] = {}
    total_weight_kg = 0
    total_cost = 0
    
    for layer in vest_layers:
        material_id = layer.material_id if hasattr(layer, 'material_id') else layer.get("material_id")
        layer_count = layer.layer_count if hasattr(layer, 'layer_count') else layer.get("layer_count", 1)
        
        if not material_id:
            continue
        
        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            continue
        
        # Calculate area for this material
        material_area_m2 = total_panel_area_per_vest * layer_count * request.quantity
        
        # Apply efficiency factor (only for soft armor components)
        if not geometry.includes_hard_plates:
            material_area_m2 *= efficiency_factor
        
        # Calculate weight
        material_weight_kg = 0
        if material.areal_density_g_m2:
            material_weight_kg = (material_area_m2 * float(material.areal_density_g_m2)) / 1000  # Convert g/m² to kg
        
        # Calculate cost
        material_cost = None
        if material.price_per_m2:
            material_cost = material_area_m2 * float(material.price_per_m2)
            total_cost += material_cost
        
        total_weight_kg += material_weight_kg
        
        # Aggregate by material
        if material_id not in material_totals:
            material_totals[material_id] = {
                "area_m2": 0,
                "weight_kg": 0,
                "cost": 0,
                "name": material.name
            }
        
        material_totals[material_id]["area_m2"] += material_area_m2
        material_totals[material_id]["weight_kg"] += material_weight_kg
        if material_cost:
            material_totals[material_id]["cost"] += material_cost
    
    # Add accessories from geometry configuration
    if geometry_config and geometry_config.accessories:
        for acc in geometry_config.accessories:
            material_id = acc.get("material_id")
            quantity_per_vest = acc.get("quantity_per_vest", 0)
            unit = acc.get("unit", "meters")
            
            if not material_id or quantity_per_vest <= 0:
                continue
            
            material = db.query(Material).filter(Material.id == material_id).first()
            if not material:
                continue
            
            # Calculate total quantity
            total_quantity = quantity_per_vest * request.quantity
            
            # Calculate area/weight based on unit type
            if unit == "meters":
                # For linear materials like velcro, calculate area based on width if available
                # For now, we'll just track the quantity
                material_area_m2 = 0  # Can't calculate area without width
            else:
                # For pieces/pairs, no area calculation
                material_area_m2 = 0
            
            # Calculate weight based on areal density if applicable
            material_weight_kg = 0
            if material.areal_density_g_m2 and material_area_m2 > 0:
                material_weight_kg = (material_area_m2 * float(material.areal_density_g_m2)) / 1000
            
            # Calculate cost if price per m2 is available
            material_cost = None
            if material.price_per_m2 and material_area_m2 > 0:
                material_cost = material_area_m2 * float(material.price_per_m2)
                total_cost += material_cost
            
            total_weight_kg += material_weight_kg
            
            # Aggregate by material
            if material_id not in material_totals:
                material_totals[material_id] = {
                    "area_m2": 0,
                    "weight_kg": 0,
                    "cost": 0,
                    "name": material.name
                }
            
            material_totals[material_id]["area_m2"] += material_area_m2
            material_totals[material_id]["weight_kg"] += material_weight_kg
            if material_cost:
                material_totals[material_id]["cost"] += material_cost
    
    # Add outer carrier fabric if configured
    if geometry.outer_carrier_material_id and geometry.outer_carrier_layer_count:
        outer_carrier = db.query(Material).filter(Material.id == geometry.outer_carrier_material_id).first()
        if outer_carrier:
            # Outer carrier uses the total panel area (front + back) for each vest
            outer_carrier_area_m2 = total_panel_area_per_vest * geometry.outer_carrier_layer_count * request.quantity
            
            # Apply efficiency factor for outer carrier
            if not geometry.includes_hard_plates:
                outer_carrier_area_m2 *= efficiency_factor
            
            # Calculate weight
            outer_carrier_weight_kg = 0
            if outer_carrier.areal_density_g_m2:
                outer_carrier_weight_kg = (outer_carrier_area_m2 * float(outer_carrier.areal_density_g_m2)) / 1000
            
            # Calculate cost
            outer_carrier_cost = None
            if outer_carrier.price_per_m2:
                outer_carrier_cost = outer_carrier_area_m2 * float(outer_carrier.price_per_m2)
                total_cost += outer_carrier_cost
            
            total_weight_kg += outer_carrier_weight_kg
            
            # Aggregate outer carrier
            outer_carrier_id_str = str(geometry.outer_carrier_material_id)
            if outer_carrier_id_str not in material_totals:
                material_totals[outer_carrier_id_str] = {
                    "area_m2": 0,
                    "weight_kg": 0,
                    "cost": 0,
                    "name": outer_carrier.name
                }
            
            material_totals[outer_carrier_id_str]["area_m2"] += outer_carrier_area_m2
            material_totals[outer_carrier_id_str]["weight_kg"] += outer_carrier_weight_kg
            if outer_carrier_cost:
                material_totals[outer_carrier_id_str]["cost"] += outer_carrier_cost
    
    # Convert aggregated totals to material requirements list
    material_requirements: List[MaterialRequirement] = []
    for material_id, totals in material_totals.items():
        # Calculate roll count if roll area is available
        material = db.query(Material).filter(Material.id == material_id).first()
        roll_count = None
        if material and material.roll_area_m2 and material.roll_area_m2 > 0:
            roll_count = int((totals["area_m2"] + float(material.roll_area_m2) - 1) // float(material.roll_area_m2))  # Round up
        
        material_requirements.append(MaterialRequirement(
            material_id=str(material_id),
            material_name=totals["name"],
            area_m2=round(totals["area_m2"], 4),
            weight_kg=round(totals["weight_kg"], 4),
            cost=round(totals["cost"], 2) if totals["cost"] > 0 else None,
            roll_count=roll_count
        ))
    
    # Calculate totals
    total_fabric_area_m2 = sum(req.area_m2 for req in material_requirements)
    
    # Create breakdown
    breakdown = {
        "geometry": {
            "name": geometry.name,
            "vest_type": geometry.vest_type,
            "size": request.size,
            "front_area_m2": front_area,
            "back_area_m2": back_area,
            "total_panel_area_m2": total_panel_area_per_vest
        },
        "production": {
            "quantity": request.quantity,
            "efficiency_factor": efficiency_factor,
            "includes_hard_plates": geometry.includes_hard_plates
        },
        "layers": [
            {
                "material_id": str(layer.material_id) if hasattr(layer, 'material_id') else layer.get("material_id"),
                "layer_count": layer.layer_count if hasattr(layer, 'layer_count') else layer.get("layer_count", 1)
            }
            for layer in vest_layers
        ]
    }
    
    return FabricCalculationResponse(
        total_fabric_area_m2=round(total_fabric_area_m2, 4),
        total_weight_kg=round(total_weight_kg, 4),
        total_cost=round(total_cost, 2) if total_cost else None,
        efficiency_factor=request.efficiency_factor,
        quantity=request.quantity,
        size=request.size,
        geometry_name=geometry.name,
        by_material=material_requirements,
        breakdown=breakdown
    )
