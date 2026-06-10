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
    weighted_elongation_percent = 0.0
    weighted_force_longitudinal = 0.0
    weighted_force_transverse = 0.0
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
            if "elongation_longitudinal_percent" in props:
                weighted_elongation_percent += props["elongation_longitudinal_percent"] * weight
            elif "elongation_transverse_percent" in props:
                weighted_elongation_percent += props["elongation_transverse_percent"] * weight
            if "force_longitudinal_n_per_cm" in props:
                weighted_force_longitudinal += props["force_longitudinal_n_per_cm"] * weight
            if "force_transverse_n_per_cm" in props:
                weighted_force_transverse += props["force_transverse_n_per_cm"] * weight

    if total_weight > 0:
        weighted_tensile_strength /= total_weight
        weighted_modulus /= total_weight
        weighted_elongation_percent /= total_weight
        weighted_force_longitudinal /= total_weight
        weighted_force_transverse /= total_weight

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
        "composition_weighted_elongation_percent": weighted_elongation_percent,
        "composition_weighted_force_longitudinal_n_per_cm": weighted_force_longitudinal,
        "composition_weighted_force_transverse_n_per_cm": weighted_force_transverse,
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


def add_engineered_features(
    df: pd.DataFrame,
    material_properties: Dict[str, Dict[str, float]],
    validate: bool = False,
    feature_toggles: Optional[Dict[str, bool]] = None,
) -> pd.DataFrame:
    """Add engineering features using dynamic material properties.
    
    Args:
        df: Input DataFrame
        material_properties: Material property dictionary
        validate: Whether to validate features
        feature_toggles: Dictionary of feature group toggles. If None, all features enabled.
            Keys: 'kinetic_energy', 'composite_thickness', 'layer_density',
                  'caliber_features', 'areal_density', 'vest_composition',
                  'vest_type_interactions', 'is_female_features', 'shot_sequence',
                  'material_density', 'velocity_interactions'
    """
    # Default: all features enabled
    if feature_toggles is None:
        feature_toggles = {
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
        }
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
        "fabric_elongation_pct",
        "fabric_strain_pct",
        "max_tensile_strength_mpa",
        "fiber_thickness_um",
        "epoxy_percentage",
        "fiber_orientation_deg",
        "caliber_diameter_mm",
        "caliber_length_mm",
    ]

    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Add material_thickness_mm and material_weight_g_m2 if they don't exist (for prediction)
    # These are calculated from composition features for prediction compatibility
    if "material_thickness_mm" not in df.columns and "composition_calculated_thickness_mm" in df.columns:
        df["material_thickness_mm"] = df["composition_calculated_thickness_mm"]
    if "material_weight_g_m2" not in df.columns and "composition_calculated_areal_density_kg_m2" in df.columns:
        df["material_weight_g_m2"] = df["composition_calculated_areal_density_kg_m2"] * 1000  # Convert kg/m2 to g/m2

    # Add material_type if it doesn't exist (for prediction)
    # Calculate from composition material classes
    if "material_type" not in df.columns:
        # Extract material classes from composition features
        material_classes = []
        material_class_cols = [col for col in df.columns if col.startswith("composition_material_class_")]
        
        for idx, row in df.iterrows():
            classes = []
            for col in material_class_cols:
                if row.get(col) and row[col] != "unknown":
                    # Extract material name from column name
                    material_name = col.replace("composition_material_class_", "").replace("_", " ")
                    classes.append(material_name.title())
            material_classes.append(", ".join(sorted(set(classes))) if classes else "unknown")
        
        df["material_type"] = material_classes

    # Add kinetic energy
    if feature_toggles.get('kinetic_energy', True):
        if "bullet_mass_g" in df.columns and "impact_velocity_mps" in df.columns:
            df["kinetic_energy_j"] = 0.5 * (df["bullet_mass_g"] / 1000) * (df["impact_velocity_mps"] ** 2)

    # Add vest_type interaction features to help distinguish hard vs soft armor behavior
    if feature_toggles.get('vest_type_interactions', True) and "vest_type" in df.columns:
        # Create binary indicator for hard vs soft armor (default to soft if not specified)
        df["vest_type"] = df["vest_type"].fillna("soft")
        df["is_hard_armor"] = df["vest_type"].str.contains("hard", case=False, na=False).astype(int)
        df["is_soft_armor"] = df["vest_type"].str.contains("soft", case=False, na=False).astype(int)

        # Interaction with kinetic energy (hard armor absorbs energy differently)
        if "kinetic_energy_j" in df.columns:
            df["kinetic_energy_x_hard_armor"] = df["kinetic_energy_j"] * df["is_hard_armor"]
            df["kinetic_energy_x_soft_armor"] = df["kinetic_energy_j"] * df["is_soft_armor"]

        # Interaction with thickness (hard armor is typically thinner but rigid)
        if "material_thickness_mm" in df.columns:
            df["thickness_x_hard_armor"] = df["material_thickness_mm"] * df["is_hard_armor"]
            df["thickness_x_soft_armor"] = df["material_thickness_mm"] * df["is_soft_armor"]

        # Interaction with layer count (hard vests have fewer layers)
        if "number_of_layers" in df.columns:
            df["layers_x_hard_armor"] = df["number_of_layers"] * df["is_hard_armor"]
            df["layers_x_soft_armor"] = df["number_of_layers"] * df["is_soft_armor"]

    # Add is_female interaction features (female vests have different BFD characteristics)
    if feature_toggles.get('is_female_features', True) and "is_female" in df.columns:
        # Fill NaN with False (default to male/unisex)
        df["is_female"] = df["is_female"].fillna(False).astype(int)

        # Interaction with panel side (female vests typically have lower front BFD)
        if "panel_side" in df.columns:
            # Create binary indicator for front panel
            df["is_front_panel"] = df["panel_side"].str.contains("front", case=False, na=False).astype(int)
            df["is_back_panel"] = df["panel_side"].str.contains("back", case=False, na=False).astype(int)

            # Female x Front interaction (female vests have lower front BFD)
            df["female_x_front_panel"] = df["is_female"] * df["is_front_panel"]
            df["female_x_back_panel"] = df["is_female"] * df["is_back_panel"]

        # Interaction with kinetic energy
        if "kinetic_energy_j" in df.columns:
            df["kinetic_energy_x_female"] = df["kinetic_energy_j"] * df["is_female"]

        # Interaction with thickness
        if "material_thickness_mm" in df.columns:
            df["thickness_x_female"] = df["material_thickness_mm"] * df["is_female"]

    # Add shot sequence effect (first shot has different behavior due to material settling)
    if feature_toggles.get('shot_sequence', True) and "shot_number" in df.columns:
        df["is_first_shot"] = (df["shot_number"] == 1).astype(int)
        layers_col = "number_of_layers" if "number_of_layers" in df.columns else "total_layers"
        if layers_col in df.columns:
            df["shot_sequence_ratio"] = df["shot_number"] / df[layers_col].clip(lower=1)

    # Material density (areal density / thickness = effective density)
    # Use material_weight_g_m2 converted to kg_m2
    if feature_toggles.get('material_density', True) and "material_weight_g_m2" in df.columns and "material_thickness_mm" in df.columns:
        areal_density_kg_m2 = df["material_weight_g_m2"] / 1000.0
        df["material_density"] = areal_density_kg_m2 / df["material_thickness_mm"].clip(lower=0.1)

    # Velocity interactions (high velocity amplifies other effects)
    if feature_toggles.get('velocity_interactions', True):
        velocity_col = "impact_velocity_mps" if "impact_velocity_mps" in df.columns else "velocity_ms"
        layers_col = "number_of_layers" if "number_of_layers" in df.columns else "total_layers"
        angle_col = "impact_angle_deg" if "impact_angle_deg" in df.columns else "angle_degrees"

        if velocity_col in df.columns:
            if layers_col in df.columns:
                df["velocity_x_layers"] = df[velocity_col] * df[layers_col]
            if angle_col in df.columns:
                # Normalize angle (90 = perpendicular, lower = oblique)
                df["velocity_x_obliquity"] = df[velocity_col] * (90 - df[angle_col].fillna(90)).clip(lower=0)

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


