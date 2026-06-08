"""
Ballistic ML Service - Training and prediction for ballistic vest testing.
Uses database-driven material properties instead of hardcoded values.
"""
import os
import re
import json
import warnings
from typing import Dict, Any, List, Optional
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss
from sklearn.base import BaseEstimator, TransformerMixin
from xgboost import XGBRegressor, XGBClassifier
from fastapi import HTTPException

from app.db.session import get_db
from app.services.ml.data_fetcher import fetch_training_data, fetch_material_properties
from app.db.models import VestLayer, Material

# Suppress sklearn warnings about features with no observed values
warnings.filterwarnings('ignore', message='Skipping features without any observed values')


# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODEL_DIR = os.path.join(PROJECT_ROOT, "storage", "model_artifacts", "ballistic")
os.makedirs(MODEL_DIR, exist_ok=True)

# Versioned model storage
VERSIONS_DIR = os.path.join(MODEL_DIR, "versions")
os.makedirs(VERSIONS_DIR, exist_ok=True)

REGISTRY_PATH = os.path.join(MODEL_DIR, "registry.json")

# Current model metadata (for backward compatibility)
METADATA_PATH = os.path.join(MODEL_DIR, "metadata.json")

# Target variables
REGRESSION_TARGETS = [
    "backface_deformation_mm",
]

CLASSIFICATION_TARGETS = [
    "perforated",
    "pass_fail",
]


# =============================================================================
# Dynamic Material Properties (loaded from database)
# =============================================================================

def get_material_properties(db_session) -> Dict[str, Dict[str, float]]:
    """Get material properties from database."""
    return fetch_material_properties(db_session)


# =============================================================================
# Text normalization
# =============================================================================

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def normalize_composition_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().upper())


def identify_material_name(raw_name: str, material_properties: Dict[str, Dict[str, float]]) -> str:
    """
    Identify material by exact name match (no aliases - names come from DB).
    """
    normalized = normalize_composition_text(raw_name)
    
    # Try exact match first
    for material_name in material_properties.keys():
        if normalize_composition_text(material_name) == normalized:
            return material_name
    
    return "UNKNOWN_MATERIAL"


def parse_vest_composition(composition: Any, material_properties: Dict[str, Dict[str, float]], validate: bool = True) -> List[Dict[str, Any]]:
    """
    Parse vest composition string using dynamic material properties from DB.
    """
    text = normalize_composition_text(composition)
    if not text:
        return []

    segments: List[Dict[str, Any]] = []
    parts = [part.strip() for part in re.split(r"\s*\+\s*", text) if part.strip()]
    unknown_materials = []

    for position, part in enumerate(parts, start=1):
        match = re.match(r"^(?:(\d+(?:\.\d+)?)\s*)?(.*)$", part)
        if match is None:
            continue

        count_text, raw_name = match.groups()
        count = float(count_text) if count_text else 1.0
        material = identify_material_name(raw_name, material_properties)
        
        if material == "UNKNOWN_MATERIAL":
            unknown_materials.append(raw_name.strip())
        
        properties = material_properties.get(material, {})
        thickness_mm = properties.get("thickness_mm", 0.0)
        density_g_cm3 = properties.get("density_g_cm3", 0.0)
        areal_density = properties.get("areal_density_g_m2", 0.0)

        segments.append({
            "position": position,
            "material": material,
            "count": count,
            "thickness_mm": thickness_mm,
            "density_g_cm3": density_g_cm3,
            "areal_density_g_m2": areal_density,
            "segment_thickness_mm": count * thickness_mm,
            "segment_areal_density_kg_m2": count * thickness_mm * density_g_cm3,
        })

    if validate and unknown_materials:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown material(s) found in vest composition: {', '.join(unknown_materials)}. "
                   f"Available materials: {', '.join(material_properties.keys())}"
        )

    return segments


