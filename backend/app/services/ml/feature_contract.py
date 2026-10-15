"""
Versioned feature contract for the ballistic BFD model.

A single code path builds model features for both training and inference.
The contract version is recorded with every trained artifact and every
simulation run so results are reproducible.

- v0_legacy:    reproduces the historical pipeline exactly (including the
                density-based areal-density bug) so existing artifacts like
                NPOptimized-6 replay faithfully.
- v1_corrected: grammage-based segment areal density (count * g/m2 / 1000),
                full categorical default set, and batch-invariant handling.

Missing-value policy: categorical gaps become the literal 'unknown'; numeric
gaps are left as NaN so the FITTED SimpleImputer inside the saved
preprocessor fills them with training statistics. No batch statistics are
ever computed at inference time.
"""
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd

from app.services.ml.ballistic_ml import add_engineered_features

CONTRACT_V0 = "v0_legacy"
CONTRACT_V1 = "v1_corrected"
SUPPORTED_CONTRACTS = (CONTRACT_V0, CONTRACT_V1)

# Canonical categorical feature names. This is the union the training path
# (train_from_dataframe) recognizes; the legacy single-input inference path
# omitted the composition sequence/name columns, which is the parity bug this
# contract fixes.
CATEGORICAL_BASE_FEATURES: Set[str] = {
    "vest_composition",
    "ammunition_used",
    "threat_level",
    "condition",
    "panel_side",
    "weave_type",
    "material_type",
    "vest_type",
    "ply_orientations",
    "geometry_name",
    "primary_weave_type",
    "composition_sequence",
    "composition_first_material",
    "composition_second_material",
    "composition_penultimate_material",
    "composition_last_material",
}


def material_prefix(material_name: str) -> str:
    return material_name.lower().replace(" ", "_").replace("-", "_")


def categorical_feature_names(material_properties: Dict[str, Dict[str, Any]]) -> Set[str]:
    names = set(CATEGORICAL_BASE_FEATURES)
    for material in material_properties:
        names.add(f"composition_material_class_{material_prefix(material)}")
    return names


def build_composition_features_v1(
    composition: Any,
    material_properties: Dict[str, Dict[str, float]],
    validate: bool = True,
) -> Dict[str, Any]:
    """Corrected composition features.

    Segment areal density uses the recorded grammage directly
    (count * areal_density_g_m2 / 1000 -> kg/m2) instead of
    count * thickness_mm * density_g_cm3, which silently produced 0 because
    no material has volumetric density populated.
    """
    from app.services.ml.ballistic_ml import (
        normalize_composition_text,
        identify_material_name,
    )
    import re

    text = normalize_composition_text(composition)
    if not text:
        segments = []
    else:
        parts = [p.strip() for p in re.split(r"\s*\+\s*", text) if p.strip()]
        segments = []
        for position, part in enumerate(parts, start=1):
            match = re.match(r"^(?:(\d+(?:\.\d+)?)\s*)?(.*)$", part)
            if match is None:
                continue
            count_text, raw_name = match.groups()
            count = float(count_text) if count_text else 1.0
            material = identify_material_name(raw_name, material_properties)
            properties = material_properties.get(material, {})
            thickness_mm = float(properties.get("thickness_mm", 0.0) or 0.0)
            grammage = float(properties.get("areal_density_g_m2", 0.0) or 0.0)
            segments.append({
                "position": position,
                "material": material,
                "count": count,
                "thickness_mm": thickness_mm,
                "segment_thickness_mm": count * thickness_mm,
                # corrected: derive kg/m2 from measured grammage
                "segment_areal_density_kg_m2": count * grammage / 1000.0,
            })

    from fastapi import HTTPException
    unknown_materials = [s["material"] for s in segments if s["material"] == "UNKNOWN_MATERIAL"]
    if validate and unknown_materials and segments:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown material(s) found in vest composition: {', '.join(unknown_materials)}. "
                   f"Available materials: {', '.join(material_properties.keys())}"
        )

    # Build the same feature dict shape as build_composition_features.
    features: Dict[str, Any] = {}
    for material in material_properties:
        prefix = material_prefix(material)
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

    empty = {
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
    }
    if not segments:
        features.update(empty)
        return features

    total_segments = len(segments)
    unknown_segment_count = sum(1 for s in segments if s["material"] == "UNKNOWN_MATERIAL")
    unknown_item_count = sum(s["count"] for s in segments if s["material"] == "UNKNOWN_MATERIAL")
    total_count = sum(s["count"] for s in segments)
    total_thickness = sum(s["segment_thickness_mm"] for s in segments)
    total_areal_density = sum(s["segment_areal_density_kg_m2"] for s in segments)
    # effective stack density: total areal density (kg/m2) / thickness (mm)
    weighted_density = total_areal_density / total_thickness if total_thickness else 0.0

    weighted_tensile_strength = 0.0
    weighted_modulus = 0.0
    weighted_elongation_percent = 0.0
    weighted_force_longitudinal = 0.0
    weighted_force_transverse = 0.0
    total_force_longitudinal = 0.0
    total_force_transverse = 0.0
    total_weight = 0.0

    sequence = [s["material"] for s in segments]
    transitions = sum(1 for l, r in zip(sequence, sequence[1:]) if l != r)

    front_cutoff = total_thickness / 2.0
    running_thickness = 0.0
    front_areal_density = 0.0
    front_thickness = 0.0
    back_areal_density = 0.0
    back_thickness = 0.0

    for segment in segments:
        material = segment["material"]
        if material in material_properties:
            prefix = material_prefix(material)
            features[f"composition_count_{prefix}"] += segment["count"]
            features[f"composition_thickness_mm_{prefix}"] += segment["segment_thickness_mm"]
            features[f"composition_areal_density_kg_m2_{prefix}"] += segment["segment_areal_density_kg_m2"]
            features[f"composition_ply_count_{prefix}"] = (
                material_properties[material].get("ply_count", 0) or 0
            ) * segment["count"]
            features[f"composition_material_class_{prefix}"] = material_properties[material].get("material_class", "unknown")
            features[f"composition_elongation_longitudinal_percent_{prefix}"] = material_properties[material].get("elongation_longitudinal_percent", 0.0)
            features[f"composition_elongation_longitudinal_error_percent_{prefix}"] = material_properties[material].get("elongation_longitudinal_error_percent", 0.0)
            features[f"composition_elongation_transverse_percent_{prefix}"] = material_properties[material].get("elongation_transverse_percent", 0.0)
            features[f"composition_elongation_transverse_error_percent_{prefix}"] = material_properties[material].get("elongation_transverse_error_percent", 0.0)
            if segment["position"] == 1:
                features[f"composition_first_position_{prefix}"] = 1.0
            if segment["position"] == total_segments:
                features[f"composition_last_position_{prefix}"] = 1.0

            props = material_properties[material]
            weight = segment["segment_thickness_mm"] if total_thickness > 0 else 0
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
                # total stack break force: per-ply force scales with ply count
                total_force_longitudinal += props["force_longitudinal_n_per_cm"] * segment["count"]
            if "force_transverse_n_per_cm" in props:
                weighted_force_transverse += props["force_transverse_n_per_cm"] * weight
                total_force_transverse += props["force_transverse_n_per_cm"] * segment["count"]

        running_thickness += segment["segment_thickness_mm"]
        if running_thickness <= front_cutoff:
            front_areal_density += segment["segment_areal_density_kg_m2"]
            front_thickness += segment["segment_thickness_mm"]
        else:
            back_areal_density += segment["segment_areal_density_kg_m2"]
            back_thickness += segment["segment_thickness_mm"]

    if total_weight > 0:
        weighted_tensile_strength /= total_weight
        weighted_modulus /= total_weight
        weighted_elongation_percent /= total_weight
        weighted_force_longitudinal /= total_weight
        weighted_force_transverse /= total_weight

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
        "composition_total_force_longitudinal_n": total_force_longitudinal,
        "composition_total_force_transverse_n": total_force_transverse,
        "composition_unique_material_count": len(set(sequence)),
        "composition_sequence": ">".join(sequence),
        "composition_first_material": sequence[0],
        "composition_second_material": sequence[1] if len(sequence) > 1 else "none",
        "composition_penultimate_material": sequence[-2] if len(sequence) > 1 else "none",
        "composition_last_material": sequence[-1],
    })
    return features