def build_regressor(
    n_estimators: int = 800,
    max_depth: int = 6,
    learning_rate: float = 0.05,
    subsample: float = 0.9,
    colsample_bytree: float = 0.9,
    min_child_weight: int = 2,
    reg_lambda: float = 1.0,
    reg_alpha: float = 0.1,
    gamma: float = 0,
) -> XGBRegressor:
    return XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        reg_lambda=reg_lambda,
        reg_alpha=reg_alpha,
        gamma=gamma,
        objective="reg:squarederror",
        random_state=42,
        tree_method="hist",
        grow_policy="depthwise",
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

def train_from_dataframe(
    df: pd.DataFrame,
    material_properties: Dict[str, Dict[str, float]],
    model_name: Optional[str] = None,
    warnings: list = None,
    data_metadata: dict = None,
    use_log_transform: bool = True,
    hyperparameters: Optional[Dict[str, Any]] = None,
    feature_toggles: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    # Capture default hyperparameters if none provided
    if hyperparameters is None:
        hyperparameters = {
            'n_estimators': 800,
            'max_depth': 6,
            'learning_rate': 0.05,
            'subsample': 0.9,
            'colsample_bytree': 0.9,
            'min_child_weight': 2,
            'reg_lambda': 1.0,
            'reg_alpha': 0.1,
            'gamma': 0,
        }

    df = add_engineered_features(df, material_properties, feature_toggles=feature_toggles)

    # Clean classification target labels if needed.
    for target in CLASSIFICATION_TARGETS:
        if target in df.columns and not pd.api.types.is_numeric_dtype(df[target]):
            df[target] = clean_binary_target(df[target])

    available_regression_targets = [t for t in REGRESSION_TARGETS if t in df.columns]
    available_classification_targets = [t for t in CLASSIFICATION_TARGETS if t in df.columns]

    all_targets = available_regression_targets + available_classification_targets

    if not all_targets:
        raise ValueError(
            "Database must contain at least one target column. "
            f"Expected one of: {REGRESSION_TARGETS + CLASSIFICATION_TARGETS}"
        )

    # Drop rows that do not have any target value at all.
    df = df.dropna(subset=all_targets, how="all").copy()

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
        "vest_type",
        "ply_orientations",
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


            if len(X_valid) == 0:
                continue

            # Apply log transform to BFD target to handle skewed distribution
            use_log_transform_bfd = use_log_transform and target == "backface_deformation_mm"
            y_train = y_valid.copy()
            if use_log_transform_bfd:
                # Ensure y_train is numpy array of floats, handle edge cases
                y_train = np.asarray(y_train, dtype=np.float64)
                # Clip negative values and apply log1p
                y_train = np.log1p(np.clip(y_train, 0, None))

            X_processed = preprocessor.transform(X_valid)
            
            # Calculate sample weights based on vest_type to balance hard vs soft armor
            sample_weights = None
            if 'vest_type' in X_valid.columns:
                vest_types = X_valid['vest_type'].fillna('soft')
                type_counts = vest_types.value_counts()
                if len(type_counts) > 1:
                    # Inverse frequency weighting: rare types get higher weight
                    weights = 1.0 / type_counts[vest_types].values
                    # Normalize to mean of 1.0
                    sample_weights = weights * (len(weights) / weights.sum())

            # Build model with custom or default hyperparameters
            if hyperparameters:
                model = build_regressor(**hyperparameters)
            else:
                model = build_regressor()
            model.fit(X_processed, y_train, sample_weight=sample_weights)

            # Inverse transform predictions for metrics
            y_pred = model.predict(X_processed)
            if use_log_transform_bfd:
                y_pred = np.expm1(y_pred)

            metrics = regression_error_summary(y_valid, y_pred)

            # Store whether log transform was used
            regression_models[target] = {
                "model": model,
                "use_log_transform": use_log_transform_bfd
            }
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
    import io
    version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    version_dir = os.path.join(VERSIONS_DIR, version)
    os.makedirs(version_dir, exist_ok=True)

    # Save preprocessor to database (as binary data)
    preprocessor_buffer = io.BytesIO()
    joblib.dump(preprocessor, preprocessor_buffer)
    preprocessor_bytes = preprocessor_buffer.getvalue()

    # Save models to database (as binary data)
    model_files = {}
    for target, model in regression_models.items():
        model_buffer = io.BytesIO()
        joblib.dump(model, model_buffer)
        model_files[f"{target}.pkl"] = model_buffer.getvalue()

    for target, model in classification_models.items():
        model_buffer = io.BytesIO()
        joblib.dump(model, model_buffer)
        model_files[f"{target}.pkl"] = model_buffer.getvalue()

    # Also save to filesystem for backward compatibility (optional, can be removed later)
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
        "hyperparameters": hyperparameters,
        "material_properties": material_properties,
        "warnings": warnings or [],
        "training_data_count": len(df),
        "data_health": data_health,
        "anchor_point_count": data_metadata.get("anchor_point_count", 0) if data_metadata else 0,
        "anchor_point_training_rows": data_metadata.get("anchor_point_training_rows", 0) if data_metadata else 0,
    }

    # Save version metadata to filesystem for local development (in addition to database)
    metadata_path = os.path.join(version_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata, preprocessor_bytes, model_files


def train_from_database(
    db_session,
    model_name: Optional[str] = None,
    use_log_transform: bool = True,
    hyperparameters: Optional[Dict[str, Any]] = None,
    feature_toggles: Optional[Dict[str, bool]] = None,
    ignore_anchor_points: bool = False,
) -> Dict[str, Any]:
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
    df, warnings, data_metadata = fetch_training_data(db_session, ignore_anchor_points=ignore_anchor_points)

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
    metadata, preprocessor_bytes, model_files = train_from_dataframe(
        df,
        material_properties,
        model_name=model_name,
        warnings=warnings,
        data_metadata=data_metadata,
        use_log_transform=use_log_transform,
        hyperparameters=hyperparameters,
        feature_toggles=feature_toggles,
    )
    
    # Save ModelRun record to database FIRST (before health evaluation)
    try:
        training_started_at = datetime.fromisoformat(metadata["trained_at"].replace('Z', '+00:00'))
        
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
            model_run.metrics_json = metadata["metrics"]
            model_run.hyperparameters_json = hyperparameters if hyperparameters else None
            model_run.preprocessor_file = preprocessor_bytes
            model_run.model_file = model_files.get("backface_deformation_mm.pkl") if model_files else None
        else:
            # Create new record
            model_run = ModelRun(
                model_name=metadata["model_name"],
                model_type="ballistic",
                version=metadata["version"],
                training_started_at=training_started_at,
                training_completed_at=training_started_at,
                training_row_count=training_row_count,
                metrics_json=metadata["metrics"],
                hyperparameters_json=hyperparameters if hyperparameters else None,
                artifact_path=f"ballistic/versions/{metadata['version']}",
                created_at=datetime.now(),
                preprocessor_file=preprocessor_bytes,
                model_file=model_files.get("backface_deformation_mm.pkl") if model_files else None,
            )
            db_session.add(model_run)
        
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        print(f"WARNING: Failed to save ModelRun record: {e}")
        # Don't fail the training if ModelRun save fails
    
    # Run model health evaluation automatically after training (now that model is in database)
    print("Starting health evaluation...")
    health_result = None
    try:
        health_result = evaluate_model_on_test_sessions(db_session, version=metadata["version"])
        overall_avg_error = health_result.get("overall_average_error")
        print("Health evaluation completed successfully")
    except Exception as e:
        print(f"WARNING: Failed to run health evaluation after training: {e}")
        overall_avg_error = None
    
    # Update ModelRun with health evaluation results
    if health_result and overall_avg_error is not None:
        try:
            model_run = db_session.query(ModelRun).filter(
                ModelRun.version == metadata["version"]
            ).first()
            if model_run:
                model_run.training_avg_error = overall_avg_error
                db_session.commit()
        except Exception as e:
            db_session.rollback()
            print(f"WARNING: Failed to update ModelRun with health evaluation results: {e}")
    
    return metadata, health_result


def list_model_versions(db_session=None) -> List[Dict[str, Any]]:
    """List all available model versions from database."""
    if db_session is None:
        # Fallback to filesystem if no database session provided
        if not os.path.exists(REGISTRY_PATH):
            return []
        with open(REGISTRY_PATH, "r") as f:
            registry = json.load(f)
        return sorted(registry, key=lambda x: x["version"], reverse=True)
    
    from app.db.models.model_run import ModelRun
    model_runs = db_session.query(ModelRun).filter(
        ModelRun.model_type == "ballistic"
    ).order_by(ModelRun.created_at.desc()).all()
    
    versions = []
    for model_run in model_runs:
        versions.append({
            "version": model_run.version,
            "model_name": model_run.model_name,
            "trained_at": model_run.training_completed_at.isoformat() if model_run.training_completed_at else model_run.created_at.isoformat(),
            "has_files": model_run.model_file is not None and model_run.preprocessor_file is not None,
        })
    
    return versions


def load_model_version(version: str, db_session=None) -> Dict[str, Any]:
    """Load a specific model version and set it as current."""
    if db_session:
        from app.db.models.model_run import ModelRun
        model_run = db_session.query(ModelRun).filter(
            ModelRun.version == version,
            ModelRun.model_type == "ballistic"
        ).first()
        
        if not model_run:
            raise ValueError(f"Model version {version} not found in database")
        
        # Load model and preprocessor from database to filesystem (for backward compatibility)
        import joblib
        import io
        
        if model_run.preprocessor_file:
            preprocessor = joblib.load(io.BytesIO(model_run.preprocessor_file))
            preprocessor_path = os.path.join(MODEL_DIR, "preprocessor.pkl")
            joblib.dump(preprocessor, preprocessor_path)
        
        if model_run.model_file:
            model = joblib.load(io.BytesIO(model_run.model_file))
            model_path = os.path.join(MODEL_DIR, "backface_deformation_mm.pkl")
            joblib.dump(model, model_path)
        
        # Return metadata from database
        metadata = {
            "version": model_run.version,
            "model_name": model_run.model_name,
            "trained_at": model_run.training_completed_at.isoformat() if model_run.training_completed_at else model_run.created_at.isoformat(),
            "metrics": model_run.metrics_json,
            "hyperparameters": model_run.hyperparameters_json,
            "regression_targets": ["backface_deformation_mm"],
            "classification_targets": [],
            "training_data_count": model_run.training_row_count,
        }
        
        # Update current metadata
        with open(METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return metadata
    
    # Fallback to filesystem
    version_dir = os.path.join(VERSIONS_DIR, version)
    
    if not os.path.exists(version_dir):
        # Check old location for backward compatibility (backend/ml/models/)
        old_models_dir = os.path.join(PROJECT_ROOT, "backend", "ml", "models")
        old_model_path = os.path.join(old_models_dir, f"bfd_predictor_{version}.pkl")
        
        if os.path.exists(old_model_path):
            # Load from old location and migrate to new structure
            import joblib
            os.makedirs(version_dir, exist_ok=True)
            
            # Load old bundled model
            model_data = joblib.load(old_model_path)
            
            # Extract and save in new structure
            joblib.dump(model_data['model'], os.path.join(version_dir, 'backface_deformation_mm.pkl'))
            joblib.dump(model_data['scaler'], os.path.join(version_dir, 'preprocessor.pkl'))
            
            # Create metadata
            metadata = {
                'version': version,
                'feature_columns': model_data.get('feature_columns', []),
                'feature_importance': model_data.get('feature_importance', {}),
                'metrics': model_data.get('metrics', {}),
                'training_date': model_data.get('training_date', version),
                'model_type': 'XGBoostRegressor',
                'model_name': 'bfd_predictor'
            }
            
            with open(os.path.join(version_dir, 'metadata.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Also save as current model
            joblib.dump(model_data['model'], os.path.join(MODEL_DIR, 'backface_deformation_mm.pkl'))
            joblib.dump(model_data['scaler'], os.path.join(MODEL_DIR, 'preprocessor.pkl'))
            with open(METADATA_PATH, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return metadata
        else:
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


def predict_with_version(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]], version: Optional[str] = None, db_session=None) -> Dict[str, Any]:
    """Make a prediction using a specific model version."""
    if version:
        # Load the specific version temporarily
        metadata = load_model_version(version)

    return predict(data, material_properties, db_session)


def predict_with_version_multi_shot(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]], version: Optional[str] = None, db_session=None) -> Dict[str, Any]:
    """Make a multi-shot prediction using a specific model version."""
    if version:
        # Load the specific version temporarily
        metadata = load_model_version(version)

    return predict_multi_shot(data, material_properties, db_session=db_session)


def delete_model_version(version: str, db_session=None) -> Dict[str, Any]:
    """Delete a specific model version."""
    if db_session:
        from app.db.models.model_run import ModelRun
        model_run = db_session.query(ModelRun).filter(
            ModelRun.version == version,
            ModelRun.model_type == "ballistic"
        ).first()
        
        if not model_run:
            raise ValueError(f"Model version {version} not found in database")
        
        model_name = model_run.model_name
        
        # Delete from database
        db_session.delete(model_run)
        db_session.commit()
        
        # Also delete from filesystem if exists
        version_dir = os.path.join(VERSIONS_DIR, version)
        if os.path.exists(version_dir):
            import shutil
            shutil.rmtree(version_dir)
        
        # Remove from file registry
        registry = []
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r") as f:
                registry = json.load(f)
        
        # Remove the version from registry
        registry = [v for v in registry if v["version"] != version]
        
        with open(REGISTRY_PATH, "w") as f:
            json.dump(registry, f, indent=2)
        
        return {
            "version": version,
            "model_name": model_name,
            "deleted": True
        }
    
    # Fallback to filesystem only
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


def update_model_name(version: str, new_name: str, db_session=None) -> Dict[str, Any]:
    """Update the display name of a model version."""
    version_dir = os.path.join(VERSIONS_DIR, version)
    
    # Check if version exists in filesystem or database
    exists_in_filesystem = os.path.exists(version_dir)
    exists_in_database = False
    model_run = None
    
    if db_session:
        from app.db.models.model_run import ModelRun
        model_run = db_session.query(ModelRun).filter(
            ModelRun.version == version,
            ModelRun.model_type == "ballistic"
        ).first()
        exists_in_database = model_run is not None
    
    if not exists_in_filesystem and not exists_in_database:
        raise ValueError(f"Model version {version} not found")
    
    old_name = None
    
    # Update registry if filesystem exists
    if exists_in_filesystem:
        registry = []
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH, "r") as f:
                registry = json.load(f)
        
        # Find and update the version in registry
        version_info = next((v for v in registry if v["version"] == version), None)
        if version_info:
            old_name = version_info["model_name"]
            version_info["model_name"] = new_name
            
            with open(REGISTRY_PATH, "w") as f:
                json.dump(registry, f, indent=2)
        
        # Update version metadata
        version_metadata_path = os.path.join(version_dir, "metadata.json")
        if os.path.exists(version_metadata_path):
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
    
    # Update database record
    if model_run:
        old_name = old_name or model_run.model_name
        model_run.model_name = new_name
        if db_session:
            db_session.commit()
    
    # If no old_name was found, use version as fallback
    if old_name is None:
        old_name = version
    
    return {
        "version": version,
        "old_name": old_name,
        "new_name": new_name,
        "updated": True
    }