def build_composition_features(composition: Any, material_properties: Dict[str, Dict[str, float]], validate: bool = False) -> Dict[str, Any]:
    """Build composition features using dynamic material properties."""
    segments = parse_vest_composition(composition, material_properties, validate=validate)
    features: Dict[str, Any] = {}

    # Initialize all material features to 0
    for material in material_properties:
        prefix = material.lower().replace(" ", "_").replace("-", "_")
        features[f"composition_count_{prefix}"] = 0.0
        features[f"composition_thickness_mm_{prefix}"] = 0.0
        features[f"composition_areal_density_kg_m2_{prefix}"] = 0.0
        features[f"composition_first_position_{prefix}"] = 0.0
        features[f"composition_last_position_{prefix}"] = 0.0
        features[f"composition_ply_count_{prefix}"] = 0.0
        features[f"composition_material_class_{prefix}"] = "unknown"
        features[f"composition_elongation_longitudinal_percent_{prefix}"] = 0.0
        features[f"composition_elongation_longitudinal_error_percent_{prefix}"] = 0.0
        features[f"composition_elongation_transverse_percent_{prefix}"] = 0.0
        features[f"composition_elongation_transverse_error_percent_{prefix}"] = 0.0

    if not segments:
        features.update({
            "composition_total_segments": 0,
            "composition_unknown_segment_count": 0,
            "composition_unknown_item_count": 0.0,
            "composition_has_unknown_material": 0,
            "composition_total_item_count": 0.0,
            "composition_calculated_thickness_mm": 0.0,
            "composition_calculated_areal_density_kg_m2": 0.0,
            "composition_weighted_density_g_cm3": 0.0,
            "composition_front_half_density_g_cm3": 0.0,
            "composition_back_half_density_g_cm3": 0.0,
            "composition_density_front_minus_back": 0.0,
            "composition_density_gradient": 0.0,
            "composition_material_transition_count": 0,
            "composition_unique_material_count": 0,
            "composition_sequence": "unknown",
            "composition_first_material": "unknown",
            "composition_second_material": "unknown",
            "composition_penultimate_material": "unknown",
            "composition_last_material": "unknown",
            "composition_weighted_tensile_strength_mpa": 0.0,
            "composition_weighted_modulus_gpa": 0.0,
            "composition_weighted_elongation_percent": 0.0,
        })
        return features

    total_segments = len(segments)
    unknown_segment_count = sum(1 for segment in segments if segment["material"] == "UNKNOWN_MATERIAL")
    unknown_item_count = sum(segment["count"] for segment in segments if segment["material"] == "UNKNOWN_MATERIAL")
    total_count = sum(segment["count"] for segment in segments)
    total_thickness = sum(segment["segment_thickness_mm"] for segment in segments)
    total_areal_density = sum(segment["segment_areal_density_kg_m2"] for segment in segments)
    weighted_density = total_areal_density / total_thickness if total_thickness else 0.0

    # Calculate weighted average material properties
    weighted_tensile_strength = 0.0
    weighted_modulus = 0.0
    weighted_elongation = 0.0
    total_weight = 0.0

    for segment in segments:
        material = segment["material"]
        if material in material_properties:
            props = material_properties[material]
            thickness = segment["segment_thickness_mm"]
            weight = thickness if total_thickness > 0 else 0
            total_weight += weight

            if "tensile_strength_mpa" in props:
                weighted_tensile_strength += props["tensile_strength_mpa"] * weight
            if "modulus_gpa" in props:
                weighted_modulus += props["modulus_gpa"] * weight
            if "force_longitudinal_n_per_cm" in props:
                weighted_elongation += props["force_longitudinal_n_per_cm"] * weight
            elif "force_transverse_n_per_cm" in props:
                weighted_elongation += props["force_transverse_n_per_cm"] * weight

    if total_weight > 0:
        weighted_tensile_strength /= total_weight
        weighted_modulus /= total_weight
        weighted_elongation /= total_weight

    sequence = [segment["material"] for segment in segments]
    transitions = sum(1 for left, right in zip(sequence, sequence[1:]) if left != right)

    front_cutoff = total_thickness / 2.0
    running_thickness = 0.0
    front_areal_density = 0.0
    front_thickness = 0.0
    back_areal_density = 0.0
    back_thickness = 0.0

    for segment in segments:
        material = segment["material"]
        if material in material_properties:
            prefix = material.lower().replace(" ", "_").replace("-", "_")
            features[f"composition_count_{prefix}"] += segment["count"]
            features[f"composition_thickness_mm_{prefix}"] += segment["segment_thickness_mm"]
            features[f"composition_areal_density_kg_m2_{prefix}"] += segment["segment_areal_density_kg_m2"]
            features[f"composition_ply_count_{prefix}"] = material_properties[material].get("ply_count", 0) * segment["count"]
            features[f"composition_material_class_{prefix}"] = material_properties[material].get("material_class", "unknown")
            features[f"composition_elongation_longitudinal_percent_{prefix}"] = material_properties[material].get("elongation_longitudinal_percent", 0.0)
            features[f"composition_elongation_longitudinal_error_percent_{prefix}"] = material_properties[material].get("elongation_longitudinal_error_percent", 0.0)
            features[f"composition_elongation_transverse_percent_{prefix}"] = material_properties[material].get("elongation_transverse_percent", 0.0)
            features[f"composition_elongation_transverse_error_percent_{prefix}"] = material_properties[material].get("elongation_transverse_error_percent", 0.0)

            if segment["position"] == 1:
                features[f"composition_first_position_{prefix}"] = 1.0
            if segment["position"] == total_segments:
                features[f"composition_last_position_{prefix}"] = 1.0

        running_thickness += segment["segment_thickness_mm"]
        if running_thickness <= front_cutoff:
            front_areal_density += segment["segment_areal_density_kg_m2"]
            front_thickness += segment["segment_thickness_mm"]
        else:
            back_areal_density += segment["segment_areal_density_kg_m2"]
            back_thickness += segment["segment_thickness_mm"]

    front_density = front_areal_density / front_thickness if front_thickness else 0.0
    back_density = back_areal_density / back_thickness if back_thickness else 0.0

    features.update({
        "composition_total_segments": total_segments,
        "composition_unknown_segment_count": unknown_segment_count,
        "composition_unknown_item_count": unknown_item_count,
        "composition_has_unknown_material": 1 if unknown_segment_count > 0 else 0,
        "composition_total_item_count": total_count,
        "composition_calculated_thickness_mm": total_thickness,
        "composition_calculated_areal_density_kg_m2": total_areal_density,
        "composition_weighted_density_g_cm3": weighted_density,
        "composition_front_half_density_g_cm3": front_density,
        "composition_back_half_density_g_cm3": back_density,
        "composition_density_front_minus_back": front_density - back_density,
        "composition_density_gradient": (back_density - front_density) / total_thickness if total_thickness else 0.0,
        "composition_material_transition_count": transitions,
        "composition_weighted_tensile_strength_mpa": weighted_tensile_strength,
        "composition_weighted_modulus_gpa": weighted_modulus,
        "composition_weighted_elongation_percent": weighted_elongation,
        "composition_unique_material_count": len(set(sequence)),
        "composition_sequence": ">".join(sequence),
        "composition_first_material": sequence[0],
        "composition_second_material": sequence[1] if len(sequence) > 1 else "none",
        "composition_penultimate_material": sequence[-2] if len(sequence) > 1 else "none",
        "composition_last_material": sequence[-1],
    })

    return features


def add_composition_features(df: pd.DataFrame, material_properties: Dict[str, Dict[str, float]], validate: bool = False) -> pd.DataFrame:
    if "vest_composition" not in df.columns:
        return df

    composition_features = pd.DataFrame(
        [build_composition_features(value, material_properties, validate=validate) for value in df["vest_composition"]],
        index=df.index,
    )

    return pd.concat([df, composition_features], axis=1)


def add_engineered_features(df: pd.DataFrame, material_properties: Dict[str, Dict[str, float]], validate: bool = False) -> pd.DataFrame:
    """Add engineering features using dynamic material properties."""
    df = normalize_column_names(df)
    df = df.copy()
    df = add_composition_features(df, material_properties, validate=validate)

    # Ensure numeric columns are numeric when possible.
    numeric_candidates = [
        "material_thickness_mm",
        "material_weight_g_m2",
        "material_weight_kg_m2",
        "number_of_layers",
        "shot_number",
        "impact_velocity_mps",
        "impact_angle_deg",
        "bullet_mass_g",
        "temperature_c",
        "humidity_pct",
        "panel_width_mm",
        "panel_height_mm",
        "plate_curvature_mm",
        "shot_x_position_mm",
        "shot_y_position_mm",
        "edge_distance_mm",
        "previous_shot_distance_mm",
        "fabric_elongation_pct",
        "fabric_strain_pct",
        "max_tensile_strength_mpa",
        "fiber_thickness_um",
        "epoxy_percentage",
        "fiber_orientation_deg",
    ]

    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Add kinetic energy
    if "bullet_mass_g" in df.columns and "impact_velocity_mps" in df.columns:
        df["kinetic_energy_j"] = 0.5 * (df["bullet_mass_g"] / 1000) * (df["impact_velocity_mps"] ** 2)

    return df


def clean_binary_target(series: pd.Series) -> pd.Series:
    """
    Convert various binary representations to 0/1.
    - 1 = bad outcome / failed / perforated
    - 0 = good outcome / passed / not perforated
    """
    if pd.api.types.is_numeric_dtype(series):
        return series

    mapping = {
        "1": 1,
        "true": 1,
        "yes": 1,
        "y": 1,
        "fail": 1,
        "failed": 1,
        "perforated": 1,
        "penetrated": 1,
        "si": 1,
        "sí": 1,

        "0": 0,
        "false": 0,
        "no": 0,
        "n": 0,
        "pass": 0,
        "passed": 0,
        "not perforated": 0,
        "no perforated": 0,
        "no penetration": 0,
    }

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map(mapping)
    )


