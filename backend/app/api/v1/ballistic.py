"""
Ballistic ML API endpoints - database-driven training and prediction.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import os
import json

from app.db.session import get_db
from app.services.ml.ballistic_ml import train_from_database, predict, load_metadata, fetch_material_properties, list_model_versions, load_model_version, predict_with_version, predict_with_version_multi_shot, delete_model_version, update_model_name, VERSIONS_DIR


router = APIRouter(prefix="/ballistic", tags=["ballistic"])


# =============================================================================
# API schemas
# =============================================================================

class BallisticInput(BaseModel):
    """
    Input variables for one prediction.
    Note: material_thickness_mm and material_weight_g_m2 are derived from vest_composition
    and should not be provided as inputs.
    """
    number_of_layers: int = Field(..., examples=[48])

    vest_composition: str = Field(
        ...,
        examples=["40 SOFT3000 + 2 UD245 + 1 PE Espumado + 5 SOFT3000"],
    )

    ammunition_used: str = Field(..., examples=[".44 MAG"])
    threat_level: Optional[str] = Field(None, examples=["RB3"])
    shot_number: int = Field(..., examples=[1])

    # Optional variables
    impact_velocity_mps: Optional[float] = Field(None, examples=[434.6])
    impact_angle_deg: Optional[float] = Field(0.0, examples=[0.0])
    bullet_mass_g: Optional[float] = Field(None, examples=[15.6])

    temperature_c: Optional[float] = Field(22.0, examples=[22.0])
    humidity_pct: Optional[float] = Field(50.0, examples=[50.0])

    condition: Optional[str] = Field(None, examples=["Ambient", "Humid"])
    panel_side: Optional[str] = Field(None, examples=["front", "back"])

    # Optional geometry
    panel_width_mm: Optional[float] = None
    panel_height_mm: Optional[float] = None
    plate_curvature_mm: Optional[float] = None

    # Optional shot position
    shot_x_position_mm: Optional[float] = None
    shot_y_position_mm: Optional[float] = None
    edge_distance_mm: Optional[float] = None
    previous_shot_distance_mm: Optional[float] = None

    # Optional material properties (if not using vest_composition)
    fabric_elongation_pct: Optional[float] = None
    fabric_strain_pct: Optional[float] = None
    max_tensile_strength_mpa: Optional[float] = None
    fiber_thickness_um: Optional[float] = None
    epoxy_percentage: Optional[float] = None
    fiber_orientation_deg: Optional[float] = None


class ProtocolPredictionInput(BaseModel):
    """Input for prediction using a protocol."""
    vest_id: str = Field(..., examples=["uuid-of-vest"])
    protocol_id: str = Field(..., examples=["uuid-of-protocol"])
    level_index: Optional[int] = Field(None, examples=[0, 1, 2])


class PredictionResponse(BaseModel):
    predicted_backface_deformation_mm: Optional[float]
    estimated_backface_absolute_error_mm: Optional[float]
    backface_prediction_lower_80_mm: Optional[float]
    backface_prediction_upper_80_mm: Optional[float]
    backface_prediction_lower_95_mm: Optional[float]
    backface_prediction_upper_95_mm: Optional[float]
    conservative_backface_deformation_upper_mm: Optional[float]
    perforation_probability: Optional[float]
    perforation_probability_estimated_error: Optional[float]
    fail_probability: Optional[float]
    fail_probability_estimated_error: Optional[float]
    recommendation: str
    confidence_note: str
    warning: str


class HealthResponse(BaseModel):
    status: str
    trained_at: Optional[str]
    version: Optional[str]
    regression_targets: list
    classification_targets: list
    feature_count: int
    material_count: int
    shot_count: int
    vest_count: int
    vest_layer_count: int
    data_health: Optional[dict] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=dict)
def root():
    return {
        "message": "Ballistic ML API",
        "version": "2.0.0",
        "description": "Database-driven ballistic vest prediction API",
        "endpoints": {
            "health": "GET /health",
            "train": "POST /train",
            "predict": "POST /predict",
            "metrics": "GET /metrics",
        }
    }


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    """Check model status and database connection."""
    from app.db.models import ShotData, Vest, Material, VestLayer
    
    metadata = load_metadata()
    material_properties = fetch_material_properties(db)
    
    # Get database counts for debugging
    shot_data_count = db.query(ShotData).count()
    vest_count = db.query(Vest).count()
    material_count = db.query(Material).count()
    vest_layer_count = db.query(VestLayer).count()
    
    if not metadata:
        return HealthResponse(
            status="not_trained",
            trained_at=None,
            version=None,
            regression_targets=[],
            classification_targets=[],
            feature_count=0,
            material_count=len(material_properties),
            shot_count=shot_data_count,
            vest_count=vest_count,
            vest_layer_count=vest_layer_count,
            data_health=None,
        )
    
    return HealthResponse(
        status="trained",
        trained_at=metadata.get("trained_at"),
        version=metadata.get("version"),
        regression_targets=metadata.get("regression_targets", []),
        classification_targets=metadata.get("classification_targets", []),
        feature_count=len(metadata.get("feature_columns", [])),
        material_count=len(material_properties),
        shot_count=shot_data_count,
        vest_count=vest_count,
        vest_layer_count=vest_layer_count,
        data_health=metadata.get("data_health"),
    )


@router.post("/train")
def train(db: Session = Depends(get_db), model_name: Optional[str] = None):
    """
    Train ML model using data from database.
    Fetches shots, vests, materials, ammunition, and test sessions from DB.
    Optional model_name parameter to give the model a friendly name.
    """
    try:
        metadata = train_from_database(db, model_name=model_name)
        return {
            "status": "success",
            "message": "Model trained successfully",
            "metadata": metadata,
            "warnings": metadata.get("warnings", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.post("/predict")
def predict_endpoint(data: BallisticInput, db: Session = Depends(get_db), version: Optional[str] = None):
    """
    Make a prediction using the trained model.
    Material properties are fetched dynamically from database.
    Optional version parameter to use a specific model version.
    Returns predictions for all 6 shots.
    """
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run /train first.",
        )

    # Get material properties from database
    material_properties = fetch_material_properties(db)

    if not material_properties:
        raise HTTPException(
            status_code=400,
            detail="No materials found in database. Please add materials with properties.",
        )

    # Make multi-shot prediction with optional version
    if version:
        return predict_with_version_multi_shot(data.model_dump(), material_properties, version)
    else:
        from app.services.ml.ballistic_ml import predict_multi_shot
        return predict_multi_shot(data.model_dump(), material_properties)


@router.post("/predict-protocol")
def predict_protocol_endpoint(data: ProtocolPredictionInput, db: Session = Depends(get_db), version: Optional[str] = None):
    """
    Make predictions using a protocol.
    Returns predictions for all shots in the protocol level (front/back, dry/wet for each ammunition).
    Optional version parameter to use a specific model version.
    """
    from ml.prediction_service import PredictionService

    prediction_service = PredictionService(db)
    
    try:
        result = prediction_service.predict_bfd_for_protocol(data.vest_id, data.protocol_id, data.level_index, version)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/health/version/{version}", response_model=HealthResponse)
def health_version(version: str, db: Session = Depends(get_db)):
    """Check model status for a specific version."""
    from app.db.models import ShotData, Vest, Material, VestLayer
    
    # Load the specific version metadata
    version_dir = os.path.join(VERSIONS_DIR, version)
    if not os.path.exists(version_dir):
        return HealthResponse(
            status="not_found",
            trained_at=None,
            version=None,
            regression_targets=[],
            classification_targets=[],
            feature_count=0,
            material_count=0,
            shot_count=0,
            vest_count=0,
            vest_layer_count=0,
            data_health=None,
        )
    
    version_metadata_path = os.path.join(version_dir, "metadata.json")
    if not os.path.exists(version_metadata_path):
        return HealthResponse(
            status="no_metadata",
            trained_at=None,
            version=version,
            regression_targets=[],
            classification_targets=[],
            feature_count=0,
            material_count=0,
            shot_count=0,
            vest_count=0,
            vest_layer_count=0,
            data_health=None,
        )
    
    with open(version_metadata_path, "r") as f:
        metadata = json.load(f)
    
    material_properties = fetch_material_properties(db)
    
    # Get database counts
    shot_data_count = db.query(ShotData).count()
    vest_count = db.query(Vest).count()
    material_count = db.query(Material).count()
    vest_layer_count = db.query(VestLayer).count()
    
    return HealthResponse(
        status="trained",
        trained_at=metadata.get("trained_at"),
        version=metadata.get("version"),
        regression_targets=metadata.get("regression_targets", []),
        classification_targets=metadata.get("classification_targets", []),
        feature_count=len(metadata.get("feature_columns", [])),
        material_count=len(material_properties),
        shot_count=shot_data_count,
        vest_count=vest_count,
        vest_layer_count=vest_layer_count,
        data_health=metadata.get("data_health"),
    )


@router.get("/metrics")
def metrics():
    """Get model training metrics."""
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run /train first.",
        )

    return metadata


@router.get("/versions")
def list_versions():
    """List all available model versions."""
    versions = list_model_versions()
    return {"versions": versions}


@router.post("/load-version/{version}")
def load_version(version: str):
    """Load a specific model version as the current model."""
    try:
        metadata = load_model_version(version)
        return {
            "status": "success",
            "message": f"Model version {version} loaded successfully",
            "metadata": metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model version: {str(e)}")


@router.delete("/versions/{version}")
def delete_version(version: str):
    """Delete a specific model version."""
    try:
        result = delete_model_version(version)
        return {
            "status": "success",
            "message": f"Model version {result['model_name']} deleted successfully",
            "result": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete model version '{version}': {str(e)}")


@router.put("/versions/{version}/name")
def update_name(version: str, new_name: str):
    """Update the display name of a model version."""
    try:
        result = update_model_name(version, new_name)
        return {
            "status": "success",
            "message": f"Model name updated from '{result['old_name']}' to '{result['new_name']}'",
            "result": result,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update model name: {str(e)}")