# =============================================================================
# Prediction logic
# =============================================================================

def load_model(target: str, db_session=None):
    import joblib
    import io

    # Try to load from database first
    if db_session:
        from app.db.models.model_run import ModelRun
        # Try to get the most recent model run with the model file
        model_run = db_session.query(ModelRun).filter(
            ModelRun.model_type == "ballistic",
            ModelRun.model_file.isnot(None)
        ).order_by(ModelRun.created_at.desc()).first()

        if model_run and model_run.model_file:
            try:
                loaded = joblib.load(io.BytesIO(model_run.model_file))
                # Handle new dict structure with log transform flag
                if isinstance(loaded, dict) and "model" in loaded:
                    return loaded
                else:
                    # Old format - wrap in dict
                    return {"model": loaded, "use_log_transform": False}
            except Exception as e:
                print(f"ERROR: Failed to load model from database: {e}")

    # Fallback to filesystem
    model_path = os.path.join(MODEL_DIR, f"{target}.pkl")
    if not os.path.exists(model_path):
        return None
    loaded = joblib.load(model_path)
    # Handle new dict structure with log transform flag
    if isinstance(loaded, dict) and "model" in loaded:
        return loaded
    else:
        # Old format - wrap in dict
        return {"model": loaded, "use_log_transform": False}