# =============================================================================
# Model building
# =============================================================================

def to_string_array(X):
    return X.astype(str)


def build_preprocessing_pipeline(numeric_cols: List[str], categorical_cols: List[str]) -> ColumnTransformer:
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown", keep_empty_features=True)),
        ("to_string", FunctionTransformer(to_string_array, feature_names_out="one-to-one")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_cols),
            ("cat", categorical_pipeline, categorical_cols),
        ],
        remainder="drop",
    )


def build_regressor() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=400,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=5.0,
        reg_alpha=0.5,
        objective="reg:squarederror",
        random_state=42,
    )


def build_classifier() -> XGBClassifier:
    return XGBClassifier(
        n_estimators=400,
        max_depth=3,
        learning_rate=0.03,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=5.0,
        reg_alpha=0.5,
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
    )


def regression_error_summary(y_true, y_pred) -> Dict[str, Optional[float]]:
    residuals = np.asarray(y_pred, dtype=float) - np.asarray(y_true, dtype=float)
    absolute_errors = np.abs(residuals)

    if len(absolute_errors) == 0:
        return {
            "mae": None,
            "rmse": None,
            "median_absolute_error": None,
            "absolute_error_p80": None,
            "absolute_error_p90": None,
            "absolute_error_p95": None,
            "mean_residual": None,
        }

    return {
        "mae": float(np.mean(absolute_errors)),
        "rmse": float(np.sqrt(np.mean(residuals ** 2))),
        "median_absolute_error": float(np.quantile(absolute_errors, 0.50)),
        "absolute_error_p80": float(np.quantile(absolute_errors, 0.80)),
        "absolute_error_p90": float(np.quantile(absolute_errors, 0.90)),
        "absolute_error_p95": float(np.quantile(absolute_errors, 0.95)),
        "mean_residual": float(np.mean(residuals)),
    }


def classification_error_summary(y_true, probabilities) -> Dict[str, Optional[float]]:
    y_array = np.asarray(y_true, dtype=float)
    prob_array = np.asarray(probabilities, dtype=float)
    probability_errors = np.abs(prob_array - y_array)

    if len(probability_errors) == 0:
        return {
            "probability_mae": None,
            "probability_error_p80": None,
            "probability_error_p95": None,
            "brier_score": None,
        }

    return {
        "probability_mae": float(np.mean(probability_errors)),
        "probability_error_p80": float(np.quantile(probability_errors, 0.80)),
        "probability_error_p95": float(np.quantile(probability_errors, 0.95)),
        "brier_score": float(brier_score_loss(y_array, prob_array)),
    }


def fill_missing_features(X: pd.DataFrame) -> pd.DataFrame:
    """
    Handles missing values before scikit-learn pipeline.
    """
    X = X.copy()

    object_cols = X.select_dtypes(include=["object", "category", "bool"]).columns
    numeric_cols = X.select_dtypes(exclude=["object", "category", "bool"]).columns

    for col in object_cols:
     X[col] = X[col].fillna("unknown").astype(str)

    for col in numeric_cols:
        non_null_values = X[col].dropna()
        median_value = non_null_values.median() if not non_null_values.empty else 0
        X[col] = X[col].fillna(median_value)

    return X


# =============================================================================
# Training logic
# =============================================================================

