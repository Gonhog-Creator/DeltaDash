"""
Ballistic ML API endpoints - database-driven training and prediction.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import os
import json
import zipfile
import tempfile
import shutil
import asyncio
import queue

from app.db.session import get_db
from app.services.ml.ballistic_ml import train_from_database, predict, load_metadata, fetch_material_properties, list_model_versions, load_model_version, predict_with_version, predict_with_version_multi_shot, delete_model_version, update_model_name, evaluate_model_on_test_sessions, VERSIONS_DIR
from app.db.models.model_run import ModelRun
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User


router = APIRouter(prefix="/ballistic", tags=["ballistic"])


# =============================================================================
# Global optimization state
# =============================================================================
trial_results = []
stop_optimization_flag = False
optimization_state = {
    "running": False,
    "stop_requested": False,
    "trial_results": [],
    "starting_model": None,  # {"name": ..., "avg_error": ...} or None for from-scratch
    "current_trial": 0,
    "total_trials": 0,
    "phase": None,  # Current phase description for UI feedback
}

# =============================================================================
# Global feature analysis state
# =============================================================================
feature_analysis_state = {
    "running": False,
    "stop_requested": False,
    "current_step": "",
    "current_step_num": 0,
    "total_steps": 0,
    "completed_steps": [],
}


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


class Hyperparameters(BaseModel):
    """XGBoost hyperparameters for model training."""
    n_estimators: int = Field(800, ge=10, le=10000, description="Number of trees")
    max_depth: int = Field(6, ge=1, le=30, description="Maximum tree depth")
    learning_rate: float = Field(0.05, ge=0.0001, le=2.0, description="Learning rate (eta)")
    subsample: float = Field(0.9, ge=0.01, le=1.0, description="Subsample ratio")
    colsample_bytree: float = Field(0.9, ge=0.01, le=1.0, description="Column subsample ratio")
    min_child_weight: int = Field(2, ge=0, le=100, description="Minimum child weight")
    reg_lambda: float = Field(1.0, ge=0.0, le=100.0, description="L2 regularization")
    reg_alpha: float = Field(0.1, ge=0.0, le=100.0, description="L1 regularization")
    gamma: float = Field(0.0, ge=0.0, le=100.0, description="Minimum loss reduction for split")


class FeatureToggles(BaseModel):
    """Toggle switches for feature engineering groups."""
    kinetic_energy: bool = False
    composite_thickness: bool = False
    layer_density: bool = False
    caliber_features: bool = False
    areal_density: bool = False
    vest_composition: bool = False
    vest_type_interactions: bool = True
    is_female_features: bool = True
    shot_sequence: bool = True
    material_density: bool = True
    velocity_interactions: bool = True
    vest_construction: bool = True
    geometry_features: bool = True
    material_mechanical: bool = False
    weave_features: bool = False


class TrainRequest(BaseModel):
    """Request body for model training with advanced parameters."""
    model_name: Optional[str] = None
    use_log_transform: bool = True
    hyperparameters: Optional[Hyperparameters] = None
    feature_toggles: Optional[FeatureToggles] = None
    ignore_anchor_points: Optional[bool] = False

    temperature_c: Optional[float] = Field(22.0, examples=[22.0])
    humidity_pct: Optional[float] = Field(50.0, examples=[50.0])

    condition: Optional[str] = Field(None, examples=["Ambient", "Humid"])
    panel_side: Optional[str] = Field(None, examples=["front", "back"])

    # Optional material properties (if not using vest_composition)
    fabric_elongation_pct: Optional[float] = None
    fabric_strain_pct: Optional[float] = None
    max_tensile_strength_mpa: Optional[float] = None
    fiber_thickness_um: Optional[float] = None
    epoxy_percentage: Optional[float] = None
    fiber_orientation_deg: Optional[float] = None

    # New features
    caliber_diameter_mm: Optional[float] = None
    caliber_length_mm: Optional[float] = None
    vest_type: Optional[str] = None
    ply_orientations: Optional[str] = None


class CustomVestLayer(BaseModel):
    material_id: str
    layer_count: int
    notes: Optional[str] = None


class CustomVest(BaseModel):
    vest_type: str
    is_female: bool
    panel_protects_front: bool
    panel_protects_back: bool
    panel_protects_sides: bool
    total_layers: int
    total_thickness_mm: float
    material_areal_density_g_m2: float
    layers: list[CustomVestLayer]


class ProtocolPredictionInput(BaseModel):
    """Input for prediction using a protocol."""
    vest_id: Optional[str] = Field(None, examples=["uuid-of-vest"])
    custom_vest: Optional[CustomVest] = None
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
    hyperparameters: Optional[dict] = None


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


@router.get("/feature-analysis-status")
def get_feature_analysis_status():
    """Get current feature analysis progress."""
    return feature_analysis_state


@router.post("/stop-feature-analysis")
def stop_feature_analysis():
    """Request to stop the current feature analysis."""
    feature_analysis_state["stop_requested"] = True
    return {"status": "stop_requested"}


@router.post("/analyze-features")
def analyze_features(db: Session = Depends(get_db), request: Optional[TrainRequest] = None):
    """
    Run ablation study to determine which features have the most effect on accuracy.
    Trains model with all features, then trains with each feature group disabled one at a time.
    Returns accuracy impact for each feature group.
    Temporary analysis models are deleted after analysis completes.
    """
    global feature_analysis_state
    from app.services.ml.ballistic_ml import train_from_database
    import shutil

    try:
        # Reset state
        feature_analysis_state.update({
            "running": True,
            "stop_requested": False,
            "current_step": "Training baseline model (all features)",
            "current_step_num": 0,
            "total_steps": 0,
            "completed_steps": [],
        })

        # Base hyperparameters
        hyperparameters = request.hyperparameters.dict() if request and request.hyperparameters else None
        use_log_transform = request.use_log_transform if request else True

        # All feature groups
        all_features = {
            'kinetic_energy': True,
            'composite_thickness': True,
            'layer_density': True,
            'caliber_features': True,
            'areal_density': True,
            'vest_composition': True,
            'vest_type_interactions': True,
            'is_female_features': True,
            'shot_sequence': True,
            'material_density': True,
            'velocity_interactions': True,
            'vest_construction': True,
            'geometry_features': True,
            'material_mechanical': True,
            'weave_features': True,
        }

        feature_analysis_state["total_steps"] = 1 + len(all_features)  # baseline + ablation

        # Track temporary analysis models for cleanup
        analysis_model_versions = []

        # Train baseline with all features
        baseline_metadata, _ = train_from_database(
            db,
            model_name="analysis_baseline",
            use_log_transform=use_log_transform,
            hyperparameters=hyperparameters,
            feature_toggles=all_features,
        )
        if baseline_metadata and baseline_metadata.get('version'):
            analysis_model_versions.append(baseline_metadata['version'])

        # Get baseline accuracy (use MAE as metric)
        baseline_mae = baseline_metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mae', None)
        baseline_r2 = baseline_metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('r2', None)

        results = {
            'baseline': {
                'mae': baseline_mae,
                'r2': baseline_r2,
            },
            'ablation': {},
        }

        feature_analysis_state["completed_steps"].append({
            "step": "baseline",
            "label": "Baseline (all features)",
            "mae": baseline_mae,
        })
        feature_analysis_state["current_step_num"] = 1

        # Test each feature group individually
        feature_groups = list(all_features.keys())
        for idx, feature in enumerate(feature_groups):
            if feature_analysis_state["stop_requested"]:
                feature_analysis_state["current_step"] = "Stopped by user"
                break

            feature_analysis_state["current_step"] = f"Training without '{feature}' ({idx + 1}/{len(feature_groups)})"
            feature_analysis_state["current_step_num"] = idx + 2

            # Create toggles with just this feature disabled
            test_toggles = {**all_features, feature: False}

            test_metadata, _ = train_from_database(
                db,
                model_name=f"analysis_no_{feature}",
                use_log_transform=use_log_transform,
                hyperparameters=hyperparameters,
                feature_toggles=test_toggles,
            )
            if test_metadata and test_metadata.get('version'):
                analysis_model_versions.append(test_metadata['version'])

            test_mae = test_metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mae', None)
            test_r2 = test_metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('r2', None)

            # Calculate impact (positive = worse without this feature)
            mae_impact = (test_mae - baseline_mae) if baseline_mae and test_mae else None
            r2_impact = (baseline_r2 - test_r2) if baseline_r2 and test_r2 else None

            results['ablation'][feature] = {
                'mae': test_mae,
                'r2': test_r2,
                'mae_impact': mae_impact,  # Higher = this feature is more important
                'r2_impact': r2_impact,
            }

            feature_analysis_state["completed_steps"].append({
                "step": feature,
                "label": f"Without {feature}",
                "mae": test_mae,
                "mae_impact": mae_impact,
            })

        # Sort by impact
        sorted_by_impact = sorted(
            results['ablation'].items(),
            key=lambda x: x[1]['mae_impact'] if x[1]['mae_impact'] is not None else 0,
            reverse=True
        )
        results['ranked_by_importance'] = [item[0] for item in sorted_by_impact]

        # Clean up temporary analysis models
        for version in analysis_model_versions:
            try:
                delete_model_version(version, db)
            except Exception as cleanup_error:
                pass

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        feature_analysis_state["running"] = False


@router.get("/optimization-status")
def get_optimization_status():
    """Get current optimization status and trial results."""
    return optimization_state


@router.post("/stop-optimization")
def stop_optimization():
    """Request to stop the current optimization."""
    global stop_optimization_flag
    stop_optimization_flag = True
    optimization_state["stop_requested"] = True
    return {"status": "stop_requested"}


@router.post("/optimize-hyperparameters")
def optimize_hyperparameters(db: Session = Depends(get_db), request: Optional[TrainRequest] = None):
    """
    Optimize hyperparameters using Bayesian optimization (Optuna).
    Runs multiple trials to find the best hyperparameters for the model.
    Returns the best parameters found and their performance.
    """
    # Track temporary optimization models for cleanup
    optimization_model_names = []
    best_trial_metadata = None  # Store metadata from best trial

    global stop_optimization_flag, trial_results
    stop_optimization_flag = False
    trial_results = []
    optimization_state.update({
        "running": True,
        "stop_requested": False,
        "trial_results": [],
        "starting_model": None,
        "current_trial": 0,
        "total_trials": 50,
        "phase": "Initializing...",
    })

    try:
        from app.services.ml.ballistic_ml import train_from_database, fetch_training_data, fetch_material_properties

        # Get base parameters from request
        use_log_transform = request.use_log_transform if request else True
        feature_toggles = request.feature_toggles.dict() if request and request.feature_toggles else None
        ignore_anchor_points = request.ignore_anchor_points if request else False
        n_trials = 50  # Number of optimization trials

        # Find model with lowest avg error from model library as starting point
        # Prefer models with hyperparameters when there's a tie
        best_existing_model = db.query(ModelRun).filter(
            ModelRun.training_avg_error.isnot(None)
        ).order_by(
            ModelRun.training_avg_error.asc(),
            ModelRun.hyperparameters_json.isnot(None).desc()
        ).first()

        # List all models for debugging
        all_models = db.query(ModelRun).filter(ModelRun.model_type == "ballistic").all()

        starting_hyperparams = None
        if best_existing_model:
            # Load its hyperparameters as starting point
            try:
                version_metadata = load_model_version(best_existing_model.version)
                if version_metadata:
                    if version_metadata.get('hyperparameters'):
                        starting_hyperparams = version_metadata['hyperparameters']
                    else:
                        # Try to load from filesystem metadata as fallback
                        from app.services.ml.ballistic_ml import load_metadata
                        fs_metadata = load_metadata()
                        if fs_metadata and fs_metadata.get('hyperparameters'):
                            starting_hyperparams = fs_metadata['hyperparameters']
            except Exception as e:
                import traceback
                traceback.print_exc()

            # Record starting model info for the frontend
            optimization_state["starting_model"] = {
                "name": best_existing_model.model_name or best_existing_model.version,
                "avg_error": best_existing_model.training_avg_error,
            }
        else:
            optimization_state["starting_model"] = None

        # Fetch training data once
        material_properties = fetch_material_properties(db)
        df, _, _ = fetch_training_data(db, verbose=False, ignore_anchor_points=ignore_anchor_points)

        if len(df) < 50:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data for optimization: {len(df)} samples. Need at least 50 samples."
            )

        # Simple hill-climbing optimization if starting hyperparameters available
        if starting_hyperparams:
            current_best_hyperparams = starting_hyperparams.copy()
            current_best_value = float('inf')
            best_trial_metadata = None
            trials_since_improvement = 0

            # --- Phase 1: Fast rough exploration on representative vest ---
            # Pick the vest that is most representative of the full dataset
            phase1_df = df
            representative_vest = None
            if 'vest_composition' in df.columns and len(df) > 100:
                try:
                    # Score each vest by how close its features are to the dataset median/mode
                    vest_groups = df.groupby('vest_composition')
                    vest_scores = {}
                    # Dataset-level reference values
                    dataset_vest_type_mode = df['vest_type'].mode().iloc[0] if 'vest_type' in df.columns else None
                    dataset_threat_mode = df['threat_level'].mode().iloc[0] if 'threat_level' in df.columns else None
                    dataset_velocity_median = df['impact_velocity_mps'].median() if 'impact_velocity_mps' in df.columns else None
                    dataset_layers_median = df['number_of_layers'].median() if 'number_of_layers' in df.columns else None
                    dataset_material_mode = df['material_type'].mode().iloc[0] if 'material_type' in df.columns else None

                    for vest_comp, group in vest_groups:
                        if len(group) < 5:
                            continue
                        score = 0
                        # Vest type match
                        if dataset_vest_type_mode and 'vest_type' in group.columns:
                            vt = group['vest_type'].mode().iloc[0] if not group['vest_type'].isna().all() else None
                            if vt == dataset_vest_type_mode:
                                score += 3
                        # Threat level match
                        if dataset_threat_mode and 'threat_level' in group.columns:
                            tl = group['threat_level'].mode().iloc[0] if not group['threat_level'].isna().all() else None
                            if tl == dataset_threat_mode:
                                score += 2
                        # Velocity closeness
                        if dataset_velocity_median and 'impact_velocity_mps' in group.columns:
                            v = group['impact_velocity_mps'].median()
                            if v and abs(v - dataset_velocity_median) < 50:
                                score += 2
                        # Layer count closeness
                        if dataset_layers_median and 'number_of_layers' in group.columns:
                            layers = group['number_of_layers'].median()
                            if layers and abs(layers - dataset_layers_median) <= 5:
                                score += 2
                        # Material type match
                        if dataset_material_mode and 'material_type' in group.columns:
                            mt = group['material_type'].mode().iloc[0] if not group['material_type'].isna().all() else None
                            if mt == dataset_material_mode:
                                score += 2
                        # Prefer vests with more shots (more training data)
                        score += min(len(group) / 10, 3)
                        vest_scores[vest_comp] = score

                    if vest_scores:
                        representative_vest = max(vest_scores, key=vest_scores.get)
                        phase1_df = df[df['vest_composition'] == representative_vest].copy()
                        optimization_state["phase"] = f"Phase 1: Fast exploration on representative vest ({len(phase1_df)} samples)"
                        optimization_state["total_trials"] = n_trials
                except Exception:
                    phase1_df = df  # Fallback to full dataset

            phase1_trials = min(30, n_trials // 2) if representative_vest else 0
            phase2_trials = n_trials - phase1_trials

            # Phase 1: Evaluate starting point on representative vest
            if phase1_trials > 0:
                try:
                    metadata, health_result = train_from_database(
                        db,
                        model_name=f"optuna_trial_0",
                        use_log_transform=use_log_transform,
                        hyperparameters=current_best_hyperparams,
                        feature_toggles=feature_toggles,
                        ignore_anchor_points=ignore_anchor_points,
                        skip_health_check=True,
                        preloaded_df=phase1_df,
                        preloaded_material_properties=material_properties,
                        skip_filesystem_save=True,
                    )
                    if metadata and metadata.get('version'):
                        optimization_model_names.append(metadata['version'])
                    mae = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mape', float('inf'))
                    current_best_value = mae
                    trial_results.append({"trial": 0, "error": mae})
                    optimization_state["trial_results"] = trial_results
                    optimization_state["current_trial"] = 0
                    best_trial_metadata = metadata
                    best_trial_metadata['health_check_error'] = mae
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    current_best_value = float('inf')

                # Phase 1 hill-climbing loop
                for trial_num in range(1, phase1_trials + 1):
                    if stop_optimization_flag:
                        optimization_state["stop_requested"] = True
                        break
                    optimization_state["current_trial"] = trial_num

                    import random
                    h = current_best_hyperparams
                    # Phase 1 always uses aggressive scale
                    scale = 3.0
                    if trials_since_improvement >= 5:
                        scale *= 2.0
                    if trials_since_improvement >= 10:
                        scale *= 2.0

                    hyperparams = {
                        'n_estimators': max(10, int(h['n_estimators'] * random.uniform(1 - 0.02 * scale, 1 + 0.02 * scale))),
                        'max_depth': max(1, h['max_depth'] + random.choice([-1, 0, 1]) if random.random() < 0.3 * scale else h['max_depth']),
                        'learning_rate': h['learning_rate'] * random.uniform(1 - 0.05 * scale, 1 + 0.05 * scale),
                        'subsample': max(0.1, min(1.0, h['subsample'] + random.uniform(-0.01 * scale, 0.01 * scale))),
                        'colsample_bytree': max(0.1, min(1.0, h['colsample_bytree'] + random.uniform(-0.01 * scale, 0.01 * scale))),
                        'min_child_weight': max(0, h['min_child_weight'] + random.choice([-1, 0, 1]) if random.random() < 0.3 * scale else h['min_child_weight']),
                        'reg_lambda': max(0.0, h['reg_lambda'] + random.uniform(-0.1 * scale, 0.1 * scale)),
                        'reg_alpha': max(0.0, h['reg_alpha'] + random.uniform(-0.1 * scale, 0.1 * scale)),
                        'gamma': max(0.0, h['gamma'] + random.uniform(-0.1 * scale, 0.1 * scale)),
                    }

                    try:
                        metadata, health_result = train_from_database(
                            db,
                            model_name=f"optuna_p1_trial_{trial_num}",
                            use_log_transform=use_log_transform,
                            hyperparameters=hyperparams,
                            feature_toggles=feature_toggles,
                            ignore_anchor_points=ignore_anchor_points,
                            skip_health_check=True,
                            preloaded_df=phase1_df,
                            preloaded_material_properties=material_properties,
                            skip_filesystem_save=True,
                        )
                        if metadata and metadata.get('version'):
                            optimization_model_names.append(metadata['version'])
                        mae = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mape', float('inf'))
                        trial_results.append({"trial": trial_num, "error": mae})
                        optimization_state["trial_results"] = trial_results

                        if mae < current_best_value:
                            improvement_threshold = current_best_value * 0.01
                            is_meaningful = mae < current_best_value - improvement_threshold
                            current_best_value = mae
                            current_best_hyperparams = hyperparams.copy()
                            best_trial_metadata = metadata
                            best_trial_metadata['health_check_error'] = mae
                            if is_meaningful:
                                trials_since_improvement = 0
                            else:
                                trials_since_improvement += 1
                        else:
                            trials_since_improvement += 1
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        trial_results.append({"trial": trial_num, "error": float('inf')})
                        optimization_state["trial_results"] = trial_results

                # --- Transition: re-evaluate best params on full dataset ---
                if not stop_optimization_flag and best_trial_metadata:
                    optimization_state["phase"] = "Phase 2: Fine-tuning on full dataset"
                    try:
                        metadata, health_result = train_from_database(
                            db,
                            model_name=f"optuna_p2_baseline",
                            use_log_transform=use_log_transform,
                            hyperparameters=current_best_hyperparams,
                            feature_toggles=feature_toggles,
                            ignore_anchor_points=ignore_anchor_points,
                            skip_health_check=True,
                            preloaded_df=df,
                            preloaded_material_properties=material_properties,
                            skip_filesystem_save=True,
                        )
                        if metadata and metadata.get('version'):
                            optimization_model_names.append(metadata['version'])
                        mae = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mape', float('inf'))
                        current_best_value = mae
                        best_trial_metadata = metadata
                        best_trial_metadata['health_check_error'] = mae
                        trials_since_improvement = 0
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
            else:
                # No phase 1 (not enough data) — evaluate starting point on full dataset
                try:
                    metadata, health_result = train_from_database(
                        db,
                        model_name=f"optuna_trial_0",
                        use_log_transform=use_log_transform,
                        hyperparameters=current_best_hyperparams,
                        feature_toggles=feature_toggles,
                        ignore_anchor_points=ignore_anchor_points,
                        skip_health_check=True,
                        preloaded_df=df,
                        preloaded_material_properties=material_properties,
                        skip_filesystem_save=True,
                    )
                    if metadata and metadata.get('version'):
                        optimization_model_names.append(metadata['version'])
                    mae = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mape', float('inf'))
                    current_best_value = mae
                    trial_results.append({"trial": 0, "error": mae})
                    optimization_state["trial_results"] = trial_results
                    optimization_state["current_trial"] = 0
                    best_trial_metadata = metadata
                    best_trial_metadata['health_check_error'] = mae
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    current_best_value = float('inf')

            # --- Phase 2: Fine-tuning on full dataset ---
            phase2_start = phase1_trials + 1 if phase1_trials > 0 else 1
            for trial_num in range(phase2_start, phase2_start + phase2_trials):
                if stop_optimization_flag:
                    optimization_state["stop_requested"] = True
                    break
                optimization_state["current_trial"] = trial_num

                import random
                h = current_best_hyperparams

                # Adaptive scale based on current error
                if current_best_value > 20:
                    scale = 3.0
                elif current_best_value > 10:
                    scale = 1.5
                else:
                    scale = 1.0

                if trials_since_improvement >= 5:
                    scale *= 2.0
                if trials_since_improvement >= 10:
                    scale *= 2.0

                hyperparams = {
                    'n_estimators': max(10, int(h['n_estimators'] * random.uniform(1 - 0.02 * scale, 1 + 0.02 * scale))),
                    'max_depth': max(1, h['max_depth'] + random.choice([-1, 0, 1]) if random.random() < 0.3 * scale else h['max_depth']),
                    'learning_rate': h['learning_rate'] * random.uniform(1 - 0.05 * scale, 1 + 0.05 * scale),
                    'subsample': max(0.1, min(1.0, h['subsample'] + random.uniform(-0.01 * scale, 0.01 * scale))),
                    'colsample_bytree': max(0.1, min(1.0, h['colsample_bytree'] + random.uniform(-0.01 * scale, 0.01 * scale))),
                    'min_child_weight': max(0, h['min_child_weight'] + random.choice([-1, 0, 1]) if random.random() < 0.3 * scale else h['min_child_weight']),
                    'reg_lambda': max(0.0, h['reg_lambda'] + random.uniform(-0.1 * scale, 0.1 * scale)),
                    'reg_alpha': max(0.0, h['reg_alpha'] + random.uniform(-0.1 * scale, 0.1 * scale)),
                    'gamma': max(0.0, h['gamma'] + random.uniform(-0.1 * scale, 0.1 * scale)),
                }

                try:
                    # Every 5th trial, run the real health check for accurate test error
                    run_health_check = (trial_num % 5 == 0)
                    metadata, health_result = train_from_database(
                        db,
                        model_name=f"optuna_p2_trial_{trial_num}",
                        use_log_transform=use_log_transform,
                        hyperparameters=hyperparams,
                        feature_toggles=feature_toggles,
                        ignore_anchor_points=ignore_anchor_points,
                        skip_health_check=not run_health_check,
                        preloaded_df=df,
                        preloaded_material_properties=material_properties,
                        skip_filesystem_save=True,
                    )
                    if metadata and metadata.get('version'):
                        optimization_model_names.append(metadata['version'])
                    
                    # Use health check error when available, otherwise training MAPE
                    if run_health_check and health_result and health_result.get('overall_average_error') is not None:
                        mae = health_result['overall_average_error']
                    else:
                        mae = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mape', float('inf'))
                    
                    trial_results.append({"trial": trial_num, "error": mae})
                    optimization_state["trial_results"] = trial_results

                    if mae < current_best_value:
                        improvement_threshold = current_best_value * 0.01
                        is_meaningful = mae < current_best_value - improvement_threshold
                        current_best_value = mae
                        current_best_hyperparams = hyperparams.copy()
                        best_trial_metadata = metadata
                        best_trial_metadata['health_check_error'] = mae
                        if is_meaningful:
                            trials_since_improvement = 0
                        else:
                            trials_since_improvement += 1
                    else:
                        trials_since_improvement += 1
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    trial_results.append({"trial": trial_num, "error": float('inf')})
                    optimization_state["trial_results"] = trial_results
            
            best_params = current_best_hyperparams
            best_value = current_best_value
            best_hyperparameters = best_params
        else:
            # Use Optuna when no starting point
            import optuna
            sampler = optuna.samplers.TPESampler(multivariate=True, n_startup_trials=10)
            study = optuna.create_study(direction='minimize', sampler=sampler)

            def objective(trial):
                """Optuna objective function to minimize."""
                # Check if stop was requested
                global stop_optimization_flag
                if stop_optimization_flag:
                    raise optuna.TrialPruned()


                # Use wide bounds when no starting point
                hyperparams = {
                    'n_estimators': trial.suggest_int('n_estimators', 10, 10000),
                    'max_depth': trial.suggest_int('max_depth', 1, 30),
                    'learning_rate': trial.suggest_float('learning_rate', 0.0001, 2.0, log=True),
                    'subsample': trial.suggest_float('subsample', 0.01, 1.0),
                    'colsample_bytree': trial.suggest_float('colsample_bytree', 0.01, 1.0),
                    'min_child_weight': trial.suggest_int('min_child_weight', 0, 100),
                    'reg_lambda': trial.suggest_float('reg_lambda', 0.0, 100.0),
                    'reg_alpha': trial.suggest_float('reg_alpha', 0.0, 100.0),
                    'gamma': trial.suggest_float('gamma', 0.0, 100.0),
                }

                # Train model with these hyperparameters
                try:
                    # Every 5th trial, run the real health check for accurate test error
                    run_health_check = (trial.number % 5 == 0 and trial.number > 0)
                    metadata, health_result = train_from_database(
                        db,
                        model_name=f"optuna_trial_{trial.number}",
                        use_log_transform=use_log_transform,
                        hyperparameters=hyperparams,
                        feature_toggles=feature_toggles,
                        ignore_anchor_points=ignore_anchor_points,
                        skip_health_check=not run_health_check,
                        preloaded_df=df,
                        preloaded_material_properties=material_properties,
                        skip_filesystem_save=True,
                    )

                    # Track version for cleanup
                    if metadata and metadata.get('version'):
                        optimization_model_names.append(metadata['version'])

                    # Use health check error when available, otherwise training MAPE
                    if run_health_check and health_result and health_result.get('overall_average_error') is not None:
                        objective_value = health_result['overall_average_error']
                    else:
                        mape = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mape')
                        if mape is not None:
                            objective_value = mape
                        else:
                            mae = metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mae', float('inf'))
                            objective_value = mae


                    # Add trial result to global list
                    global trial_results
                    trial_results.append({
                        "trial": trial.number,
                        "error": objective_value
                    })
                    optimization_state["trial_results"] = trial_results
                    optimization_state["current_trial"] = trial.number

                    # Store metadata if this is the best trial so far
                    nonlocal best_trial_metadata
                    if best_trial_metadata is None or objective_value < (best_trial_metadata.get('health_check_error', float('inf')) if best_trial_metadata.get('health_check_error') else best_trial_metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}).get('mae', float('inf'))):
                        best_trial_metadata = metadata
                        best_trial_metadata['health_check_error'] = objective_value

                    return objective_value
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    return float('inf')  # Return worst score on failure

            try:
                study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
            except optuna.TrialPruned:
                pass

            # Get best parameters
            best_params = study.best_params
            best_value = study.best_value

            # Convert to expected format
            best_hyperparameters = {
                'n_estimators': best_params['n_estimators'],
                'max_depth': best_params['max_depth'],
                'learning_rate': best_params['learning_rate'],
                'subsample': best_params['subsample'],
                'colsample_bytree': best_params['colsample_bytree'],
                'min_child_weight': best_params['min_child_weight'],
                'reg_lambda': best_params['reg_lambda'],
                'reg_alpha': best_params['reg_alpha'],
                'gamma': best_params['gamma'],
            }

        # Retrain the best model with full health check for accurate metrics
        # Skip if stopped — just use the best trial's training MAPE
        if best_trial_metadata and best_hyperparameters and not stop_optimization_flag:
            optimization_state["phase"] = "Running final health check on best model..."
            try:
                final_metadata, final_health_result = train_from_database(
                    db,
                    model_name=f"optuna_best_final",
                    use_log_transform=use_log_transform,
                    hyperparameters=best_hyperparameters,
                    feature_toggles=feature_toggles,
                    ignore_anchor_points=ignore_anchor_points,
                    preloaded_df=df,
                    preloaded_material_properties=material_properties,
                )
                if final_metadata and final_metadata.get('version'):
                    optimization_model_names.append(final_metadata['version'])
                # Use the final model's health check result
                if final_health_result and final_health_result.get('overall_average_error') is not None:
                    best_trial_metadata = final_metadata
                    best_trial_metadata['health_check_error'] = final_health_result['overall_average_error']
            except Exception as e:
                import traceback
                traceback.print_exc()

        # Extract additional metrics from best trial
        best_metrics = best_trial_metadata.get('metrics', {}).get('backface_deformation_mm_regression', {}) if best_trial_metadata else {}
        health_check_error = best_trial_metadata.get('health_check_error', None)
        training_mae = best_metrics.get('mae', None)
        r2_score = best_metrics.get('r2', None)
        rmse = best_metrics.get('rmse', None)

        return {
            'status': 'success',
            'best_hyperparameters': best_hyperparameters,
            'best_mae': best_value,
            'health_check_error': health_check_error,
            'training_mae': training_mae,
            'r2_score': r2_score,
            'rmse': rmse,
            'n_trials': n_trials,
            'message': f'Found best parameters with health check error: {health_check_error:.2f}% after {n_trials} trials' if health_check_error else f'Found best parameters with MAE: {best_value:.4f} mm after {n_trials} trials'
        }

    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Optuna not installed. Run: pip install optuna"
        )
    except HTTPException as he:
        # Re-raise HTTPExceptions (like the insufficient data error) with their original detail
        raise he
    except Exception as e:
        error_msg = str(e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Optimization failed: {error_msg}")
    finally:
        optimization_state["phase"] = "Cleaning up trial models..."
        optimization_state["running"] = False
        # Batch delete optimization trial models from the database
        if optimization_model_names:
            try:
                db.query(ModelRun).filter(
                    ModelRun.version.in_(optimization_model_names)
                ).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
            # Clean up filesystem dirs (batch, best-effort)
            import shutil
            for version in optimization_model_names:
                version_dir = os.path.join(VERSIONS_DIR, version)
                if os.path.exists(version_dir):
                    try:
                        shutil.rmtree(version_dir)
                    except Exception:
                        pass
        optimization_state["phase"] = None


@router.post("/train")
def train(db: Session = Depends(get_db), request: Optional[TrainRequest] = None):
    """
    Train ML model using data from database.
    Fetches shots, vests, materials, ammunition, and test sessions from DB.
    Optional model_name parameter to give the model a friendly name.
    Optional use_log_transform parameter to enable/disable log transform for BFD target.
    Optional hyperparameters for custom model training.
    Optional feature_toggles to enable/disable feature groups.
    """
    try:
        # Use defaults if no request body provided
        model_name = request.model_name if request else None
        use_log_transform = request.use_log_transform if request else True
        hyperparameters = request.hyperparameters.dict() if request and request.hyperparameters else None
        feature_toggles = request.feature_toggles.dict() if request and request.feature_toggles else None
        ignore_anchor_points = request.ignore_anchor_points if request else False

        metadata, health_result = train_from_database(
            db,
            model_name=model_name,
            use_log_transform=use_log_transform,
            hyperparameters=hyperparameters,
            feature_toggles=feature_toggles,
            ignore_anchor_points=ignore_anchor_points,
        )
        # Get health check status from ModelRun
        model_run = db.query(ModelRun).filter(ModelRun.version == metadata["version"]).first()
        health_check_status = None
        if model_run:
            health_check_status = {
                "training_avg_error": model_run.training_avg_error,
                "health_check_passed": model_run.training_avg_error is not None
            }
        return {
            "status": "success",
            "message": "Model trained successfully",
            "metadata": metadata,
            "warnings": metadata.get("warnings", []),
            "health_check": health_check_status,
            "health_result": health_result,  # Full health check results for caching
        }
    except ValueError as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
        return predict_with_version_multi_shot(data.model_dump(), material_properties, version, db)
    else:
        from app.services.ml.ballistic_ml import predict_multi_shot
        return predict_multi_shot(data.model_dump(), material_properties, db_session=db)


@router.post("/predict-protocol")
def predict_protocol_endpoint(data: ProtocolPredictionInput, db: Session = Depends(get_db), version: Optional[str] = None):
    """
    Make predictions using a protocol.
    Returns predictions for all shots in the protocol level (front/back, dry/wet for each ammunition).
    Optional version parameter to use a specific model version.
    """
    import sys
    import os
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from ml.prediction_service import PredictionService

    prediction_service = PredictionService(db)

    # Validate that either vest_id or custom_vest is provided
    if not data.vest_id and not data.custom_vest:
        raise HTTPException(status_code=400, detail="Either vest_id or custom_vest must be provided")

    try:
        if data.custom_vest:
            # Handle custom vest prediction
            result = prediction_service.predict_bfd_for_custom_vest(
                data.custom_vest.model_dump(),
                data.protocol_id,
                data.level_index,
                version
            )
        else:
            # Handle prebuilt vest prediction
            result = prediction_service.predict_bfd_for_protocol(data.vest_id, data.protocol_id, data.level_index, version)
        return result
    except ValueError as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.get("/health/version/{version}", response_model=HealthResponse)
def health_version(version: str, db: Session = Depends(get_db)):
    """Check model status for a specific version."""
    from app.db.models import ShotData, Vest, Material, VestLayer
    
    material_properties = fetch_material_properties(db)
    
    # Get database counts
    shot_data_count = db.query(ShotData).count()
    vest_count = db.query(Vest).count()
    material_count = db.query(Material).count()
    vest_layer_count = db.query(VestLayer).count()
    
    # Load metadata from filesystem (metadata_json field doesn't exist in ModelRun)
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
            material_count=len(material_properties),
            shot_count=shot_data_count,
            vest_count=vest_count,
            vest_layer_count=vest_layer_count,
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
            material_count=len(material_properties),
            shot_count=0,
            vest_count=vest_count,
            vest_layer_count=vest_layer_count,
            data_health=None,
        )
    
    with open(version_metadata_path, "r") as f:
        metadata = json.load(f)
    
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
        hyperparameters=metadata.get("hyperparameters"),
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
def list_versions(db: Session = Depends(get_db)):
    """List all available model versions."""
    versions = list_model_versions(db_session=db)
    return {"versions": versions}


@router.get("/versions-with-metrics")
def list_versions_with_metrics(db: Session = Depends(get_db), limit: int = 20):
    """List all available model versions with training metrics from database."""
    # Get recent models from database (source of truth), limited to avoid memory issues
    model_runs = db.query(ModelRun).filter(
        ModelRun.model_type == "ballistic"
    ).order_by(ModelRun.created_at.desc()).limit(limit).all()
    
    # Get file versions as fallback/additional info
    file_versions = list_model_versions()
    file_version_dict = {v["version"]: v for v in file_versions}
    
    # Build versions list from database records
    versions_with_metrics = []
    for model_run in model_runs:
        file_version = file_version_dict.get(model_run.version)
        
        versions_with_metrics.append({
            "version": model_run.version,
            "model_name": model_run.model_name or model_run.version,
            "trained_at": model_run.training_completed_at.isoformat() if model_run.training_completed_at else model_run.created_at.isoformat(),
            "training_row_count": model_run.training_row_count,
            "training_avg_error": model_run.training_avg_error,
            "has_files": model_run.model_file is not None and model_run.preprocessor_file is not None,
            "created_at": model_run.created_at.isoformat(),
        })
    
    # Also include file versions that aren't in database (legacy models)
    file_version_set = {v["version"] for v in file_versions}
    db_version_set = {model_run.version for model_run in model_runs}
    
    for version in file_versions:
        if version["version"] not in db_version_set:
            versions_with_metrics.append({
                **version,
                "training_row_count": None,
                "training_avg_error": None,
                "has_files": True,
                "created_at": version.get("trained_at"),
            })
    
    # Sort by created_at (newest first)
    versions_with_metrics.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {"versions": versions_with_metrics}


@router.post("/load-version/{version}")
def load_version(version: str, db: Session = Depends(get_db)):
    """Load a specific model version as the current model."""
    try:
        metadata = load_model_version(version, db)
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
        
        # Copy version directory to the correct location (for backward compatibility)
        shutil.copytree(source_version_dir, target_version_dir)
        
        # Load model and preprocessor files and save to database
        import joblib
        import io
        
        preprocessor_bytes = None
        model_bytes = None
        
        preprocessor_path = os.path.join(target_version_dir, "preprocessor.pkl")
        if os.path.exists(preprocessor_path):
            with open(preprocessor_path, 'rb') as f:
                preprocessor_bytes = f.read()
        
        model_path = os.path.join(target_version_dir, "backface_deformation_mm.pkl")
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                model_bytes = f.read()
        
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
                model_run.preprocessor_file = preprocessor_bytes
                model_run.model_file = model_bytes
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
                    preprocessor_file=preprocessor_bytes,
                    model_file=model_bytes,
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
def delete_version(version: str, db: Session = Depends(get_db)):
    """Delete a specific model version."""
    try:
        result = delete_model_version(version, db)
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
def update_name(version: str, new_name: str = Query(..., description="New model name"), db: Session = Depends(get_db)):
    """Update the display name of a model version."""
    try:
        result = update_model_name(version, new_name, db_session=db)
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Model health evaluation failed: {str(e)}")


@router.post("/calculate-missing-metrics")
def calculate_missing_metrics(db: Session = Depends(get_db)):
    """
    Force recalculate training metrics for all model versions.
    This will iterate through all model versions in the database and
    calculate training_row_count and training_avg_error using model health evaluation.
    """
    from app.services.ml.ballistic_ml import list_model_versions
    from datetime import datetime
    
    try:
        model_runs = db.query(ModelRun).filter(
            ModelRun.model_type == "ballistic"
        ).order_by(ModelRun.created_at.desc()).all()
        
        updated_count = 0
        processed_versions = []
        
        for model_run in model_runs:
            version_str = model_run.version
            
            # Get training data count from database
            training_row_count = model_run.training_row_count
            if training_row_count is None:
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
                    # Fallback to existing metrics if health evaluation fails
                    if model_run.metrics_json:
                        metrics = model_run.metrics_json
                        if "backface_deformation_mm_regression" in metrics:
                            bfd_metrics = metrics["backface_deformation_mm_regression"]
                            bfd_mae = bfd_metrics.get("mae")
            except Exception as e:
                # Fallback to existing metrics
                bfd_mae = model_run.training_avg_error
                if bfd_mae is None and model_run.metrics_json:
                    metrics = model_run.metrics_json
                    if "backface_deformation_mm_regression" in metrics:
                        bfd_metrics = metrics["backface_deformation_mm_regression"]
                        bfd_mae = bfd_metrics.get("mae")
            
            # Update ModelRun record
            model_run.training_row_count = training_row_count
            model_run.training_avg_error = bfd_mae
            
            updated_count += 1
            processed_versions.append({
                "version": version_str,
                "model_name": model_run.model_name,
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
