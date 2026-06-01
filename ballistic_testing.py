"""
FastAPI backend for ballistic vest surrogate modeling.

This version is built for Jacob's current training CSV:
    /Users/jacobmosu/Desktop/ballistic_training_dataset_draft.csv

What it does:
- Trains XGBoost models from a shot-level ballistic vest CSV.
- Uses the practical inputs currently available:
    1. material_thickness_mm
    2. material_weight_g_m2
    3. number_of_layers
    4. vest_composition
    5. ammunition_used / threat_level
    6. shot_number
    plus optional velocity / environment / panel variables when present.
- Predicts:
    - backface_deformation_mm
    - perforation_probability
    - fail_probability

Important:
This is for engineering screening / experiment reduction only.
It is NOT a replacement for certified ballistic testing.
"""

from __future__ import annotations

import os
import json
import re
from typing import Optional, Dict, Any, List

import joblib
import numpy as np
import pandas as pd

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.preprocessing import FunctionTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    accuracy_score,
    roc_auc_score,
    brier_score_loss,
)

from xgboost import XGBRegressor, XGBClassifier


# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Your current training CSV path
DEFAULT_TRAINING_CSV_PATH = "/Users/jacobmosu/Desktop/ballistic_training_dataset_draft.csv"

# Start simple: your uploaded Excel-derived dataset clearly supports this target.
REGRESSION_TARGETS = [
    "backface_deformation_mm",
]

# These are binary targets.
# IMPORTANT:
# - perforated: 1 = perforated, 0 = not perforated
# - pass_fail: 1 = failed, 0 = passed
#
# The column name "pass_fail" is kept only because the draft CSV already uses it.
# In the API response, it is exposed as fail_probability to avoid confusion.
CLASSIFICATION_TARGETS = [
    "perforated",
    "pass_fail",
]

MODEL_PATHS = {
    "backface_deformation_mm": os.path.join(MODEL_DIR, "model_bfd.pkl"),
    "perforated": os.path.join(MODEL_DIR, "model_perforation.pkl"),
    "pass_fail": os.path.join(MODEL_DIR, "model_fail.pkl"),
}

METADATA_PATH = os.path.join(MODEL_DIR, "metadata.json")

# Material property assumptions used to turn vest_composition strings into
# order-aware engineering features. Thickness is per ply/item as listed.
MATERIAL_PROPERTIES = {
    "UD245": {"density_g_cm3": 0.95, "thickness_mm": 0.25},
    "SOFT3000": {"density_g_cm3": 1.10, "thickness_mm": 0.30},
    "PE_ESPUMADO": {"density_g_cm3": 0.06, "thickness_mm": 5.00},
    "STOP_III": {"density_g_cm3": 1.10, "thickness_mm": 10.00},
    "LADY_STOP_III": {"density_g_cm3": 1.08, "thickness_mm": 8.50},
    "DEF_III": {"density_g_cm3": 1.15, "thickness_mm": 12.00},
    "CHALECO_RB4": {"density_g_cm3": 1.30, "thickness_mm": 20.00},
}

MATERIAL_ALIASES = {
    "UD245": ["UD245", "UD 245"],
    "SOFT3000": ["SOFT3000", "SOFT 3000"],
    "PE_ESPUMADO": ["PE ESPUMADO", "ESPUMADO", "FOAM", "PE FOAM"],
    "STOP_III": ["STOP III", "STOP 3"],
    "LADY_STOP_III": ["LADY STOP III", "LADY STOP 3"],
    "DEF_III": ["DEF III", "DEF 3"],
    "CHALECO_RB4": ["CHALECO RB4", "RB4"],
}


# =============================================================================
# API input/output schemas
# =============================================================================