def train_from_dataframe(df: pd.DataFrame, material_properties: Dict[str, Dict[str, float]], model_name: Optional[str] = None, warnings: list = None, data_metadata: dict = None) -> Dict[str, Any]:
    print(f"DEBUG: Initial training data shape: {df.shape}")
    print(f"DEBUG: Columns in initial data: {df.columns.tolist()}")

    df = add_engineered_features(df, material_properties)

    print(f"DEBUG: After feature engineering shape: {df.shape}")

    # Clean classification target labels if needed.
    for target in CLASSIFICATION_TARGETS:
        if target in df.columns and not pd.api.types.is_numeric_dtype(df[target]):
            df[target] = clean_binary_target(df[target])

    available_regression_targets = [t for t in REGRESSION_TARGETS if t in df.columns]
    available_classification_targets = [t for t in CLASSIFICATION_TARGETS if t in df.columns]

    print(f"DEBUG: Available regression targets: {available_regression_targets}")
    print(f"DEBUG: Available classification targets: {available_classification_targets}")

    all_targets = available_regression_targets + available_classification_targets

    if not all_targets:
        raise ValueError(
            "Database must contain at least one target column. "
            f"Expected one of: {REGRESSION_TARGETS + CLASSIFICATION_TARGETS}"
        )

    # Drop rows that do not have any target value at all.
    print(f"DEBUG: Before dropping NaN targets, shape: {df.shape}")
    for target in all_targets:
        non_null_count = df[target].notna().sum()
        print(f"DEBUG: {target}: {non_null_count} non-null values")
    df = df.dropna(subset=all_targets, how="all").copy()
    print(f"DEBUG: After dropping NaN targets, shape: {df.shape}")

    # Do not train on ID/source columns. They can accidentally cause memorization.
    columns_to_exclude_from_features = set(all_targets + [
        "source_file",
        "source_sheet",
        "raw_source_file",
        "raw_row_number",
        "id",
        "vest_id",
        "shot_id",
        "test_session_id",
    ])

    feature_columns = [c for c in df.columns if c not in columns_to_exclude_from_features]

    X = df[feature_columns].copy()
    y_regression = df[available_regression_targets] if available_regression_targets else None
    y_classification = df[available_classification_targets] if available_classification_targets else None

    # Identify categorical vs numeric columns
    categorical_feature_names = {
        "vest_composition",
        "ammunition_used",
        "threat_level",
        "condition",
        "panel_side",
        "weave_type",
        "material_type",
        # Composition string features
        "composition_sequence",
        "composition_first_material",
        "composition_second_material",
        "composition_penultimate_material",
        "composition_last_material",
    }

    # Add material class features to categorical
    for material in material_properties:
        prefix = material.lower().replace(" ", "_").replace("-", "_")
        categorical_feature_names.add(f"composition_material_class_{prefix}")

    numeric_cols = [c for c in feature_columns if c not in categorical_feature_names]
    categorical_cols = [c for c in feature_columns if c in categorical_feature_names]

    # Build preprocessing pipeline
    preprocessor = build_preprocessing_pipeline(numeric_cols, categorical_cols)

    # Fit preprocessor on all available data
    X_all_for_preprocessor = X.copy()
    preprocessor.fit(X_all_for_preprocessor)

    # Train regression models
    regression_models = {}
    regression_metrics = {}

    if y_regression is not None:
        for target in available_regression_targets:
            y = y_regression[target]
            valid_idx = y.notna()
            X_valid = X[valid_idx]
            y_valid = y[valid_idx]

            print(f"DEBUG: Training regression model for {target}")
            print(f"DEBUG: Valid records for {target}: {len(X_valid)}")
            print(f"DEBUG: X shape: {X_valid.shape}, y shape: {y_valid.shape}")

            if len(X_valid) == 0:
                continue

            X_processed = preprocessor.transform(X_valid)
            model = build_regressor()
            model.fit(X_processed, y_valid)

            y_pred = model.predict(X_processed)
            metrics = regression_error_summary(y_valid, y_pred)

            regression_models[target] = model
            regression_metrics[target] = metrics

    # Train classification models
    classification_models = {}
    classification_metrics = {}

    if y_classification is not None:
        for target in available_classification_targets:
            y = y_classification[target]
            valid_idx = y.notna()
            X_valid = X[valid_idx]
            y_valid = y[valid_idx]

            if len(X_valid) == 0:
                continue

            # Check if there are at least 2 classes for classification
            unique_classes = y_valid.unique()
            if len(unique_classes) < 2:
                print(f"DEBUG: Skipping classification target {target} - only {len(unique_classes)} unique class(es)")
                continue

            X_processed = preprocessor.transform(X_valid)
            model = build_classifier()
            model.fit(X_processed, y_valid)

            y_pred_proba = model.predict_proba(X_processed)[:, 1]
            metrics = classification_error_summary(y_valid, y_pred_proba)

            classification_models[target] = model
            classification_metrics[target] = metrics

    # Save models with versioning
    import joblib
    version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    version_dir = os.path.join(VERSIONS_DIR, version)
    os.makedirs(version_dir, exist_ok=True)

    # Save preprocessor
    preprocessor_path = os.path.join(version_dir, "preprocessor.pkl")
    joblib.dump(preprocessor, preprocessor_path)

    for target, model in regression_models.items():
        model_path = os.path.join(version_dir, f"{target}.pkl")
        joblib.dump(model, model_path)

    for target, model in classification_models.items():
        model_path = os.path.join(version_dir, f"{target}.pkl")
        joblib.dump(model, model_path)

    # Use provided model name or default to version
    display_name = model_name if model_name else version

    # Save metadata
    # Calculate training data statistics
    material_stats = {}
    for material_name, props in material_properties.items():
        # Generate the column name for this material
        prefix = material_name.lower().replace(" ", "_").replace("-", "_")
        col_name = f'composition_count_{prefix}'
        
        if col_name in df.columns:
            try:
                # Count test shots where material count > 0 (material is present)
                count = (pd.to_numeric(df[col_name], errors='coerce') > 0).sum()
                if count > 0:
                    material_stats[material_name] = int(count)
            except:
                pass
    
    ammunition_stats = {}
    if 'ammunition_used' in df.columns:
        ammo_counts = df['ammunition_used'].value_counts()
        for ammo, count in ammo_counts.items():
            ammunition_stats[ammo] = int(count)
    
    velocity_stats = {}
    if 'impact_velocity_mps' in df.columns:
        try:
            velocity_col = pd.to_numeric(df['impact_velocity_mps'], errors='coerce')
            velocity_stats = {
                'min': float(velocity_col.min()),
                'max': float(velocity_col.max()),
                'mean': float(velocity_col.mean()),
                'std': float(velocity_col.std()),
            }
        except:
            pass
    
    bfd_stats = {}
    if 'backface_deformation_mm' in df.columns:
        try:
            bfd_col = pd.to_numeric(df['backface_deformation_mm'], errors='coerce')
            bfd_stats = {
                'min': float(bfd_col.min()),
                'max': float(bfd_col.max()),
                'mean': float(bfd_col.mean()),
                'std': float(bfd_col.std()),
            }
        except:
            pass
    
    protection_level_stats = {}
    if 'threat_level' in df.columns:
        level_counts = df['threat_level'].value_counts()
        for level, count in level_counts.items():
            protection_level_stats[level] = int(count)
    
    data_health = {
        'material_distribution': material_stats,
        'ammunition_distribution': ammunition_stats,
        'velocity_stats': velocity_stats,
        'bfd_stats': bfd_stats,
        'protection_level_distribution': protection_level_stats,
        'total_data_points': len(df),
    }
    
    metadata = {
        "trained_at": datetime.utcnow().isoformat(),
        "version": version,
        "model_name": display_name,
        "feature_columns": feature_columns,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "regression_targets": available_regression_targets,
        "classification_targets": available_classification_targets,
        "metrics": {
            **{f"{k}_regression": v for k, v in regression_metrics.items()},
            **{f"{k}_classification": v for k, v in classification_metrics.items()},
        },
        "material_properties": material_properties,
        "warnings": warnings or [],
        "training_data_count": len(df),
        "data_health": data_health,
        "anchor_point_count": data_metadata.get("anchor_point_count", 0) if data_metadata else 0,
        "anchor_point_training_rows": data_metadata.get("anchor_point_training_rows", 0) if data_metadata else 0,
    }

    # Save version metadata
    version_metadata_path = os.path.join(version_dir, "metadata.json")
    with open(version_metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Update registry
    registry = []
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            registry = json.load(f)

    registry.append({
        "version": version,
        "model_name": display_name,
        "trained_at": metadata["trained_at"],
        "metrics": metadata["metrics"],
        "regression_targets": available_regression_targets,
        "classification_targets": available_classification_targets,
    })

    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)

    # Save current metadata (for backward compatibility)
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def train_from_database(db_session, model_name: Optional[str] = None) -> Dict[str, Any]:
    """Train model using data from database."""
    from app.db.models import ShotData, Vest, Material, VestLayer, ModelRun
    from app.db.models.user import User
    
    # Check what data exists in database
    shot_data_count = db_session.query(ShotData).count()
    vest_count = db_session.query(Vest).count()
    material_count = db_session.query(Material).count()
    vest_layer_count = db_session.query(VestLayer).count()
    
    # Provide detailed error message
    errors = []
    if shot_data_count == 0:
        errors.append(f"No shot data found in database (count: {shot_data_count})")
    if vest_count == 0:
        errors.append(f"No vests found in database (count: {vest_count})")
    if material_count == 0:
        errors.append(f"No materials found in database (count: {material_count})")
    if vest_layer_count == 0:
        errors.append(f"No vest layers found in database (count: {vest_layer_count})")
    
    if errors:
        raise ValueError(
            "Database is missing required data for training:\n" + 
            "\n".join(f"  - {e}" for e in errors) +
            "\n\nPlease add the missing data to the database before training."
        )
    
    # Fetch training data
    df, warnings, data_metadata = fetch_training_data(db_session)
    
    if df.empty:
        raise ValueError(
            f"Database has data but training query returned empty results. " +
            f"Shot Data: {shot_data_count}, Vests: {vest_count}, Materials: {material_count}, Vest Layers: {vest_layer_count}. " +
            "Check that test sessions are properly linked to vests and vests have layers with materials."
        )
    
    # Fetch material properties
    material_properties = fetch_material_properties(db_session)
    
    if not material_properties:
        raise ValueError(
            f"Materials exist ({material_count}) but none have properties (density, thickness, areal_density). " +
            "Please add material properties to the database."
        )
    
    # Train
    metadata = train_from_dataframe(df, material_properties, model_name=model_name, warnings=warnings, data_metadata=data_metadata)
    
    # Run model health evaluation automatically after training
    print("Starting health evaluation...")
    health_result = None
    try:
        health_result = evaluate_model_on_test_sessions(db_session, version=metadata["version"])
        overall_avg_error = health_result.get("overall_average_error")
        print("Health evaluation completed successfully")
    except Exception as e:
        print(f"WARNING: Failed to run health evaluation after training: {e}")
        overall_avg_error = None
    
    # Save ModelRun record to database
    try:
        training_started_at = datetime.fromisoformat(metadata["trained_at"].replace('Z', '+00:00'))
        
        # Use health evaluation error if available, otherwise use training MAE
        bfd_mae = overall_avg_error
        if bfd_mae is None:
            if "backface_deformation_mm_regression" in metadata["metrics"]:
                bfd_metrics = metadata["metrics"]["backface_deformation_mm_regression"]
                bfd_mae = bfd_metrics.get("mae")
        
        # Use training data count from metadata (training points, not test points)
        training_row_count = metadata.get("training_data_count")
        if training_row_count is None:
            print("WARNING: Model metadata is missing training_data_count, using len(df)")
            training_row_count = len(df)
        
        # Create or update ModelRun record
        model_run = db_session.query(ModelRun).filter(
            ModelRun.version == metadata["version"]
        ).first()
        
        if model_run:
            # Update existing record
            model_run.training_completed_at = training_started_at
            model_run.training_row_count = training_row_count
            model_run.training_avg_error = bfd_mae
            model_run.metrics_json = metadata["metrics"]
        else:
            # Create new record
            model_run = ModelRun(
                model_name=metadata["model_name"],
                model_type="ballistic",
                version=metadata["version"],
                training_started_at=training_started_at,
                training_completed_at=training_started_at,
                training_row_count=training_row_count,
                training_avg_error=bfd_mae,
                metrics_json=metadata["metrics"],
                artifact_path=f"ballistic/versions/{metadata['version']}",
                created_at=datetime.now(),
            )
            db_session.add(model_run)
        
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        print(f"WARNING: Failed to save ModelRun record: {e}")
        # Don't fail the training if ModelRun save fails
    
    return metadata


