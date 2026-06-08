"""
Ballistic ML API endpoints - database-driven training and prediction.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import os
import json
import zipfile
import tempfile
import shutil

from app.db.session import get_db
from app.services.ml.ballistic_ml import train_from_database, predict, load_metadata, fetch_material_properties, list_model_versions, load_model_version, predict_with_version, predict_with_version_multi_shot, delete_model_version, update_model_name, evaluate_model_on_test_sessions, VERSIONS_DIR
from app.db.models.model_run import ModelRun
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User


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
    model_name: Optional[str] = None
    trained_at: Optional[str]
    version: Optional[str]
    regression_targets: list
    classification_targets: list
    feature_count: int
    material_count: int
    shot_count: int
    vest_count: int
    vest_layer_count: int
    anchor_point_count: Optional[int] = None
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
            anchor_point_count=None,
            data_health=None,
        )
    
    return HealthResponse(
        status="trained",
        model_name=metadata.get("model_name"),
        trained_at=metadata.get("trained_at"),
        version=metadata.get("version"),
        regression_targets=metadata.get("regression_targets", []),
        classification_targets=metadata.get("classification_targets", []),
        feature_count=len(metadata.get("feature_columns", [])),
        material_count=len(material_properties),
        shot_count=metadata.get("training_data_count"),
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
        print(f"ERROR: ValueError during training: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"ERROR: Exception during training: {str(e)}")
        import traceback
        traceback.print_exc()
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
            model_name=None,
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
            model_name=None,
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
        model_name=metadata.get("model_name"),
        trained_at=metadata.get("trained_at"),
        version=metadata.get("version"),
        regression_targets=metadata.get("regression_targets", []),
        classification_targets=metadata.get("classification_targets", []),
        feature_count=len(metadata.get("feature_columns", [])),
        material_count=len(material_properties),
        shot_count=metadata.get("training_data_count"),
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


@router.get("/versions-with-metrics")
def list_versions_with_metrics(db: Session = Depends(get_db)):
    """List all available model versions with training metrics from database."""
    # Get versions from file registry
    file_versions = list_model_versions()
    file_version_set = {v["version"] for v in file_versions}
    
    # Get metrics from database
    model_runs = db.query(ModelRun).filter(ModelRun.model_type == "ballistic").all()
    
    # Merge file versions with database metrics
    versions_with_metrics = []
    for version in file_versions:
        version_str = version["version"]
        model_run = db.query(ModelRun).filter(
            ModelRun.version == version_str,
            ModelRun.model_type == "ballistic"
        ).first()
        
        versions_with_metrics.append({
            **version,
            "training_row_count": model_run.training_row_count if model_run else None,
            "training_avg_error": model_run.training_avg_error if model_run else None,
            "has_files": True,
            "created_at": model_run.created_at.isoformat() if model_run else version.get("trained_at"),
        })
    
    # Also include models from database that aren't in file registry
    for model_run in model_runs:
        if model_run.version not in file_version_set:
            versions_with_metrics.append({
                "version": model_run.version,
                "model_name": model_run.model_name or model_run.version,
                "trained_at": model_run.training_completed_at.isoformat() if model_run.training_completed_at else model_run.created_at.isoformat(),
                "training_row_count": model_run.training_row_count,
                "training_avg_error": model_run.training_avg_error,
                "has_files": False,
                "created_at": model_run.created_at.isoformat(),
            })
    
    # Sort by created_at (newest first)
    versions_with_metrics.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {"versions": versions_with_metrics}


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


@router.post("/versions/upload")
def upload_model(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a model version from a zip file.
    """
    # Check if user is admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")
    
    temp_dir = tempfile.mkdtemp()
    temp_zip = os.path.join(temp_dir, file.filename)
    
    try:
        # Save uploaded file
        with open(temp_zip, 'wb') as f:
            content = file.file.read()
            f.write(content)
        
        # Extract zip file
        with zipfile.ZipFile(temp_zip, 'r') as zipf:
            zipf.extractall(temp_dir)

        # Find the version directory
        # Supports two formats:
        # 1. ballistic/versions/{version}/... (download format)
        # 2. {version}/... (simple format)
        extracted_dirs = os.listdir(temp_dir)
        if not extracted_dirs:
            raise HTTPException(status_code=400, detail="Zip file is empty")

        source_version_dir = None
        version = None

        # Try to find ballistic/versions/{version} structure
        for item in extracted_dirs:
            item_path = os.path.join(temp_dir, item)
            if os.path.isdir(item_path):
                # Check if this is the ballistic directory
                versions_path = os.path.join(item_path, 'versions')
                if os.path.exists(versions_path):
                    # Look for version directory inside versions
                    version_subdirs = [d for d in os.listdir(versions_path) if os.path.isdir(os.path.join(versions_path, d))]
                    if version_subdirs:
                        version = version_subdirs[0]
                        source_version_dir = os.path.join(versions_path, version)
                        break

        # If not found, try simple {version} format
        if not source_version_dir:
            version_dirs = [d for d in extracted_dirs if os.path.isdir(os.path.join(temp_dir, d))]
            if version_dirs:
                version = version_dirs[0]
                source_version_dir = os.path.join(temp_dir, version)

        if not source_version_dir:
            raise HTTPException(status_code=400, detail="No version directory found in zip file")
        
        # Check if version already exists
        target_version_dir = os.path.join(VERSIONS_DIR, version)
        if os.path.exists(target_version_dir):
            raise HTTPException(status_code=400, detail=f"Version {version} already exists")
        
        # Copy version directory to the correct location
        shutil.copytree(source_version_dir, target_version_dir)
        
        # Update or create ModelRun record
        metadata_path = os.path.join(target_version_dir, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            trained_at = None
            if "trained_at" in metadata:
                try:
                    trained_at = datetime.fromisoformat(metadata["trained_at"].replace('Z', '+00:00'))
                except:
                    pass
            
            model_run = db.query(ModelRun).filter(
                ModelRun.version == version,
                ModelRun.model_type == "ballistic"
            ).first()
            
            if model_run:
                model_run.training_completed_at = trained_at
                model_run.training_row_count = metadata.get("training_data_count")
                model_run.metrics_json = metadata.get("metrics")
            else:
                model_run = ModelRun(
                    model_name=metadata.get("model_name", version),
                    model_type="ballistic",
                    version=version,
                    training_started_at=trained_at,
                    training_completed_at=trained_at,
                    training_row_count=metadata.get("training_data_count"),
                    metrics_json=metadata.get("metrics"),
                    artifact_path=f"ballistic/versions/{version}",
                    created_at=datetime.now(),
                )
                db.add(model_run)
            
            db.commit()
        
        return {
            "status": "success",
            "message": f"Model version {version} uploaded successfully",
            "version": version
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload model: {str(e)}")
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


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


@router.get("/model-health")
def model_health(
    version: Optional[str] = None,
    protocol: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Evaluate model performance on test session data.
    
    Args:
        version: Model version to use (uses current if None)
        protocol: Protocol level to filter by (None for all)
    
    Returns:
        Vest-level average errors and point-level data for graphing
    """
    try:
        result = evaluate_model_on_test_sessions(db, version=version, protocol_filter=protocol)
        return result
    except ValueError as e:
        print(f"ERROR: ValueError during model health evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"ERROR: Exception during model health evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model health evaluation failed: {str(e)}")


@router.post("/calculate-missing-metrics")
def calculate_missing_metrics(db: Session = Depends(get_db)):
    """
    Force recalculate training metrics for all model versions.
    This will iterate through all model versions in the file registry and
    calculate training_row_count and training_avg_error using model health evaluation.
    """
    from app.services.ml.ballistic_ml import list_model_versions, load_metadata, VERSIONS_DIR
    from datetime import datetime
    import os
    
    try:
        file_versions = list_model_versions()
        updated_count = 0
        processed_versions = []
        
        for version in file_versions:
            version_str = version["version"]
            
            # Load version metadata to get training data count
            version_metadata_path = os.path.join(VERSIONS_DIR, version_str, "metadata.json")
            if not os.path.exists(version_metadata_path):
                continue
            
            with open(version_metadata_path, "r") as f:
                metadata = json.load(f)
            
            # Get training data count from metadata (training points, not test points)
            training_row_count = metadata.get("training_data_count")
            if training_row_count is None:
                print(f"WARNING: Version {version_str} is missing training_data_count in metadata, skipping")
                continue
            
            # Run model health evaluation to get actual test error
            bfd_mae = None
            try:
                health_result = evaluate_model_on_test_sessions(db, version=version_str)
                overall_avg_error = health_result.get("overall_average_error")
                
                # Use health evaluation results for error
                if overall_avg_error is not None:
                    bfd_mae = overall_avg_error
                else:
                    # Fallback to metadata MAE if health evaluation fails
                    if "metrics" in metadata:
                        metrics = metadata["metrics"]
                        if "backface_deformation_mm_regression" in metrics:
                            bfd_metrics = metrics["backface_deformation_mm_regression"]
                            bfd_mae = bfd_metrics.get("mae")
            except Exception as e:
                print(f"WARNING: Failed to run health evaluation for {version_str}: {e}")
                # Fallback to metadata MAE
                bfd_mae = None
                if "metrics" in metadata:
                    metrics = metadata["metrics"]
                    if "backface_deformation_mm_regression" in metrics:
                        bfd_metrics = metrics["backface_deformation_mm_regression"]
                        bfd_mae = bfd_metrics.get("mae")
            
            # Parse trained_at datetime
            trained_at = None
            if "trained_at" in metadata:
                try:
                    trained_at = datetime.fromisoformat(metadata["trained_at"].replace('Z', '+00:00'))
                except:
                    pass
            
            # Create or update ModelRun record (always update, don't skip existing)
            existing_run = db.query(ModelRun).filter(
                ModelRun.version == version_str,
                ModelRun.model_type == "ballistic"
            ).first()
            
            if existing_run:
                # Update existing record
                existing_run.training_row_count = training_row_count
                existing_run.training_avg_error = bfd_mae
                if trained_at:
                    existing_run.training_completed_at = trained_at
            else:
                # Create new record
                model_run = ModelRun(
                    model_name=version.get("model_name", version_str),
                    model_type="ballistic",
                    version=version_str,
                    training_started_at=trained_at,
                    training_completed_at=trained_at,
                    training_row_count=training_row_count,
                    training_avg_error=bfd_mae,
                    metrics_json=metadata.get("metrics"),
                    artifact_path=f"ballistic/versions/{version_str}",
                )
                db.add(model_run)
            
            updated_count += 1
            processed_versions.append({
                "version": version_str,
                "model_name": version.get("model_name", version_str),
                "training_row_count": training_row_count,
                "training_avg_error": bfd_mae
            })
            db.commit()  # Commit each update to avoid losing progress
        
        return {
            "status": "success",
            "message": f"Recalculated metrics for {updated_count} model versions",
            "updated_count": updated_count,
            "processed_versions": processed_versions
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to recalculate metrics: {str(e)}")


@router.post("/recalculate-metrics/{version}")
def recalculate_metrics_for_version(version: str, db: Session = Depends(get_db)):
    """
    Force recalculate training metrics for a specific model version.
    This will run model health evaluation and update the database with the results.
    """
    from app.services.ml.ballistic_ml import list_model_versions, VERSIONS_DIR
    from datetime import datetime
    import os
    
    try:
        # Check if model exists in database
        model_run = db.query(ModelRun).filter(
            ModelRun.version == version,
            ModelRun.model_type == "ballistic"
        ).first()
        
        if not model_run:
            raise HTTPException(status_code=404, detail=f"Version {version} not found in database")
        
        # Try to load version metadata from filesystem
        training_row_count = None
        has_files = False
        
        version_metadata_path = os.path.join(VERSIONS_DIR, version, "metadata.json")
        if os.path.exists(version_metadata_path):
            has_files = True
            with open(version_metadata_path, "r") as f:
                metadata = json.load(f)
            
            # Get training data count from metadata (training points, not test points)
            training_row_count = metadata.get("training_data_count")
            
            # Run model health evaluation to get actual test error
            bfd_mae = None
            try:
                health_result = evaluate_model_on_test_sessions(db, version=version)
                overall_avg_error = health_result.get("overall_average_error")
                
                # Use health evaluation results for error
                if overall_avg_error is not None:
                    bfd_mae = overall_avg_error
                else:
                    # Fallback to metadata MAE if health evaluation fails
                    if "metrics" in metadata:
                        metrics = metadata["metrics"]
                        if "backface_deformation_mm_regression" in metrics:
                            bfd_metrics = metrics["backface_deformation_mm_regression"]
                            bfd_mae = bfd_metrics.get("mae")
            except Exception as e:
                print(f"WARNING: Failed to run health evaluation for {version}: {e}")
                # Fallback to metadata MAE
                bfd_mae = None
                if "metrics" in metadata:
                    metrics = metadata["metrics"]
                    if "backface_deformation_mm_regression" in metrics:
                        bfd_metrics = metrics["backface_deformation_mm_regression"]
                        bfd_mae = bfd_metrics.get("mae")
        else:
            # Files don't exist, use database values
            training_row_count = model_run.training_row_count
            bfd_mae = model_run.training_avg_error
        
        if training_row_count is None:
            raise HTTPException(status_code=400, detail=f"Version {version} has no training data count available")
        
        # Update ModelRun record
        model_run.training_row_count = training_row_count
        model_run.training_avg_error = bfd_mae
        
        db.commit()
        
        return {
            "status": "success",
            "message": f"Recalculated metrics for version {version}",
            "version": version,
            "has_files": has_files,
            "training_row_count": training_row_count,
            "training_avg_error": bfd_mae
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to recalculate metrics: {str(e)}")


@router.get("/versions/{version}/download")
def download_model(version: str, background_tasks: BackgroundTasks):
    """
    Download a model version as a zip file.
    """
    version_dir = os.path.join(VERSIONS_DIR, version)
    if not os.path.exists(version_dir):
        raise HTTPException(status_code=404, detail=f"Version {version} not found")
    
    # Load metadata to get model name
    metadata_path = os.path.join(version_dir, "metadata.json")
    model_name = version  # fallback to version if no metadata
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                model_name = metadata.get("model_name", version)
        except:
            pass
    
    # Create a temporary zip file
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"ballistic_model_{version}.zip")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(version_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, VERSIONS_DIR)
                    zipf.write(file_path, arcname)
        
        # Add background task to clean up temp directory after response is sent
        def cleanup():
            shutil.rmtree(temp_dir, ignore_errors=True)
        background_tasks.add_task(cleanup)
        
        # Sanitize model name for filename
        safe_model_name = model_name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        filename = f"{safe_model_name}_{version}.zip"
        
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=filename
        )
    except Exception as e:
        # Clean up on error
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to create zip file: {str(e)}")