class BallisticInput(BaseModel):
    """
    Input variables for one prediction.

    Required now:
    1. material_thickness_mm
    2. material_weight_g_m2
    3. number_of_layers
    4. vest_composition
    5. ammunition_used / threat_level
    6. shot_number

    Optional variables are included because the dataset may contain them now
    or you may collect them in future tests.
    """

    material_thickness_mm: Optional[float] = Field(None, examples=[12.5])
    material_weight_g_m2: Optional[float] = Field(None, examples=[6500])
    number_of_layers: int = Field(..., examples=[48])

    vest_composition: str = Field(
        ...,
        examples=["40 SOFT3000 + 2 UD245 + 1 PE Espumado + 5 SOFT3000"],
    )

    ammunition_used: str = Field(..., examples=[".44 MAG"])
    threat_level: Optional[str] = Field(None, examples=["RB3"])
    shot_number: int = Field(..., examples=[1])

    # Optional variables that may improve predictions if they exist in training data
    impact_velocity_mps: Optional[float] = Field(None, examples=[434.6])
    impact_angle_deg: Optional[float] = Field(0.0, examples=[0.0])
    bullet_mass_g: Optional[float] = Field(None, examples=[15.6])

    temperature_c: Optional[float] = Field(22.0, examples=[22.0])
    humidity_pct: Optional[float] = Field(50.0, examples=[50.0])

    condition: Optional[str] = Field(None, examples=["Seco"])
    panel_side: Optional[str] = Field(None, examples=["Delantero"])

    # Optional geometry
    panel_width_mm: Optional[float] = None
    panel_height_mm: Optional[float] = None
    plate_curvature_mm: Optional[float] = None
    shot_x_position_mm: Optional[float] = None
    shot_y_position_mm: Optional[float] = None
    edge_distance_mm: Optional[float] = None
    previous_shot_distance_mm: Optional[float] = None

    # Optional material/fabric properties for future data collection
    fabric_elongation_pct: Optional[float] = None
    fabric_strain_pct: Optional[float] = None
    max_tensile_strength_mpa: Optional[float] = None
    fiber_thickness_um: Optional[float] = None
    epoxy_percentage: Optional[float] = None
    weave_type: Optional[str] = None
    fiber_orientation_deg: Optional[float] = None


class PredictionResponse(BaseModel):
    predicted_backface_deformation_mm: Optional[float] = None
    estimated_backface_absolute_error_mm: Optional[float] = None
    backface_prediction_lower_80_mm: Optional[float] = None
    backface_prediction_upper_80_mm: Optional[float] = None
    backface_prediction_lower_95_mm: Optional[float] = None
    backface_prediction_upper_95_mm: Optional[float] = None
    conservative_backface_deformation_upper_mm: Optional[float] = None

    perforation_probability: Optional[float] = None
    perforation_probability_estimated_error: Optional[float] = None
    fail_probability: Optional[float] = None
    fail_probability_estimated_error: Optional[float] = None

    recommendation: str
    confidence_note: str
    warning: str


class TrainPathRequest(BaseModel):
    csv_path: str = Field(
        DEFAULT_TRAINING_CSV_PATH,
        examples=[DEFAULT_TRAINING_CSV_PATH],
    )


# =============================================================================
# Feature engineering
# =============================================================================

def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize possible alternate column names from old exports / manual edits.

    This lets the model accept slightly different CSV headers without breaking.
    """
    df = df.copy()

    rename_map = {
        "thickness_mm": "material_thickness_mm",
        "material_weight": "material_weight_g_m2",
        "areal_density_g_m2": "material_weight_g_m2",
        "areal_density_kg_m2": "material_weight_kg_m2",
        "layer_count": "number_of_layers",
        "layers": "number_of_layers",
        "composition": "vest_composition",
        "ammo": "ammunition_used",
        "velocity_mps": "impact_velocity_mps",
        "trauma_mm": "backface_deformation_mm",
        "bfd_mm": "backface_deformation_mm",
        "backface_signature_mm": "backface_deformation_mm",
        "fail": "pass_fail",
        "failed": "pass_fail",
        "perforation": "perforated",
    }

    for old, new in rename_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    return df


def clean_binary_target(series: pd.Series) -> pd.Series:
    """
    Converts pass/fail or yes/no-ish labels into 0/1.

    Intended meanings:
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