def list_model_versions() -> List[Dict[str, Any]]:
    """List all available model versions."""
    if not os.path.exists(REGISTRY_PATH):
        return []
    
    with open(REGISTRY_PATH, "r") as f:
        registry = json.load(f)
    
    # Sort by version (newest first)
    return sorted(registry, key=lambda x: x["version"], reverse=True)


def load_model_version(version: str) -> Dict[str, Any]:
    """Load a specific model version and set it as current."""
    version_dir = os.path.join(VERSIONS_DIR, version)
    
    if not os.path.exists(version_dir):
        raise ValueError(f"Model version {version} not found")
    
    # Load version metadata
    version_metadata_path = os.path.join(version_dir, "metadata.json")
    with open(version_metadata_path, "r") as f:
        metadata = json.load(f)
    
    # Copy models to current location
    import joblib
    import shutil
    for target in metadata.get("regression_targets", []) + metadata.get("classification_targets", []):
        model_path = os.path.join(version_dir, f"{target}.pkl")
        current_path = os.path.join(MODEL_DIR, f"{target}.pkl")
        if os.path.exists(model_path):
            joblib.load(model_path)  # Verify it loads
            shutil.copy(model_path, current_path)
    
    # Copy preprocessor
    preprocessor_path = os.path.join(version_dir, "preprocessor.pkl")
    current_preprocessor_path = os.path.join(MODEL_DIR, "preprocessor.pkl")
    if os.path.exists(preprocessor_path):
        joblib.load(preprocessor_path)  # Verify it loads
        shutil.copy(preprocessor_path, current_preprocessor_path)
    
    # Update current metadata
    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)
    
    return metadata


def predict_with_version(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]], version: Optional[str] = None) -> Dict[str, Any]:
    """Make a prediction using a specific model version."""
    if version:
        # Load the specific version temporarily
        metadata = load_model_version(version)

    return predict(data, material_properties)


def predict_with_version_multi_shot(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]], version: Optional[str] = None) -> Dict[str, Any]:
    """Make a multi-shot prediction using a specific model version."""
    if version:
        # Load the specific version temporarily
        metadata = load_model_version(version)

    return predict_multi_shot(data, material_properties)


def delete_model_version(version: str) -> Dict[str, Any]:
    """Delete a specific model version."""
    version_dir = os.path.join(VERSIONS_DIR, version)
    
    if not os.path.exists(version_dir):
        raise ValueError(f"Model version {version} not found")
    
    # Load registry to get model name
    registry = []
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            registry = json.load(f)
    
    # Find the version in registry to get model name
    version_info = next((v for v in registry if v["version"] == version), None)
    model_name = version_info.get("model_name", version) if version_info else version
    
    # Remove from registry
    registry = [v for v in registry if v["version"] != version]
    
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    
    # Delete version directory
    import shutil
    shutil.rmtree(version_dir)
    
    return {
        "version": version,
        "model_name": model_name,
        "deleted": True
    }


def update_model_name(version: str, new_name: str) -> Dict[str, Any]:
    """Update the display name of a model version."""
    version_dir = os.path.join(VERSIONS_DIR, version)
    
    if not os.path.exists(version_dir):
        raise ValueError(f"Model version {version} not found")
    
    # Update registry
    registry = []
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, "r") as f:
            registry = json.load(f)
    
    # Find and update the version in registry
    version_info = next((v for v in registry if v["version"] == version), None)
    if not version_info:
        raise ValueError(f"Model version {version} not found in registry")
    
    old_name = version_info["model_name"]
    version_info["model_name"] = new_name
    
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    
    # Update version metadata
    version_metadata_path = os.path.join(version_dir, "metadata.json")
    with open(version_metadata_path, "r") as f:
        metadata = json.load(f)
    
    metadata["model_name"] = new_name
    
    with open(version_metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    # Update current metadata if this is the current model
    current_metadata = load_metadata()
    if current_metadata and current_metadata.get("version") == version:
        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
    
    return {
        "version": version,
        "old_name": old_name,
        "new_name": new_name,
        "updated": True
    }


# =============================================================================
# Prediction logic
# =============================================================================

def load_model(target: str):
    model_path = os.path.join(MODEL_DIR, f"{target}.pkl")
    if not os.path.exists(model_path):
        return None
    import joblib
    return joblib.load(model_path)


def load_preprocessor():
    preprocessor_path = os.path.join(MODEL_DIR, "preprocessor.pkl")
    if not os.path.exists(preprocessor_path):
        print(f"WARNING: Preprocessor not found at {preprocessor_path}")
        return None
    import joblib
    try:
        return joblib.load(preprocessor_path)
    except Exception as e:
        print(f"ERROR: Failed to load preprocessor: {e}")
        return None


def load_metadata() -> Dict[str, Any]:
    if not os.path.exists(METADATA_PATH):
        return {}

    with open(METADATA_PATH, "r") as f:
        return json.load(f)


def prepare_single_input(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]], validate: bool = True) -> pd.DataFrame:
    df = pd.DataFrame([data])
    df = add_engineered_features(df, material_properties, validate=validate)

    metadata = load_metadata()
    feature_columns = metadata.get("feature_columns", [])

    categorical_feature_names = {
        "vest_composition",
        "ammunition_used",
        "threat_level",
        "condition",
        "panel_side",
        "weave_type",
        "material_type",
    }

    # Add material class features to categorical
    for material in material_properties:
        prefix = material.lower().replace(" ", "_").replace("-", "_")
        categorical_feature_names.add(f"composition_material_class_{prefix}")

    if feature_columns:
        for col in feature_columns:
            if col not in df.columns:
                if col in categorical_feature_names:
                    df[col] = "unknown"
                else:
                    df[col] = np.nan

        df = df[feature_columns]

    for col in df.columns:
        if col in categorical_feature_names:
            df[col] = df[col].fillna("unknown").astype(str)

    df = fill_missing_features(df)
    return df