def add_composition_features_v1(
    df: pd.DataFrame,
    material_properties: Dict[str, Dict[str, float]],
    validate: bool = False,
) -> pd.DataFrame:
    if "vest_composition" not in df.columns:
        return df
    composition_features = pd.DataFrame(
        [build_composition_features_v1(v, material_properties, validate=validate) for v in df["vest_composition"]],
        index=df.index,
    )
    return pd.concat([df, composition_features], axis=1)


def build_features(
    df: pd.DataFrame,
    material_properties: Dict[str, Dict[str, float]],
    feature_toggles: Optional[Dict[str, bool]] = None,
    contract_version: str = CONTRACT_V0,
    validate: bool = False,
) -> pd.DataFrame:
    """Engineered features under the requested contract."""
    if contract_version not in SUPPORTED_CONTRACTS:
        raise ValueError(f"Unsupported feature contract: {contract_version}")

    if contract_version == CONTRACT_V0:
        return add_engineered_features(
            df, material_properties, validate=validate, feature_toggles=feature_toggles
        )

    # v1: corrected composition features, then the rest of the engineering
    # pipeline (which keys off the composition_* columns it produces).
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = add_composition_features_v1(df, material_properties, validate=validate)
    # Reuse the remaining engineering from the legacy pipeline by calling it
    # with composition features already present; add_composition_features is
    # idempotent-skipped here because the composition_* columns now exist, so
    # we recompute them via the corrected path only.
    from app.services.ml import ballistic_ml
    original = ballistic_ml.add_composition_features
    try:
        ballistic_ml.add_composition_features = lambda d, mp, validate=False: d
        out = ballistic_ml.add_engineered_features(
            df, material_properties, validate=validate, feature_toggles=feature_toggles
        )
    finally:
        ballistic_ml.add_composition_features = original
    return out


def align_to_contract(
    df: pd.DataFrame,
    feature_columns: List[str],
    categorical_names: Set[str],
) -> pd.DataFrame:
    """Align an engineered frame to the artifact's feature contract.

    Adds missing columns (categorical -> 'unknown', numeric -> NaN), selects
    contract order, and fills categoricals/bools. Numeric NaN is preserved so
    the fitted preprocessor imputes with training statistics — a row's
    features never depend on which other rows share its batch.
    """
    df = df.copy()
    for col in feature_columns:
        if col not in df.columns:
            df[col] = "unknown" if col in categorical_names else np.nan
    df = df[feature_columns]
    for col in df.columns:
        if col in categorical_names:
            df[col] = df[col].fillna("unknown").astype(str)
    bool_cols = df.select_dtypes(include=["bool"]).columns
    for col in bool_cols:
        df[col] = df[col].fillna(False).astype(int)
    return df