def normalize_composition_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().upper())


def identify_material_name(raw_name: str) -> str:
    normalized = normalize_composition_text(raw_name)

    for material, aliases in sorted(
        MATERIAL_ALIASES.items(),
        key=lambda item: max(len(alias) for alias in item[1]),
        reverse=True,
    ):
        for alias in aliases:
            if alias in normalized:
                return material

    return "UNKNOWN_MATERIAL"


def parse_vest_composition(composition: Any) -> List[Dict[str, Any]]:
    """
    Parse strings such as:
    "40 SOFT3000 + 2 UD245 + 1 PE Espumado + 5 SOFT3000"
    into ordered material segments with count, density, and thickness.
    """
    text = normalize_composition_text(composition)
    if not text:
        return []

    segments: List[Dict[str, Any]] = []
    parts = [part.strip() for part in re.split(r"\s*\+\s*", text) if part.strip()]

    for position, part in enumerate(parts, start=1):
        match = re.match(r"^(?:(\d+(?:\.\d+)?)\s*)?(.*)$", part)
        if match is None:
            continue

        count_text, raw_name = match.groups()
        count = float(count_text) if count_text else 1.0
        material = identify_material_name(raw_name)
        properties = MATERIAL_PROPERTIES.get(material, {})
        thickness_mm = properties.get("thickness_mm", 0.0)
        density_g_cm3 = properties.get("density_g_cm3", 0.0)

        segments.append({
            "position": position,
            "material": material,
            "count": count,
            "thickness_mm": thickness_mm,
            "density_g_cm3": density_g_cm3,
            "segment_thickness_mm": count * thickness_mm,
            # 1 g/cm^3 across 1 mm equals 1 kg/m^2 of areal density.
            "segment_areal_density_kg_m2": count * thickness_mm * density_g_cm3,
        })

    return segments


def build_composition_features(composition: Any) -> Dict[str, Any]:
    segments = parse_vest_composition(composition)
    features: Dict[str, Any] = {}

    for material in MATERIAL_PROPERTIES:
        features[f"composition_count_{material.lower()}"] = 0.0
        features[f"composition_thickness_mm_{material.lower()}"] = 0.0
        features[f"composition_areal_density_kg_m2_{material.lower()}"] = 0.0
        features[f"composition_first_position_{material.lower()}"] = 0.0
        features[f"composition_last_position_{material.lower()}"] = 0.0

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
        })
        return features

    total_segments = len(segments)
    unknown_segment_count = sum(1 for segment in segments if segment["material"] == "UNKNOWN_MATERIAL")
    unknown_item_count = sum(segment["count"] for segment in segments if segment["material"] == "UNKNOWN_MATERIAL")
    total_count = sum(segment["count"] for segment in segments)
    total_thickness = sum(segment["segment_thickness_mm"] for segment in segments)
    total_areal_density = sum(segment["segment_areal_density_kg_m2"] for segment in segments)
    weighted_density = total_areal_density / total_thickness if total_thickness else 0.0

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
        if material in MATERIAL_PROPERTIES:
            prefix = material.lower()
            features[f"composition_count_{prefix}"] += segment["count"]
            features[f"composition_thickness_mm_{prefix}"] += segment["segment_thickness_mm"]
            features[f"composition_areal_density_kg_m2_{prefix}"] += segment["segment_areal_density_kg_m2"]
            if features[f"composition_first_position_{prefix}"] == 0.0:
                features[f"composition_first_position_{prefix}"] = segment["position"]
            features[f"composition_last_position_{prefix}"] = segment["position"]

        remaining = segment["segment_thickness_mm"]
        density = segment["density_g_cm3"]
        while remaining > 0:
            if running_thickness < front_cutoff:
                add_thickness = min(remaining, front_cutoff - running_thickness)
                front_thickness += add_thickness
                front_areal_density += add_thickness * density
            else:
                add_thickness = remaining
                back_thickness += add_thickness
                back_areal_density += add_thickness * density

            running_thickness += add_thickness
            remaining -= add_thickness

    front_density = front_areal_density / front_thickness if front_thickness else 0.0
    back_density = back_areal_density / back_thickness if back_thickness else 0.0

    features.update({
        "composition_total_segments": total_segments,
        "composition_unknown_segment_count": unknown_segment_count,
        "composition_unknown_item_count": unknown_item_count,
        "composition_has_unknown_material": int(unknown_segment_count > 0),
        "composition_total_item_count": total_count,
        "composition_calculated_thickness_mm": total_thickness,
        "composition_calculated_areal_density_kg_m2": total_areal_density,
        "composition_weighted_density_g_cm3": weighted_density,
        "composition_front_half_density_g_cm3": front_density,
        "composition_back_half_density_g_cm3": back_density,
        "composition_density_front_minus_back": front_density - back_density,
        "composition_density_gradient": segments[-1]["density_g_cm3"] - segments[0]["density_g_cm3"],
        "composition_material_transition_count": transitions,
        "composition_unique_material_count": len(set(sequence)),
        "composition_sequence": ">".join(sequence),
        "composition_first_material": sequence[0],
        "composition_second_material": sequence[1] if len(sequence) > 1 else "none",
        "composition_penultimate_material": sequence[-2] if len(sequence) > 1 else "none",
        "composition_last_material": sequence[-1],
    })

    return features