def conservative_upper_prediction(
    value: Optional[float],
    mae: Optional[float],
    multiplier: float = 1.64,
) -> Optional[float]:
    """
    Conservative-ish upper estimate using model MAE.
    1.64 is roughly a one-sided 95% normal multiplier,
    but this is only a rough screening heuristic.
    """
    if value is None or mae is None:
        return None
    return value + multiplier * mae


def generate_velocity_curves(
    data: Dict[str, Any],
    material_properties: Dict[str, Dict[str, float]],
    validate: bool = False,
    num_points: int = 20,
    num_shots: int = 6,
) -> Dict[int, List[Dict[str, float]]]:
    """
    Generate BFD vs velocity curve predictions for each shot.
    Returns a dict mapping shot_number to list of (velocity, predicted_bfd) points.
    """
    metadata = load_metadata()
    if not metadata:
        return {}

    base_velocity = data.get("impact_velocity_mps", 434.6)
    velocity_range = np.linspace(base_velocity * 0.8, base_velocity * 1.2, num_points)

    curves = {}
    preprocessor = load_preprocessor()
    if preprocessor is None:
        return {}

    bfd_model = load_model("backface_deformation_mm")
    if bfd_model is None:
        return {}

    for shot_num in range(1, num_shots + 1):
        curve_points = []
        for velocity in velocity_range:
            curve_data = data.copy()
            curve_data["impact_velocity_mps"] = velocity
            curve_data["shot_number"] = shot_num

            X = prepare_single_input(curve_data, material_properties, validate=True)
            X_processed = preprocessor.transform(X)
            bfd_prediction = float(bfd_model.predict(X_processed)[0])

            curve_points.append({
                "velocity_mps": velocity,
                "predicted_bfd_mm": bfd_prediction,
            })
        curves[shot_num] = curve_points

    return curves


def predict_multi_shot(
    data: Dict[str, Any],
    material_properties: Dict[str, Dict[str, float]],
    validate: bool = False,
    num_shots: int = 6,
) -> Dict[str, Any]:
    """
    Predict backface deformation for multiple shots (default 6).
    Returns predictions for each shot as a table.
    """
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run training first.",
        )

    # Generate predictions for each shot
    shot_predictions = []
    for shot_num in range(1, num_shots + 1):
        shot_data = data.copy()
        shot_data["shot_number"] = shot_num

        X = prepare_single_input(shot_data, material_properties, validate=True)

        # Load and apply preprocessor
        preprocessor = load_preprocessor()
        if preprocessor is None:
            raise HTTPException(
                status_code=500,
                detail="Preprocessor not found. The model may have been trained with an older version. Please retrain the model.",
            )

        X_processed = preprocessor.transform(X)

        metrics = metadata.get("metrics", {})

        bfd_prediction = None
        perforation_probability = None

        bfd_model = load_model("backface_deformation_mm")
        if bfd_model is not None:
            bfd_prediction = float(bfd_model.predict(X_processed)[0])

        perforation_model = load_model("perforated")
        if perforation_model is not None:
            perforation_probability = float(perforation_model.predict_proba(X_processed)[0, 1])

        bfd_metric = metrics.get("backface_deformation_mm_regression", {})
        bfd_mae = bfd_metric.get("mae") if isinstance(bfd_metric, dict) else None
        bfd_p95 = bfd_metric.get("absolute_error_p95", bfd_mae) if isinstance(bfd_metric, dict) else bfd_mae

        bfd_lower_95 = float(bfd_prediction - bfd_p95) if bfd_prediction is not None and bfd_p95 is not None else None
        bfd_upper_95 = float(bfd_prediction + bfd_p95) if bfd_prediction is not None and bfd_p95 is not None else None

        shot_predictions.append({
            "shot_number": shot_num,
            "predicted_backface_deformation_mm": bfd_prediction,
            "lower_95_ci_mm": bfd_lower_95,
            "upper_95_ci_mm": bfd_upper_95,
            "perforation_probability": perforation_probability,
        })

    # Calculate BFD vs velocity curves for all shots
    velocity_curves = generate_velocity_curves(data, material_properties, validate)

    return {
        "shot_predictions": shot_predictions,
        "velocity_curves": velocity_curves,
        "training_data_count": metadata.get("training_data_count", "unknown"),
    }