def load_preprocessor(db_session=None):
    import joblib
    import io
    
    # Try to load from database first
    if db_session:
        from app.db.models.model_run import ModelRun
        # Try to get the most recent model run with the preprocessor file
        model_run = db_session.query(ModelRun).filter(
            ModelRun.model_type == "ballistic",
            ModelRun.preprocessor_file.isnot(None)
        ).order_by(ModelRun.created_at.desc()).first()
        
        if model_run and model_run.preprocessor_file:
            try:
                return joblib.load(io.BytesIO(model_run.preprocessor_file))
            except Exception as e:
                print(f"ERROR: Failed to load preprocessor from database: {e}")
    
    # Fallback to filesystem
    preprocessor_path = os.path.join(MODEL_DIR, "preprocessor.pkl")
    if not os.path.exists(preprocessor_path):
        print(f"WARNING: Preprocessor not found at {preprocessor_path}")
        return None
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
    # Ensure is_female is present with default value before creating DataFrame
    if "is_female" not in data:
        data["is_female"] = False
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
        "vest_type",
        "ply_orientations",
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

    # Handle new dict structure with log transform flag
    if isinstance(bfd_model, dict):
        actual_model = bfd_model["model"]
        use_log_transform = bfd_model.get("use_log_transform", False)
    else:
        actual_model = bfd_model
        use_log_transform = False

    for shot_num in range(1, num_shots + 1):
        curve_points = []
        for velocity in velocity_range:
            curve_data = data.copy()
            curve_data["impact_velocity_mps"] = velocity
            curve_data["shot_number"] = shot_num

            X = prepare_single_input(curve_data, material_properties, validate=True)
            X_processed = preprocessor.transform(X)
            bfd_prediction = float(actual_model.predict(X_processed)[0])
            # Apply inverse transform if log transform was used
            if use_log_transform:
                bfd_prediction = float(np.expm1(bfd_prediction))

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
    db_session=None,
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
        preprocessor = load_preprocessor(db_session)
        if preprocessor is None:
            raise HTTPException(
                status_code=500,
                detail="Preprocessor not found. The model may have been trained with an older version. Please retrain the model.",
            )

        X_processed = preprocessor.transform(X)

        metrics = metadata.get("metrics", {})

        bfd_prediction = None
        perforation_probability = None

        bfd_model = load_model("backface_deformation_mm", db_session)
        if bfd_model is not None:
            # Handle new dict structure with log transform flag
            if isinstance(bfd_model, dict):
                actual_model = bfd_model["model"]
                use_log_transform = bfd_model.get("use_log_transform", False)
            else:
                actual_model = bfd_model
                use_log_transform = False
            
            bfd_prediction = float(actual_model.predict(X_processed)[0])
            # Apply inverse transform if log transform was used
            if use_log_transform:
                bfd_prediction = float(np.expm1(bfd_prediction))

        perforation_model = load_model("perforated", db_session)
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