def add_composition_features(df: pd.DataFrame) -> pd.DataFrame:
    if "vest_composition" not in df.columns:
        return df

    composition_features = pd.DataFrame(
        [build_composition_features(value) for value in df["vest_composition"]],
        index=df.index,
    )

    return pd.concat([df, composition_features], axis=1)

def add_engineered_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add simple physics/design features from the variables currently available.
    """
    df = normalize_column_names(df)
    df = df.copy()
    df = add_composition_features(df)

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
        "backface_deformation_mm",
        "perforated",
        "pass_fail",
    ]

    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    known_complete_stack = (
        df.get("composition_has_unknown_material", pd.Series(1, index=df.index)).fillna(1) == 0
    )

    if "composition_calculated_thickness_mm" in df.columns:
        if "material_thickness_mm" not in df.columns:
            df["material_thickness_mm"] = np.nan
        calculated_thickness = df["composition_calculated_thickness_mm"].where(known_complete_stack)
        df["material_thickness_mm"] = df["material_thickness_mm"].fillna(
            calculated_thickness.replace(0, np.nan)
        )

    if "composition_calculated_areal_density_kg_m2" in df.columns:
        if "material_weight_g_m2" not in df.columns:
            df["material_weight_g_m2"] = np.nan
        calculated_areal_density = df["composition_calculated_areal_density_kg_m2"].where(known_complete_stack)
        df["material_weight_g_m2"] = df["material_weight_g_m2"].fillna(
            calculated_areal_density.replace(0, np.nan) * 1000.0
        )

    # Weight conversions.
    if "material_weight_g_m2" in df.columns:
        df["material_weight_kg_m2"] = df["material_weight_g_m2"] / 1000.0

    if "material_weight_kg_m2" in df.columns and "material_weight_g_m2" not in df.columns:
        df["material_weight_g_m2"] = df["material_weight_kg_m2"] * 1000.0

    if "composition_calculated_thickness_mm" in df.columns and "material_thickness_mm" in df.columns:
        df["measured_minus_calculated_thickness_mm"] = (
            df["material_thickness_mm"] - df["composition_calculated_thickness_mm"]
        )
        df["measured_to_calculated_thickness_ratio"] = (
            df["material_thickness_mm"] / df["composition_calculated_thickness_mm"].replace(0, np.nan)
        )

    if "composition_calculated_areal_density_kg_m2" in df.columns and "material_weight_kg_m2" in df.columns:
        df["measured_minus_calculated_areal_density_kg_m2"] = (
            df["material_weight_kg_m2"] - df["composition_calculated_areal_density_kg_m2"]
        )
        df["measured_to_calculated_areal_density_ratio"] = (
            df["material_weight_kg_m2"] / df["composition_calculated_areal_density_kg_m2"].replace(0, np.nan)
        )

    # Basic vest design features.
    if "material_thickness_mm" in df.columns and "number_of_layers" in df.columns:
        df["avg_layer_thickness_mm"] = (
            df["material_thickness_mm"] / df["number_of_layers"].replace(0, np.nan)
        )

    if "material_weight_g_m2" in df.columns and "number_of_layers" in df.columns:
        df["weight_per_layer_g_m2"] = (
            df["material_weight_g_m2"] / df["number_of_layers"].replace(0, np.nan)
        )

    if "material_thickness_mm" in df.columns and "material_weight_g_m2" in df.columns:
        df["thickness_to_weight_ratio"] = (
            df["material_thickness_mm"] / df["material_weight_g_m2"].replace(0, np.nan)
        )

    # Shot importance.
    if "shot_number" in df.columns:
        df["is_primary_shot_1_to_3"] = (df["shot_number"] <= 3).astype(int)
        df["is_later_shot_4_to_6"] = (df["shot_number"] >= 4).astype(int)

    # Optional physics features.
    if "bullet_mass_g" in df.columns and "impact_velocity_mps" in df.columns:
        mass_kg = df["bullet_mass_g"] / 1000.0
        velocity = df["impact_velocity_mps"]

        df["kinetic_energy_j"] = 0.5 * mass_kg * velocity ** 2
        df["momentum_kg_mps"] = mass_kg * velocity

        if "impact_angle_deg" in df.columns:
            angle_rad = np.radians(df["impact_angle_deg"].fillna(0.0))
            normal_velocity = velocity * np.cos(angle_rad)
            df["normal_velocity_mps"] = normal_velocity
            df["normal_energy_j"] = 0.5 * mass_kg * normal_velocity ** 2

        if "material_weight_kg_m2" in df.columns:
            df["energy_per_areal_density"] = (
                df["kinetic_energy_j"] / df["material_weight_kg_m2"].replace(0, np.nan)
            )
            df["momentum_per_areal_density"] = (
                df["momentum_kg_mps"] / df["material_weight_kg_m2"].replace(0, np.nan)
            )

        if "number_of_layers" in df.columns:
            df["energy_per_layer"] = (
                df["kinetic_energy_j"] / df["number_of_layers"].replace(0, np.nan)
            )

    return df.replace([np.inf, -np.inf], np.nan)


def split_columns(X: pd.DataFrame) -> tuple[List[str], List[str]]:
    categorical_cols = X.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    numeric_cols = [col for col in X.columns if col not in categorical_cols]
    return numeric_cols, categorical_cols


def to_string_array(values):
    return values.astype(str)


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    numeric_cols, categorical_cols = split_columns(X)

    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
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

def train_from_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    df = add_engineered_features(df)

    # Clean classification target labels if needed.
    for target in CLASSIFICATION_TARGETS:
        if target in df.columns and not pd.api.types.is_numeric_dtype(df[target]):
            df[target] = clean_binary_target(df[target])

    available_regression_targets = [t for t in REGRESSION_TARGETS if t in df.columns]
    available_classification_targets = [t for t in CLASSIFICATION_TARGETS if t in df.columns]

    all_targets = available_regression_targets + available_classification_targets

    if not all_targets:
        raise ValueError(
            "CSV must contain at least one target column. "
            f"Expected one of: {REGRESSION_TARGETS + CLASSIFICATION_TARGETS}"
        )

    # Drop rows that do not have any target value at all.
    df = df.dropna(subset=all_targets, how="all").copy()

    # Do not train on ID/source columns. They can accidentally cause memorization.
    columns_to_exclude_from_features = set(all_targets + [
        "source_file",
        "source_sheet",
        "file_name",
        "id",
        "row_id",
    ])

    feature_cols = [col for col in df.columns if col not in columns_to_exclude_from_features]
    X = df[feature_cols]
    X = X.dropna(axis=1, how="all")
    X = fill_missing_features(X)

    metrics: Dict[str, Any] = {}
    trained_targets: List[str] = []
    feature_columns = X.columns.tolist()

    # Regression training.
    for target in available_regression_targets:
        y = pd.to_numeric(df[target], errors="coerce")
        valid = y.notna()

        X_valid = X.loc[valid]
        y_valid = y.loc[valid]

        if len(y_valid) < 8:
            metrics[target] = {
                "type": "regression",
                "error": f"Not enough valid rows to train. Found {len(y_valid)}.",
            }
            continue

        test_size = 0.2 if len(y_valid) >= 20 else 0.25

        X_train, X_test, y_train, y_test = train_test_split(
            X_valid,
            y_valid,
            test_size=test_size,
            random_state=42,
        )

        pipeline = Pipeline([
            ("preprocess", build_preprocessor(X_train)),
            ("model", build_regressor()),
        ])

        pipeline.fit(X_train, y_train)
        preds = pipeline.predict(X_test)

        error_stats = regression_error_summary(y_test, preds)
        mae = float(mean_absolute_error(y_test, preds))
        r2 = float(r2_score(y_test, preds)) if len(y_test) > 1 else None

        joblib.dump(pipeline, MODEL_PATHS[target])
        trained_targets.append(target)

        metrics[target] = {
            "type": "regression",
            "mae": mae,
            "rmse": error_stats["rmse"],
            "r2": r2,
            "error_estimates": error_stats,
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
        }

    # Classification training.
    for target in available_classification_targets:
        y = pd.to_numeric(df[target], errors="coerce")
        valid = y.notna()

        X_valid = X.loc[valid]
        y_valid = y.loc[valid].astype(int)

        if len(y_valid) < 8:
            metrics[target] = {
                "type": "classification",
                "error": f"Not enough valid rows to train. Found {len(y_valid)}.",
            }
            continue

        if y_valid.nunique() < 2:
            metrics[target] = {
                "type": "classification",
                "error": "Only one class present. Model was not trained.",
            }
            continue

        class_counts = y_valid.value_counts()
        can_stratify = class_counts.min() >= 2

        X_train, X_test, y_train, y_test = train_test_split(
            X_valid,
            y_valid,
            test_size=0.2,
            random_state=42,
            stratify=y_valid if can_stratify else None,
        )

        pipeline = Pipeline([
            ("preprocess", build_preprocessor(X_train)),
            ("model", build_classifier()),
        ])

        pipeline.fit(X_train, y_train)

        class_preds = pipeline.predict(X_test)
        prob_preds = pipeline.predict_proba(X_test)[:, 1]

        acc = float(accuracy_score(y_test, class_preds))
        probability_error_stats = classification_error_summary(y_test, prob_preds)

        try:
            auc = float(roc_auc_score(y_test, prob_preds))
        except ValueError:
            auc = None

        joblib.dump(pipeline, MODEL_PATHS[target])
        trained_targets.append(target)

        metrics[target] = {
            "type": "classification",
            "accuracy": acc,
            "roc_auc": auc,
            "probability_error_estimates": probability_error_stats,
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
            "class_balance": {
                str(k): int(v) for k, v in y_valid.value_counts().to_dict().items()
            },
        }

    metadata = {
        "feature_columns": feature_columns,
        "trained_targets": trained_targets,
        "metrics": metrics,
        "notes": {
            "pass_fail_meaning": "1 = failed, 0 = passed",
            "perforated_meaning": "1 = perforated, 0 = not perforated",
            "warning": "Screening model only. Requires physical ballistic validation.",
        },
    }

    with open(METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def train_from_csv_path(csv_path: str) -> Dict[str, Any]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    return train_from_dataframe(df)


# =============================================================================
# Prediction logic
# =============================================================================

def load_model(target: str):
    path = MODEL_PATHS.get(target)

    if path is None or not os.path.exists(path):
        return None

    return joblib.load(path)


def load_metadata() -> Dict[str, Any]:
    if not os.path.exists(METADATA_PATH):
        return {}

    with open(METADATA_PATH, "r") as f:
        return json.load(f)


def prepare_single_input(data: BallisticInput) -> pd.DataFrame:
    row = data.model_dump()
    df = pd.DataFrame([row])
    df = add_engineered_features(df)

    metadata = load_metadata()
    feature_columns = metadata.get("feature_columns", [])

    categorical_feature_names = {
        "vest_composition",
        "ammunition_used",
       "threat_level",
        "condition",
        "panel_side",
        "weave_type",
    }

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

    return float(value + multiplier * mae)


def make_recommendation(
    bfd_upper: Optional[float],
    perforation_prob: Optional[float],
    fail_prob: Optional[float],
) -> str:
    """
    Conservative screening logic.

    Default NIJ-style BFD screening reference often uses 44 mm,
    but you should adjust thresholds based on the exact standard/company policy.
    """
    high_risk = False
    reasons = []

    if bfd_upper is not None and bfd_upper >= 44:
        high_risk = True
        reasons.append("conservative backface deformation estimate is at/above 44 mm")

    if perforation_prob is not None and perforation_prob >= 0.05:
        high_risk = True
        reasons.append("perforation probability is elevated")

    if fail_prob is not None and fail_prob >= 0.10:
        high_risk = True
        reasons.append("fail probability is elevated")

    if high_risk:
        return (
            "High-risk design. Physical ballistic test strongly recommended. "
            "Reason(s): " + "; ".join(reasons) + "."
        )

    return (
        "Lower-risk screening result. Still requires physical validation before "
        "approval, sale, field use, or certification."
    )


# =============================================================================
# FastAPI app
# =============================================================================

app = FastAPI(
    title="Ballistic Vest Surrogate Model API",
    description=(
        "Backend for predicting ballistic vest screening outcomes from structured "
        "test/design variables."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "Ballistic vest surrogate model backend is running.",
        "docs": "/docs",
        "default_training_csv_path": DEFAULT_TRAINING_CSV_PATH,
    }


@app.get("/health")
def health():
    metadata = load_metadata()

    return {
        "status": "ok",
        "models_trained": metadata.get("trained_targets", []),
        "has_metadata": bool(metadata),
    }


@app.post("/train")
async def train_model(file: UploadFile = File(...)):
    """
    Train by uploading a CSV through Swagger UI at /docs.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file.")

    try:
        df = pd.read_csv(file.file)
        metadata = train_from_dataframe(df)

        return {
            "message": "Training complete.",
            "metadata": metadata,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/train-from-path")
def train_model_from_path(request: TrainPathRequest):
    """
    Train directly from a CSV path on your Mac.

    Since your CSV is on your Desktop, the default request body can be:
    {
      "csv_path": "/Users/jacobmosu/Desktop/ballistic_training_dataset_draft.csv"
    }
    """
    try:
        metadata = train_from_csv_path(request.csv_path)

        return {
            "message": "Training complete.",
            "csv_path": request.csv_path,
            "metadata": metadata,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/train-default")
def train_default_csv():
    """
    One-click training from:
    /Users/jacobmosu/Desktop/ballistic_training_dataset_draft.csv
    """
    try:
        metadata = train_from_csv_path(DEFAULT_TRAINING_CSV_PATH)

        return {
            "message": "Training complete.",
            "csv_path": DEFAULT_TRAINING_CSV_PATH,
            "metadata": metadata,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict", response_model=PredictionResponse)
def predict(data: BallisticInput):
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(
            status_code=404,
            detail="No trained model found. Run /train, /train-from-path, or /train-default first.",
        )

    X = prepare_single_input(data)
    metrics = metadata.get("metrics", {})

    bfd_prediction = None
    perforation_probability = None
    fail_probability = None

    bfd_model = load_model("backface_deformation_mm")
    if bfd_model is not None:
        bfd_prediction = float(bfd_model.predict(X)[0])

    perforation_model = load_model("perforated")
    if perforation_model is not None:
        perforation_probability = float(perforation_model.predict_proba(X)[0, 1])

    fail_model = load_model("pass_fail")
    if fail_model is not None:
        fail_probability = float(fail_model.predict_proba(X)[0, 1])

    bfd_metric = metrics.get("backface_deformation_mm", {})
    bfd_error_stats = bfd_metric.get("error_estimates", {})
    bfd_mae = bfd_error_stats.get("mae", bfd_metric.get("mae"))
    bfd_p80 = bfd_error_stats.get("absolute_error_p80", bfd_mae)
    bfd_p95 = bfd_error_stats.get("absolute_error_p95", bfd_mae)

    bfd_lower_80 = float(bfd_prediction - bfd_p80) if bfd_prediction is not None and bfd_p80 is not None else None
    bfd_upper_80 = float(bfd_prediction + bfd_p80) if bfd_prediction is not None and bfd_p80 is not None else None
    bfd_lower_95 = float(bfd_prediction - bfd_p95) if bfd_prediction is not None and bfd_p95 is not None else None
    bfd_upper_95 = float(bfd_prediction + bfd_p95) if bfd_prediction is not None and bfd_p95 is not None else None
    bfd_upper = bfd_upper_95 if bfd_upper_95 is not None else conservative_upper_prediction(bfd_prediction, bfd_mae)

    perforation_error = (
        metrics.get("perforated", {})
        .get("probability_error_estimates", {})
        .get("probability_mae")
    )
    fail_error = (
        metrics.get("pass_fail", {})
        .get("probability_error_estimates", {})
        .get("probability_mae")
    )

    recommendation = make_recommendation(
        bfd_upper=bfd_upper,
        perforation_prob=perforation_probability,
        fail_prob=fail_probability,
    )

    confidence_note = (
        "Error bands are calibrated from the current train/test split residuals. "
        "They are useful for screening confidence, not a certification-grade uncertainty bound."
    )

    return PredictionResponse(
        predicted_backface_deformation_mm=bfd_prediction,
        estimated_backface_absolute_error_mm=bfd_mae,
        backface_prediction_lower_80_mm=bfd_lower_80,
        backface_prediction_upper_80_mm=bfd_upper_80,
        backface_prediction_lower_95_mm=bfd_lower_95,
        backface_prediction_upper_95_mm=bfd_upper_95,
        conservative_backface_deformation_upper_mm=bfd_upper,
        perforation_probability=perforation_probability,
        perforation_probability_estimated_error=perforation_error,
        fail_probability=fail_probability,
        fail_probability_estimated_error=fail_error,
        recommendation=recommendation,
        confidence_note=confidence_note,
        warning=(
            "Screening model only. Do not use as a replacement for physical "
            "ballistic testing, certification, or safety approval."
        ),
    )


@app.get("/metrics")
def get_metrics():
    metadata = load_metadata()

    if not metadata:
        raise HTTPException(status_code=404, detail="No trained model metadata found.")

    return metadata


# =============================================================================
# Local run command
# =============================================================================
# Save this file as:
#   Ballistic_Model_Backend.py
#
# Then run:
#   cd "/path/to/your/backend/folder"
#   uvicorn Ballistic_Model_Backend:app --reload
#
# Then open:
#   http://127.0.0.1:8000/docs
# =============================================================================