def predict(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run training first.",
        )

    X = prepare_single_input(data, material_properties, validate=True)

    # Log weighted average material properties for debugging
    if "composition_weighted_tensile_strength_mpa" in X.columns:
        print(f"DEBUG: Weighted Tensile Strength: {X['composition_weighted_tensile_strength_mpa'].iloc[0]:.2f} MPa")
    if "composition_weighted_modulus_gpa" in X.columns:
        print(f"DEBUG: Weighted Modulus: {X['composition_weighted_modulus_gpa'].iloc[0]:.2f} GPa")
    if "composition_weighted_elongation_percent" in X.columns:
        print(f"DEBUG: Weighted Elongation: {X['composition_weighted_elongation_percent'].iloc[0]:.2f}%")
    if "composition_weighted_density_g_cm3" in X.columns:
        print(f"DEBUG: Weighted Density: {X['composition_weighted_density_g_cm3'].iloc[0]:.2f} g/cm³")

    # Load and apply preprocessor
    preprocessor = load_preprocessor()
    if preprocessor is None:
        print(f"ERROR: Preprocessor is None, cannot proceed with prediction")
        raise HTTPException(
            status_code=500,
            detail="Preprocessor not found. The model may have been trained with an older version. Please retrain the model.",
        )

    print(f"INFO: Preprocessor loaded successfully, applying transform")
    print(f"INFO: Input columns: {X.columns.tolist()}")
    X_processed = preprocessor.transform(X)
    print(f"INFO: Processed shape: {X_processed.shape}")
    
    metrics = metadata.get("metrics", {})

    bfd_prediction = None
    perforation_probability = None
    fail_probability = None

    bfd_model = load_model("backface_deformation_mm")
    if bfd_model is not None:
        bfd_prediction = float(bfd_model.predict(X_processed)[0])

    perforation_model = load_model("perforated")
    if perforation_model is not None:
        perforation_probability = float(perforation_model.predict_proba(X_processed)[0, 1])

    fail_model = load_model("pass_fail")
    if fail_model is not None:
        fail_probability = float(fail_model.predict_proba(X_processed)[0, 1])

    bfd_metric = metrics.get("backface_deformation_mm_regression", {})
    bfd_mae = bfd_metric.get("mae") if isinstance(bfd_metric, dict) else None
    bfd_p80 = bfd_metric.get("absolute_error_p80", bfd_mae) if isinstance(bfd_metric, dict) else bfd_mae
    bfd_p95 = bfd_metric.get("absolute_error_p95", bfd_mae) if isinstance(bfd_metric, dict) else bfd_mae

    bfd_lower_80 = float(bfd_prediction - bfd_p80) if bfd_prediction is not None and bfd_p80 is not None else None
    bfd_upper_80 = float(bfd_prediction + bfd_p80) if bfd_prediction is not None and bfd_p80 is not None else None
    bfd_lower_95 = float(bfd_prediction - bfd_p95) if bfd_prediction is not None and bfd_p95 is not None else None
    bfd_upper_95 = float(bfd_prediction + bfd_p95) if bfd_prediction is not None and bfd_p95 is not None else None
    bfd_upper = bfd_upper_95 if bfd_upper_95 is not None else conservative_upper_prediction(bfd_prediction, bfd_mae)

    perforation_metric = metrics.get("perforated_classification", {})
    perforation_error = perforation_metric.get("probability_mae") if isinstance(perforation_metric, dict) else None

    fail_metric = metrics.get("pass_fail_classification", {})
    fail_error = fail_metric.get("probability_mae") if isinstance(fail_metric, dict) else None

    # Generate recommendation
    recommendation = "No recommendation available"
    confidence_note = "Model not trained or insufficient data"

    if bfd_prediction is not None:
        if bfd_upper is not None and bfd_upper > 44:
            recommendation = "FAIL: Predicted backface deformation exceeds NIJ 44mm limit"
        elif bfd_upper is not None and bfd_upper > 40:
            recommendation = "WARNING: High backface deformation predicted"
        else:
            recommendation = "PASS: Predicted backface deformation within acceptable limits"

        training_count = metadata.get("training_data_count", "unknown")
        confidence_note = f"Model trained on {training_count} data points. 95% confidence interval: {bfd_lower_95:.1f} - {bfd_upper_95:.1f} mm"

    if perforation_probability is not None and perforation_probability > 0.5:
        recommendation = "FAIL: High perforation probability predicted"

    return {
        "predicted_backface_deformation_mm": bfd_prediction,
        "estimated_backface_absolute_error_mm": bfd_mae,
        "backface_prediction_lower_80_mm": bfd_lower_80,
        "backface_prediction_upper_80_mm": bfd_upper_80,
        "backface_prediction_lower_95_mm": bfd_lower_95,
        "backface_prediction_upper_95_mm": bfd_upper_95,
        "conservative_backface_deformation_upper_mm": bfd_upper,
        "perforation_probability": perforation_probability,
        "perforation_probability_estimated_error": perforation_error,
        "fail_probability": fail_probability,
        "fail_probability_estimated_error": fail_error,
        "recommendation": recommendation,
        "confidence_note": confidence_note,
    }