def predict(data: Dict[str, Any], material_properties: Dict[str, Dict[str, float]], db_session=None) -> Dict[str, Any]:
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run training first.",
        )

    X = prepare_single_input(data, material_properties, validate=True)

    # Load and apply preprocessor
    preprocessor = load_preprocessor(db_session)
    if preprocessor is None:
        raise HTTPException(
            status_code=500,
            detail="Preprocessor not found. The model may have been trained with an older version. Please retrain the model.",
        )

    X_processed = preprocessor.transform(X)

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

    bfd_model = load_model("backface_deformation_mm", db_session)
    if bfd_model is not None:
        bfd_prediction = float(bfd_model.predict(X_processed)[0])

    perforation_model = load_model("perforated", db_session)
    if perforation_model is not None:
        perforation_probability = float(perforation_model.predict_proba(X_processed)[0, 1])

    fail_model = load_model("pass_fail", db_session)
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
        load_model_version(version, db_session=db_session)
    
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
    
    # Build query for shot data - try both test session and vest_number approaches
    # First try with test sessions (structured data)
    query_with_session = (
        db_session.query(ShotData, TestSession, Vest)
        .join(TestSession, ShotData.test_session_id == TestSession.id)
        .outerjoin(Vest, TestSession.vest_id == Vest.id)
    )
    
    # Filter by protocol if specified
    if protocol_filter and protocol_filter != "all":
        query_with_session = query_with_session.filter(TestSession.protocol == protocol_filter)
    
    # Only include shots with trauma data
    query_with_session = query_with_session.filter(ShotData.trauma_mm.isnot(None))
    
    results = query_with_session.all()
    
    # If no results with test sessions, fall back to vest_number approach (like training)
    if not results:
        # Query shots with vest_number (matches training data structure)
        query_with_vest = (
            db_session.query(ShotData)
            .filter(ShotData.trauma_mm.isnot(None))
            .filter(ShotData.vest_number.isnot(None))
        )
        
        shots_only = query_with_vest.all()
        
        if not shots_only:
            return {
                "vest_averages": [],
                "point_data": [],
                "total_points": 0,
                "message": "No test data found matching criteria"
            }
        
        # Convert to format expected by rest of function
        results = []
        for shot in shots_only:
            # Create dummy test session and vest objects for compatibility
            class DummyTestSession:
                def __init__(self):
                    self.id = None
                    self.protocol = None
                    self.conditioning = "dry"
                    self.vest_id = None
                    
            class DummyVest:
                def __init__(self):
                    self.id = None
                    self.vest_code = shot.vest_number
                    
            results.append((shot, DummyTestSession(), DummyVest()))
    
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

    # Batch fetch all vest layers and materials to avoid N+1 queries
    vest_ids = [vest.id for _, _, vest in results if vest]
    vest_layers = db_session.query(VestLayer).filter(VestLayer.vest_id.in_(vest_ids)).all() if vest_ids else []
    material_ids = list(set(vl.material_id for vl in vest_layers))
    materials = {m.id: m for m in db_session.query(Material).filter(Material.id.in_(material_ids)).all()} if material_ids else {}

    # Batch fetch all ammunition to avoid N+1 queries
    calibers = list(set(shot_data.caliber for shot_data, _, _ in results if shot_data.caliber))
    ammunition_map = {a.caliber: a for a in db_session.query(Ammunition).filter(Ammunition.caliber.in_(calibers)).all()} if calibers else {}

    # Group vest layers by vest_id
    vest_layers_by_vest = {}
    for vl in vest_layers:
        if vl.vest_id not in vest_layers_by_vest:
            vest_layers_by_vest[vl.vest_id] = []
        vest_layers_by_vest[vl.vest_id].append(vl)

    # Handle model dict structure once
    if isinstance(bfd_model, dict):
        actual_model = bfd_model["model"]
        use_log_transform = bfd_model.get("use_log_transform", False)
    else:
        actual_model = bfd_model
        use_log_transform = False

    # Build all prediction inputs as a batch for speed
    batch_rows = []
    row_metadata = []  # parallel list of (vest_identifier, vest_name, protocol, actual_bfd, shot_number, protection_level, caliber)
    for shot_data_rec, test_session, vest in results:
        composition_parts = []
        total_layers = 0
        if vest:
            layers = vest_layers_by_vest.get(vest.id, [])
            for vl in sorted(layers, key=lambda x: x.layer_index or 0):
                material = materials.get(vl.material_id)
                if material:
                    count = vl.layer_count or 1
                    total_layers += count
                    composition_parts.append(f"{count} {material.name}")

        vest_composition = " + ".join(composition_parts) if composition_parts else ""
        caliber = shot_data_rec.caliber
        ammunition = ammunition_map.get(caliber)

        batch_rows.append({
            "vest_composition": vest_composition,
            "number_of_layers": total_layers,
            "ammunition_used": ammunition.name if ammunition else caliber,
            "threat_level": shot_data_rec.protection_level,
            "shot_number": int(float(shot_data_rec.shot_number)) if shot_data_rec.shot_number else 1,
            "impact_velocity_mps": float(shot_data_rec.velocity_m_s) if shot_data_rec.velocity_m_s else None,
            "impact_angle_deg": float(shot_data_rec.angle_degrees) if shot_data_rec.angle_degrees else 0.0,
            "bullet_mass_g": float(ammunition.projectile_mass_grams) if ammunition and ammunition.projectile_mass_grams else None,
            "temperature_c": float(shot_data_rec.temperature_c) if shot_data_rec.temperature_c else 20.0,
            "humidity_pct": float(shot_data_rec.humidity_percent) if shot_data_rec.humidity_percent else 50.0,
            "condition": test_session.conditioning if test_session else "dry",
            "panel_side": shot_data_rec.side,
            "caliber_diameter_mm": float(ammunition.caliber_diameter_mm) if ammunition and ammunition.caliber_diameter_mm else None,
            "caliber_length_mm": float(ammunition.caliber_length_mm) if ammunition and ammunition.caliber_length_mm else None,
            "vest_type": vest.vest_type if vest else None,
            "is_female": vest.is_female if vest and hasattr(vest, 'is_female') else False,
            "ply_orientations": None,
        })

        vest_identifier = vest.vest_code if vest else f"Unknown-{shot_data_rec.test_session_id}"
        row_metadata.append({
            "vest_identifier": vest_identifier,
            "vest_name": vest.vest_code if vest else "Unknown",
            "protocol": test_session.protocol if test_session else "Unknown",
            "actual_bfd": float(shot_data_rec.trauma_mm),
            "shot_number": shot_data_rec.shot_number,
            "protection_level": (getattr(shot_data_rec, 'protection_level', None) or
                               (test_session.threat_level if test_session else None) or
                               (vest.threat_level if vest else None) or
                               "Unknown"),
            "caliber": getattr(shot_data_rec, 'caliber', 'Unknown') if getattr(shot_data_rec, 'caliber', None) else "Unknown",
        })

    # Shared categorical feature names for batch processing
    feature_columns = metadata.get("feature_columns", [])
    categorical_feature_names = {
        "vest_composition", "ammunition_used", "threat_level", "condition",
        "panel_side", "weave_type", "material_type", "vest_type", "ply_orientations",
    }
    for mat_name in material_properties:
        prefix = mat_name.lower().replace(" ", "_").replace("-", "_")
        categorical_feature_names.add(f"composition_material_class_{prefix}")

    # Batch feature engineering + prediction
    try:
        batch_df = pd.DataFrame(batch_rows)
        batch_df = add_engineered_features(batch_df, material_properties, validate=False)

        if feature_columns:
            for col in feature_columns:
                if col not in batch_df.columns:
                    if col in categorical_feature_names:
                        batch_df[col] = "unknown"
                    else:
                        batch_df[col] = np.nan
            batch_df = batch_df[feature_columns]

        for col in batch_df.columns:
            if col in categorical_feature_names:
                batch_df[col] = batch_df[col].fillna("unknown").astype(str)

        batch_df = fill_missing_features(batch_df)
        X_processed = preprocessor.transform(batch_df)
        predictions = actual_model.predict(X_processed)
        if use_log_transform:
            predictions = np.expm1(predictions)

        for i, meta in enumerate(row_metadata):
            predicted_bfd = float(predictions[i])
            actual_bfd = meta["actual_bfd"]
            if actual_bfd != 0:
                percent_error = abs(predicted_bfd - actual_bfd) / actual_bfd * 100
            else:
                percent_error = abs(predicted_bfd - actual_bfd)

            vest_identifier = meta["vest_identifier"]
            if vest_identifier not in vest_errors:
                vest_errors[vest_identifier] = []
            vest_errors[vest_identifier].append(percent_error)

            point_data.append({
                "vest_code": vest_identifier,
                "vest_name": meta["vest_name"],
                "protocol": meta["protocol"],
                "actual_bfd": actual_bfd,
                "predicted_bfd": predicted_bfd,
                "percent_error": percent_error,
                "shot_number": meta["shot_number"],
                "protection_level": meta["protection_level"],
                "caliber": meta["caliber"],
            })
    except Exception as e:
        print(f"ERROR: Batch prediction failed: {e}")
        import traceback
        traceback.print_exc()
    
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
            # Batch predict all anchor points at once
            anchor_input_df = anchor_df.copy()
            anchor_input_df = add_engineered_features(anchor_input_df, material_properties, validate=False)

            if feature_columns:
                # Add missing columns with defaults
                for col in feature_columns:
                    if col not in anchor_input_df.columns:
                        if col in categorical_feature_names:
                            anchor_input_df[col] = "unknown"
                        else:
                            anchor_input_df[col] = np.nan
                
                # Only select columns that exist (defensive)
                existing_cols = [col for col in feature_columns if col in anchor_input_df.columns]
                missing_cols = set(feature_columns) - set(existing_cols)
                if missing_cols:
                    print(f"Warning: Columns missing after addition: {missing_cols}")
                anchor_input_df = anchor_input_df[existing_cols]

            for col in anchor_input_df.columns:
                if col in categorical_feature_names:
                    anchor_input_df[col] = anchor_input_df[col].fillna("unknown").astype(str)

            anchor_input_df = fill_missing_features(anchor_input_df)
            X_anchor = preprocessor.transform(anchor_input_df)
            anchor_predictions = actual_model.predict(X_anchor)
            if use_log_transform:
                anchor_predictions = np.expm1(anchor_predictions)

            for i, (_, row) in enumerate(anchor_df.iterrows()):
                actual_bfd = row.get('backface_deformation_mm')
                if actual_bfd is not None:
                    actual_bfd = float(actual_bfd)
                    predicted_bfd = float(anchor_predictions[i])
                    if actual_bfd != 0:
                        percent_error = abs(predicted_bfd - actual_bfd) / actual_bfd * 100
                    else:
                        percent_error = abs(predicted_bfd - actual_bfd)
                    anchor_point_errors.append(percent_error)
                    vest_composition = row.get('vest_composition', '')
                    if vest_composition not in anchor_point_material_errors:
                        anchor_point_material_errors[vest_composition] = []
                    anchor_point_material_errors[vest_composition].append(percent_error)

            # Filter out NaN values and calculate average
            valid_errors = [e for e in anchor_point_errors if not (e != e)]  # Filter NaN
            anchor_avg_error = round(sum(valid_errors) / len(valid_errors), 2) if valid_errors else 0
            
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