def evaluate_model_on_test_sessions(
    db_session,
    version: Optional[str] = None,
    protocol_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Evaluate model performance on test session data.
    
    Args:
        db_session: Database session
        version: Model version to use (uses current if None)
        protocol_filter: Protocol level to filter by (None for all)
    
    Returns:
        Dictionary with vest-level averages and point-level data for graphing
    """
    from app.db.models import ShotData, TestSession, Vest, Protocol, Ammunition
    from app.services.ml.data_fetcher import fetch_material_properties
    
    # Load the specified version if provided
    if version:
        load_model_version(version)
    
    # Load model metadata
    metadata = load_metadata()
    if not metadata:
        raise ValueError("No trained model found. Run training first.")
    
    # Load preprocessor and model
    preprocessor = load_preprocessor()
    if preprocessor is None:
        raise ValueError("Preprocessor not found. Please retrain the model.")
    
    bfd_model = load_model("backface_deformation_mm")
    if bfd_model is None:
        raise ValueError("BFD model not found.")
    
    # Fetch material properties
    material_properties = fetch_material_properties(db_session)
    
    # Build query for shot data with test sessions and vests
    query = (
        db_session.query(ShotData, TestSession, Vest)
        .join(TestSession, ShotData.test_session_id == TestSession.id)
        .outerjoin(Vest, TestSession.vest_id == Vest.id)
    )
    
    # Filter by protocol if specified
    if protocol_filter and protocol_filter != "all":
        query = query.filter(TestSession.protocol == protocol_filter)
    
    # Only include shots with trauma data
    query = query.filter(ShotData.trauma_mm.isnot(None))
    
    results = query.all()
    
    if not results:
        return {
            "vest_averages": [],
            "point_data": [],
            "total_points": 0,
            "message": "No test data found matching criteria"
        }
    
    # Process each shot
    vest_errors = {}  # vest_code -> list of percentage errors
    point_data = []  # list of individual point data for graphing
    
    for shot_data, test_session, vest in results:
        # Build vest composition from vest layers
        composition_parts = []
        total_layers = 0
        if vest:
            vest_layers = db_session.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
            for vl in sorted(vest_layers, key=lambda x: x.layer_index or 0):
                material = db_session.query(Material).filter(Material.id == vl.material_id).first()
                if material:
                    count = vl.layer_count or 1
                    total_layers += count
                    composition_parts.append(f"{count} {material.name}")
        
        vest_composition = " + ".join(composition_parts) if composition_parts else ""
        
        # Get ammunition info
        caliber = shot_data.caliber
        ammunition = db_session.query(Ammunition).filter(Ammunition.caliber == caliber).first()
        
        # Build prediction input
        prediction_input = {
            "vest_composition": vest_composition,
            "number_of_layers": total_layers,
            "ammunition_used": ammunition.name if ammunition else caliber,
            "threat_level": shot_data.protection_level,
            "shot_number": int(float(shot_data.shot_number)) if shot_data.shot_number else 1,
            "impact_velocity_mps": float(shot_data.velocity_m_s) if shot_data.velocity_m_s else None,
            "impact_angle_deg": float(shot_data.angle_degrees) if shot_data.angle_degrees else 0.0,
            "bullet_mass_g": float(ammunition.projectile_mass_grams) if ammunition and ammunition.projectile_mass_grams else None,
            "temperature_c": float(shot_data.temperature_c) if shot_data.temperature_c else 20.0,
            "humidity_pct": float(shot_data.humidity_percent) if shot_data.humidity_percent else 50.0,
            "condition": test_session.conditioning if test_session else "dry",
            "panel_side": shot_data.side,
        }
        
        # Prepare input and predict
        try:
            X = prepare_single_input(prediction_input, material_properties, validate=False)
            X_processed = preprocessor.transform(X)
            predicted_bfd = float(bfd_model.predict(X_processed)[0])
            
            # Get actual BFD
            actual_bfd = float(shot_data.trauma_mm)
            
            # Calculate percentage error
            if actual_bfd != 0:
                percent_error = abs(predicted_bfd - actual_bfd) / actual_bfd * 100
            else:
                percent_error = abs(predicted_bfd - actual_bfd)  # Absolute error if actual is 0
            
            # Get vest identifier
            vest_identifier = vest.vest_code if vest else f"Unknown-{shot_data.test_session_id}"
            
            # Aggregate by vest
            if vest_identifier not in vest_errors:
                vest_errors[vest_identifier] = []
            vest_errors[vest_identifier].append(percent_error)
            
            # Add to point data for graphing
            point_data.append({
                "vest_code": vest_identifier,
                "vest_name": vest.vest_code if vest else "Unknown",
                "protocol": test_session.protocol if test_session else "Unknown",
                "actual_bfd": actual_bfd,
                "predicted_bfd": predicted_bfd,
                "percent_error": percent_error,
                "shot_number": shot_data.shot_number,
                "protection_level": (getattr(shot_data, 'protection_level', None) or 
                                   (test_session.threat_level if test_session else None) or 
                                   (vest.threat_level if vest else None) or 
                                   "Unknown"),
                "caliber": getattr(shot_data, 'caliber', 'Unknown') if getattr(shot_data, 'caliber', None) else "Unknown",
            })
            
            # Debug: print first few records to see what data we're getting
            if len(point_data) <= 3:
                print(f"DEBUG shot_data object: {dir(shot_data)}")
                print(f"DEBUG point_data {len(point_data)}: protection_level={getattr(shot_data, 'protection_level', 'MISSING')}, caliber={getattr(shot_data, 'caliber', 'MISSING')}")
            
        except Exception as e:
            print(f"ERROR: Failed to predict for shot {shot_data.id}: {e}")
            continue
    
    # Calculate vest averages
    vest_averages = []
    for vest_code, errors in vest_errors.items():
        avg_error = sum(errors) / len(errors) if errors else 0
        vest_averages.append({
            "vest_code": vest_code,
            "average_percent_error": round(avg_error, 2),
            "num_points": len(errors),
        })
    
    # Calculate overall average error
    all_errors = []
    for errors in vest_errors.values():
        all_errors.extend(errors)
    overall_average_error = round(sum(all_errors) / len(all_errors), 2) if all_errors else 0
    
    # Sort by average error
    vest_averages.sort(key=lambda x: x["average_percent_error"])
    
    # Evaluate on anchor points
    anchor_point_errors = []
    anchor_point_material_errors = {}  # Track errors by material composition
    try:
        from app.db.models import AnchorPoint, AnchorPointLayer
        from app.services.ml.data_fetcher import fetch_anchor_points_as_training_data
        
        anchor_df, anchor_metadata = fetch_anchor_points_as_training_data(db_session)
        if not anchor_df.empty:
            print(f"DEBUG: Evaluating {len(anchor_df)} anchor points")
            
            for _, row in anchor_df.iterrows():
                vest_composition = row.get('vest_composition', '')
                prediction_input = {
                    "vest_composition": vest_composition,
                    "number_of_layers": row.get('number_of_layers'),
                    "ammunition_used": row.get('ammunition_used'),
                    "threat_level": row.get('threat_level'),
                    "shot_number": row.get('shot_number', 1),
                    "impact_velocity_mps": row.get('impact_velocity_mps'),
                    "impact_angle_deg": row.get('impact_angle_deg', 0.0),
                    "bullet_mass_g": row.get('bullet_mass_g'),
                    "temperature_c": row.get('temperature_c', 20.0),
                    "humidity_pct": row.get('humidity_pct', 50.0),
                    "condition": row.get('condition'),
                    "panel_side": row.get('panel_side'),
                }
                
                try:
                    X = prepare_single_input(prediction_input, material_properties, validate=False)
                    X_processed = preprocessor.transform(X)
                    predicted_bfd = float(bfd_model.predict(X_processed)[0])
                    
                    actual_bfd = row.get('backface_deformation_mm')
                    if actual_bfd is not None:
                        actual_bfd = float(actual_bfd)
                        
                        # Calculate percentage error
                        if actual_bfd != 0:
                            percent_error = abs(predicted_bfd - actual_bfd) / actual_bfd * 100
                        else:
                            percent_error = abs(predicted_bfd - actual_bfd)  # Absolute error if actual is 0
                        
                        anchor_point_errors.append(percent_error)
                        
                        # Track by material composition
                        if vest_composition not in anchor_point_material_errors:
                            anchor_point_material_errors[vest_composition] = []
                        anchor_point_material_errors[vest_composition].append(percent_error)
                except Exception as e:
                    print(f"ERROR: Failed to predict for anchor point: {e}")
                    continue
            
            # Filter out NaN values and calculate average
            valid_errors = [e for e in anchor_point_errors if not (e != e)]  # Filter NaN
            anchor_avg_error = round(sum(valid_errors) / len(valid_errors), 2) if valid_errors else 0
            print(f"DEBUG: Anchor point average error: {anchor_avg_error}%")
            
            # Calculate per-material averages
            anchor_point_material_averages = []
            for composition, errors in anchor_point_material_errors.items():
                valid_material_errors = [e for e in errors if not (e != e)]
                if valid_material_errors:
                    avg_error = round(sum(valid_material_errors) / len(valid_material_errors), 2)
                    anchor_point_material_averages.append({
                        "composition": composition,
                        "average_error": avg_error,
                        "count": len(valid_material_errors)
                    })
            # Sort by average error
            anchor_point_material_averages.sort(key=lambda x: x["average_error"])
        else:
            anchor_avg_error = 0
            anchor_point_material_averages = []
    except Exception as e:
        print(f"ERROR: Failed to evaluate anchor points: {e}")
        anchor_avg_error = 0
        anchor_point_material_averages = []
    
    return {
        "vest_averages": vest_averages,
        "point_data": point_data,
        "total_points": len(point_data),
        "model_version": metadata.get("version"),
        "model_name": metadata.get("model_name"),
        "overall_average_error": overall_average_error,
        "anchor_point_average_error": anchor_avg_error,
        "anchor_point_count": len(anchor_point_errors),
        "anchor_point_material_errors": anchor_point_material_averages,
    }
