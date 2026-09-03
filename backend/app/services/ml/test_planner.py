"""
Test Planner: Recommends which vest configurations to physically test next.

Uses the trained model's prediction uncertainty, feature-space distance to
existing training data, and data density gaps to rank candidate configurations
by their expected information value.
"""
import os
import sys
import json
import itertools
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from sqlalchemy.orm import Session


def _ensure_backend_path():
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


def _get_existing_vest_configs(db: Session) -> List[Dict]:
    """Fetch all existing tested vest configurations from the database."""
    from app.db.models import Vest, VestLayer, Material

    vests = db.query(Vest).all()
    result = []
    for vest in vests:
        layers = db.query(VestLayer).filter(VestLayer.vest_id == vest.id).order_by(VestLayer.layer_index).all()
        if not layers:
            continue
        composition_parts = []
        layer_info = []
        for layer in layers:
            material = db.query(Material).filter(Material.id == layer.material_id).first()
            if material:
                count = layer.layer_count or 1
                composition_parts.append(f"{count} {material.name}")
                layer_info.append({
                    "material_id": str(material.id),
                    "material_name": material.name,
                    "material_class": material.material_class,
                    "layer_count": count,
                    "layer_index": layer.layer_index,
                })
        if not composition_parts:
            continue
        result.append({
            "vest_id": str(vest.id),
            "vest_code": vest.vest_code,
            "vest_type": vest.vest_type,
            "is_female": vest.is_female if vest.is_female else False,
            "threat_level": vest.threat_level,
            "total_layers": vest.total_layers or sum(l["layer_count"] for l in layer_info),
            "composition": " + ".join(composition_parts),
            "layers": layer_info,
        })
    return result


def _get_available_materials(db: Session) -> List[Dict]:
    """Fetch all materials from the database."""
    from app.db.models import Material

    materials = db.query(Material).all()
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "material_class": m.material_class,
            "areal_density_g_m2": float(m.areal_density_g_m2) if m.areal_density_g_m2 else None,
            "thickness_mm": float(m.thickness_mm) if m.thickness_mm else None,
            "density_g_cm3": float(m.density_g_cm3) if m.density_g_cm3 else None,
        }
        for m in materials
    ]


def _generate_material_swap_variants(
    existing_configs: List[Dict],
    available_materials: List[Dict],
    max_variants: int = 200,
) -> List[Dict]:
    """Generate candidates by swapping one material in existing configs for another of the same class."""
    materials_by_class = defaultdict(list)
    for m in available_materials:
        if m["material_class"]:
            materials_by_class[m["material_class"]].append(m)

    seen_compositions = {c["composition"] for c in existing_configs}
    candidates = []

    for config in existing_configs:
        for i, layer in enumerate(config["layers"]):
            mat_class = layer.get("material_class")
            if not mat_class:
                continue
            same_class_materials = [m for m in materials_by_class.get(mat_class, []) if m["id"] != layer["material_id"]]
            for replacement in same_class_materials:
                new_layers = [dict(l) for l in config["layers"]]
                new_layers[i]["material_id"] = replacement["id"]
                new_layers[i]["material_name"] = replacement["name"]
                new_layers[i]["material_class"] = replacement["material_class"]
                composition_parts = [f"{l['layer_count']} {l['material_name']}" for l in new_layers]
                composition = " + ".join(composition_parts)
                if composition in seen_compositions:
                    continue
                seen_compositions.add(composition)
                candidates.append({
                    "composition": composition,
                    "layers": new_layers,
                    "vest_type": config["vest_type"],
                    "is_female": config["is_female"],
                    "total_layers": sum(l["layer_count"] for l in new_layers),
                    "source": "material_swap",
                    "source_detail": f"Swapped {layer['material_name']} → {replacement['name']} in {config['vest_code']}",
                })
                if len(candidates) >= max_variants:
                    return candidates
    return candidates


def _generate_layer_count_variants(
    existing_configs: List[Dict],
    available_materials: List[Dict],
    max_variants: int = 200,
) -> List[Dict]:
    """Generate candidates by varying layer counts ±20% on existing configs."""
    seen_compositions = {c["composition"] for c in existing_configs}
    candidates = []

    for config in existing_configs:
        total = config["total_layers"]
        if total < 5:
            continue
        # Generate a few variations: -20%, -10%, +10%, +20%
        multipliers = [0.8, 0.9, 1.1, 1.2]
        for mult in multipliers:
            new_total = int(total * mult)
            if new_total == total or new_total < 1:
                continue
            # Scale each layer proportionally
            new_layers = []
            for layer in config["layers"]:
                new_count = max(1, int(layer["layer_count"] * mult))
                new_layers.append({
                    "material_id": layer["material_id"],
                    "material_name": layer["material_name"],
                    "material_class": layer.get("material_class"),
                    "layer_count": new_count,
                    "layer_index": layer["layer_index"],
                })
            composition_parts = [f"{l['layer_count']} {l['material_name']}" for l in new_layers]
            composition = " + ".join(composition_parts)
            if composition in seen_compositions:
                continue
            seen_compositions.add(composition)
            candidates.append({
                "composition": composition,
                "layers": new_layers,
                "vest_type": config["vest_type"],
                "is_female": config["is_female"],
                "total_layers": sum(l["layer_count"] for l in new_layers),
                "source": "layer_count_variation",
                "source_detail": f"Adjusted {config['vest_code']} from {total} → {new_total} layers",
            })
            if len(candidates) >= max_variants:
                return candidates
    return candidates


def _generate_user_constrained_candidates(
    available_materials: List[Dict],
    vest_type: str,
    threat_level: str,
    max_layers: int,
    selected_material_ids: Optional[List[str]] = None,
    max_variants: int = 200,
) -> List[Dict]:
    """Generate candidate configurations from user-specified constraints."""
    if selected_material_ids:
        materials = [m for m in available_materials if m["id"] in selected_material_ids]
    else:
        materials = available_materials

    if len(materials) < 1:
        return []

    # Generate plausible combinations: 1-3 material types, varying counts
    candidates = []
    seen = set()

    # Single-material configs
    for m in materials:
        for count in [10, 20, 30, 40, 50]:
            if count > max_layers:
                break
            comp = f"{count} {m['name']}"
            if comp in seen:
                continue
            seen.add(comp)
            candidates.append({
                "composition": comp,
                "layers": [{
                    "material_id": m["id"],
                    "material_name": m["name"],
                    "material_class": m["material_class"],
                    "layer_count": count,
                    "layer_index": 0,
                }],
                "vest_type": vest_type,
                "is_female": False,
                "total_layers": count,
                "source": "user_constrained",
                "source_detail": f"Single-material: {count} layers of {m['name']}",
            })
            if len(candidates) >= max_variants:
                return candidates

    # Two-material configs
    for m1, m2 in itertools.combinations(materials, 2):
        for c1, c2 in [(30, 10), (20, 20), (40, 5), (10, 30), (35, 15)]:
            total = c1 + c2
            if total > max_layers:
                continue
            comp = f"{c1} {m1['name']} + {c2} {m2['name']}"
            if comp in seen:
                continue
            seen.add(comp)
            candidates.append({
                "composition": comp,
                "layers": [
                    {"material_id": m1["id"], "material_name": m1["name"], "material_class": m1["material_class"], "layer_count": c1, "layer_index": 0},
                    {"material_id": m2["id"], "material_name": m2["name"], "material_class": m2["material_class"], "layer_count": c2, "layer_index": 1},
                ],
                "vest_type": vest_type,
                "is_female": False,
                "total_layers": total,
                "source": "user_constrained",
                "source_detail": f"Two-material: {c1} {m1['name']} + {c2} {m2['name']}",
            })
            if len(candidates) >= max_variants:
                return candidates

    # Three-material configs (limited)
    for m1, m2, m3 in itertools.combinations(materials, 3):
        for c1, c2, c3 in [(30, 10, 5), (20, 15, 10), (25, 10, 10)]:
            total = c1 + c2 + c3
            if total > max_layers:
                continue
            comp = f"{c1} {m1['name']} + {c2} {m2['name']} + {c3} {m3['name']}"
            if comp in seen:
                continue
            seen.add(comp)
            candidates.append({
                "composition": comp,
                "layers": [
                    {"material_id": m1["id"], "material_name": m1["name"], "material_class": m1["material_class"], "layer_count": c1, "layer_index": 0},
                    {"material_id": m2["id"], "material_name": m2["name"], "material_class": m2["material_class"], "layer_count": c2, "layer_index": 1},
                    {"material_id": m3["id"], "material_name": m3["name"], "material_class": m3["material_class"], "layer_count": c3, "layer_index": 2},
                ],
                "vest_type": vest_type,
                "is_female": False,
                "total_layers": total,
                "source": "user_constrained",
                "source_detail": f"Three-material: {c1} {m1['name']} + {c2} {m2['name']} + {c3} {m3['name']}",
            })
            if len(candidates) >= max_variants:
                return candidates

    return candidates


def _fast_predict_candidate(
    candidate: Dict,
    model_data: Dict,
    protocol: Dict,
    material_properties: Dict,
    db: Session,
    ammo_cache: Optional[Dict] = None,
    material_name_cache: Optional[Dict] = None,
) -> Optional[Dict]:
    """
    Fast lightweight prediction for scoring — predicts only 1 shot per ammo
    at target velocity (front/dry) instead of all 288 protocol shots.

    Args:
        candidate: candidate vest config dict
        model_data: preloaded model dict with model, scaler, feature_columns, etc.
        protocol: preloaded protocol dict with levels_config
        material_properties: preloaded material properties dict
        db: database session
        ammo_cache: preloaded ammunition objects keyed by ammo_id
        material_name_cache: preloaded material names keyed by material_id
    """
    from app.services.ml.ballistic_ml import add_engineered_features, prepare_single_input, check_extrapolation
    from app.db.models import Material, Ammunition

    model = model_data['model']
    perforation_model = model_data.get('perforation_model')
    scaler = model_data['scaler']
    feature_columns = model_data['feature_columns']
    use_log_transform = model_data.get('use_log_transform', False)
    training_ranges = model_data.get('training_ranges', {})

    # Build vest composition string using cache
    composition_parts = []
    for layer in candidate["layers"]:
        mid = layer["material_id"]
        if material_name_cache and mid in material_name_cache:
            name = material_name_cache[mid]
        else:
            material = db.query(Material).filter(Material.id == mid).first()
            name = material.name if material else None
        if name:
            composition_parts.append(f"{layer['layer_count']} {name}")
    vest_composition = " + ".join(composition_parts) if composition_parts else ""

    predictions = []
    for level in protocol.get("levels_config", []):
        level_name = level.get("level_name", "Unknown")
        for ammo_config in level.get("ammunition_config", []):
            ammo_id = ammo_config.get("ammunition_id")
            reference_velocity = ammo_config.get("reference_velocity_m_s", 400)
            if ammo_cache and ammo_id in ammo_cache:
                ammo = ammo_cache[ammo_id]
            else:
                ammo = db.query(Ammunition).filter(Ammunition.id == ammo_id).first()
            if not ammo:
                continue

            # Single representative shot: front, dry, target velocity, shot 1
            features = {
                'vest_composition': vest_composition,
                'number_of_layers': int(candidate["total_layers"]),
                'ammunition_used': ammo.name if ammo.name else ammo.caliber,
                'threat_level': level_name,
                'shot_number': 1,
                'impact_velocity_mps': reference_velocity,
                'impact_angle_deg': 0.0,
                'bullet_mass_g': float(ammo.projectile_mass_grams) if ammo.projectile_mass_grams else 0,
                'temperature_c': 20.0,
                'humidity_pct': 50.0,
                'condition': 'dry',
                'panel_side': 'front',
                'caliber_diameter_mm': float(ammo.caliber_diameter_mm) if ammo.caliber_diameter_mm else None,
                'caliber_length_mm': float(ammo.caliber_length_mm) if ammo.caliber_length_mm else None,
                'vest_type': candidate.get("vest_type", "soft"),
                'is_female': candidate.get("is_female", False),
                'ply_orientations': None,
            }

            try:
                import pandas as pd
                df = prepare_single_input(features, material_properties, validate=False)

                missing_cols = [c for c in feature_columns if c not in df.columns]
                if missing_cols:
                    df = pd.concat([df, pd.DataFrame(0, index=df.index, columns=missing_cols)], axis=1)

                df = df[feature_columns]
                features_scaled = scaler.transform(df)

                prediction = model.predict(features_scaled)[0]
                if use_log_transform:
                    prediction = float(np.expm1(prediction))

                perforation_probability = None
                if perforation_model:
                    perforation_probability = float(perforation_model.predict_proba(features_scaled)[0, 1])

                extrap_result = check_extrapolation(df, training_ranges)

                predictions.append({
                    'predicted_bfd_mm': float(prediction),
                    'perforation_probability': perforation_probability,
                    'ammunition_name': ammo.name if ammo.name else ammo.caliber,
                    'level_name': level_name,
                    'extrapolation_warning': extrap_result['is_extrapolated'],
                    'out_of_range_features': extrap_result['out_of_range_features'],
                })
            except Exception:
                continue

    if not predictions:
        return None

    bfd_values = [p['predicted_bfd_mm'] for p in predictions if p['predicted_bfd_mm'] is not None]
    if not bfd_values:
        return None

    return {
        'predictions': predictions,
        'summary': {
            'mean_bfd_mm': float(np.mean(bfd_values)),
            'max_bfd_mm': float(np.max(bfd_values)),
            'min_bfd_mm': float(np.min(bfd_values)),
        },
    }


def _compute_feature_space_distance(
    candidate: Dict,
    db: Session,
    preprocessor,
    feature_columns: List[str],
    training_features_cache: Optional[np.ndarray] = None,
    material_properties_cache: Optional[Dict] = None,
) -> float:
    """Compute distance from candidate to nearest training data point in feature space."""
    from app.services.ml.ballistic_ml import add_engineered_features, fetch_material_properties

    material_properties = material_properties_cache if material_properties_cache is not None else fetch_material_properties(db)

    # Build feature row for the candidate
    features = {
        "vest_composition": candidate["composition"],
        "number_of_layers": candidate["total_layers"],
        "ammunition_used": "unknown",
        "threat_level": None,
        "shot_number": 1,
        "impact_velocity_mps": 400,
        "impact_angle_deg": 0.0,
        "bullet_mass_g": 8.0,
        "temperature_c": 22.0,
        "humidity_pct": 50.0,
        "condition": "dry",
        "panel_side": "front",
        "vest_type": candidate.get("vest_type", "soft"),
        "is_female": candidate.get("is_female", False),
        "ply_orientations": None,
    }

    try:
        import pandas as pd
        from app.services.ml.ballistic_ml import prepare_single_input
        df = prepare_single_input(features, material_properties, validate=False)

        missing_cols = [c for c in feature_columns if c not in df.columns]
        if missing_cols:
            df = pd.concat([df, pd.DataFrame(0, index=df.index, columns=missing_cols)], axis=1)

        df = df[feature_columns]
        candidate_transformed = preprocessor.transform(df)

        if training_features_cache is not None and len(training_features_cache) > 0:
            distances = np.linalg.norm(training_features_cache - candidate_transformed, axis=1)
            return float(np.min(distances))
        return 0.0
    except Exception:
        return 0.0


def _get_training_features_cache(db: Session, preprocessor, feature_columns: List[str]) -> Optional[np.ndarray]:
    """Build a cache of transformed training features for distance computation."""
    from app.services.ml.data_fetcher import fetch_training_data, fetch_material_properties
    from app.services.ml.ballistic_ml import add_engineered_features

    try:
        df, _, _ = fetch_training_data(db, ignore_anchor_points=True)
        if df.empty:
            return None

        material_properties = fetch_material_properties(db)
        df_features = add_engineered_features(df, material_properties, validate=False)

        categorical_feature_names = {
            "vest_composition", "ammunition_used", "threat_level", "condition",
            "panel_side", "weave_type", "material_type", "vest_type", "ply_orientations",
            "geometry_name", "primary_weave_type",
            "composition_sequence", "composition_first_material",
            "composition_second_material", "composition_penultimate_material",
            "composition_last_material",
        }
        for mat_name in material_properties:
            prefix = mat_name.lower().replace(" ", "_").replace("-", "_")
            categorical_feature_names.add(f"composition_material_class_{prefix}")

        if feature_columns:
            for col in feature_columns:
                if col not in df_features.columns:
                    if col in categorical_feature_names:
                        df_features[col] = "unknown"
                    else:
                        df_features[col] = np.nan
            df_features = df_features[feature_columns]

        for col in df_features.columns:
            if col in categorical_feature_names:
                df_features[col] = df_features[col].fillna("unknown").astype(str)

        from app.services.ml.ballistic_ml import fill_missing_features
        df_features = fill_missing_features(df_features)

        transformed = preprocessor.transform(df_features)
        return transformed
    except Exception:
        return None


def _count_comparable_training_shots(
    candidate: Dict,
    db: Session,
    protocol_id: str,
) -> int:
    """Count training shots with similar material composition and threat level."""
    from app.db.models import ShotData, Vest, VestLayer, Material
    from app.db.models.protocol import Protocol as ProtocolModel

    # Get the protocol's threat levels
    protocol = db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
    if not protocol or not protocol.levels_config:
        return 0

    threat_levels = set()
    for level in protocol.levels_config:
        ln = level.get("level_name")
        if ln:
            threat_levels.add(ln)

    # Get material IDs in the candidate
    candidate_material_ids = {l["material_id"] for l in candidate["layers"]}

    # Find vests that share at least one material
    vests_with_matching_material = db.query(Vest.id).join(VestLayer, VestLayer.vest_id == Vest.id).filter(
        VestLayer.material_id.in_(list(candidate_material_ids))
    ).distinct().all()
    vest_ids = [v[0] for v in vests_with_matching_material]

    if not vest_ids:
        return 0

    # Count shots for those vests (ShotData links to vest via TestSession.vest_id)
    from app.db.models.test_session import TestSession
    shot_count = db.query(ShotData).join(
        TestSession, ShotData.test_session_id == TestSession.id
    ).filter(
        TestSession.vest_id.in_(vest_ids)
    ).count()

    return shot_count


def recommend_tests(
    db: Session,
    protocol_id: str,
    version: Optional[str] = None,
    selected_material_ids: Optional[List[str]] = None,
    vest_type: Optional[str] = None,
    threat_level: Optional[str] = None,
    max_layers: int = 60,
    max_candidates: int = 50,
    include_swap_variants: bool = True,
    include_layer_variants: bool = True,
    include_user_constrained: bool = True,
) -> Dict[str, Any]:
    """
    Generate and rank test recommendations.

    Returns a dict with:
        - recommendations: sorted list of candidate configs with scores
        - summary: stats about the candidate pool
    """
    _ensure_backend_path()

    from app.services.ml.ballistic_ml import load_metadata, load_preprocessor

    # Load model metadata
    metadata = load_metadata()
    if not metadata:
        raise ValueError("No trained model found. Train a model first.")

    feature_columns = metadata.get("feature_columns", [])
    preprocessor = load_preprocessor(db)
    if preprocessor is None:
        raise ValueError("Preprocessor not found. Retrain the model.")

    # Fetch existing configs and available materials
    all_existing_configs = _get_existing_vest_configs(db)
    available_materials = _get_available_materials(db)

    if not available_materials:
        raise ValueError("No materials found in database.")

    # Filter existing configs by user-selected vest type for swap/layer variants
    existing_configs = [
        c for c in all_existing_configs
        if (c.get("vest_type") or "soft").lower() == (vest_type or "soft").lower()
    ]

    # Generate candidates
    candidates = []

    if include_swap_variants and existing_configs:
        candidates.extend(_generate_material_swap_variants(existing_configs, available_materials))

    if include_layer_variants and existing_configs:
        candidates.extend(_generate_layer_count_variants(existing_configs, available_materials))

    if include_user_constrained:
        candidates.extend(_generate_user_constrained_candidates(
            available_materials,
            vest_type=vest_type or "soft",
            threat_level=threat_level or "",
            max_layers=max_layers,
            selected_material_ids=selected_material_ids,
        ))

    # Deduplicate by composition
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c["composition"] not in seen:
            seen.add(c["composition"])
            unique_candidates.append(c)

    # Limit pool size for performance — keep it small since each prediction is expensive
    unique_candidates = unique_candidates[:max_candidates * 2]

    # Build training feature cache for distance computation
    training_cache = _get_training_features_cache(db, preprocessor, feature_columns)

    # Cache material properties once (used by _compute_feature_space_distance)
    from app.services.ml.ballistic_ml import fetch_material_properties
    material_properties_cache = fetch_material_properties(db)

    # Precompute median pairwise distance from training cache (used for normalization)
    median_dist = 1.0
    if training_cache is not None and len(training_cache) > 1:
        n = min(100, len(training_cache))
        sample = training_cache[:n]
        pairwise = []
        for i in range(n):
            for j in range(i + 1, n):
                pairwise.append(np.linalg.norm(sample[i] - sample[j]))
        median_dist = np.median(pairwise) if pairwise else 1.0

    # Precompute CI width from metadata (same for all candidates)
    metrics = metadata.get("metrics", {})
    bfd_metric = metrics.get("backface_deformation_mm_regression", {})
    bfd_p95 = bfd_metric.get("absolute_error_p95") if isinstance(bfd_metric, dict) else None
    bfd_mae = bfd_metric.get("mae") if isinstance(bfd_metric, dict) else None
    ci_width = (bfd_p95 or bfd_mae or 5.0) * 2

    # Preload model ONCE from disk (avoids per-candidate disk reads)
    _ensure_backend_path()
    from ml.prediction_service import PredictionService
    _tmp_service = PredictionService(db)
    model_data = _tmp_service.load_model(version)
    if not model_data:
        raise ValueError("No trained model found. Train a model first.")

    # Preload protocol ONCE
    from app.db.models.protocol import Protocol as ProtocolModel
    protocol = db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
    if not protocol:
        raise ValueError(f"Protocol with id {protocol_id} not found")
    protocol_dict = {
        "id": str(protocol.id),
        "name": protocol.name,
        "levels_config": protocol.levels_config or [],
    }

    # Preload ammunition for this protocol into a cache to avoid per-candidate DB queries
    from app.db.models import Ammunition
    ammo_cache = {}
    for level in protocol_dict["levels_config"]:
        for ammo_config in level.get("ammunition_config", []):
            ammo_id = ammo_config.get("ammunition_id")
            if ammo_id and ammo_id not in ammo_cache:
                ammo = db.query(Ammunition).filter(Ammunition.id == ammo_id).first()
                if ammo:
                    ammo_cache[ammo_id] = ammo

    # Preload material names for composition building
    from app.db.models import Material
    material_name_cache = {}
    for c in unique_candidates:
        for layer in c["layers"]:
            mid = layer["material_id"]
            if mid not in material_name_cache:
                mat = db.query(Material).filter(Material.id == mid).first()
                material_name_cache[mid] = mat.name if mat else "Unknown"

    # Score each candidate
    scored = []
    print(f"[TestPlanner] Scoring {len(unique_candidates)} candidates...")
    for i, candidate in enumerate(unique_candidates):
        if (i + 1) % 10 == 0:
            print(f"[TestPlanner]   {i + 1}/{len(unique_candidates)} scored")
        prediction = _fast_predict_candidate(
            candidate, model_data, protocol_dict, material_properties_cache, db,
            ammo_cache, material_name_cache
        )
        if not prediction or not prediction.get("predictions"):
            continue

        # Extract prediction stats
        bfd_values = [p["predicted_bfd_mm"] for p in prediction["predictions"] if p.get("predicted_bfd_mm") is not None]
        if not bfd_values:
            continue

        mean_bfd = float(np.mean(bfd_values))
        max_bfd = float(np.max(bfd_values))
        min_bfd = float(np.min(bfd_values))

        # Perforation probabilities
        perf_probs = [p.get("perforation_probability") for p in prediction["predictions"] if p.get("perforation_probability") is not None]
        max_perf_prob = max(perf_probs) if perf_probs else 0.0

        # Extrapolation warnings
        all_out_of_range = set()
        for p in prediction["predictions"]:
            for feat in p.get("out_of_range_features", []):
                all_out_of_range.add(feat)
        is_extrapolated = len(all_out_of_range) > 0

        # Feature space distance
        distance = _compute_feature_space_distance(
            candidate, db, preprocessor, feature_columns, training_cache, material_properties_cache
        )

        # Comparable shot count
        comparable_count = _count_comparable_training_shots(candidate, db, protocol_id)

        # Boundary proximity: how close is max BFD to the 44mm NIJ limit
        boundary_proximity = 1.0 - abs(max_bfd - 44.0) / 44.0
        boundary_proximity = max(0.0, min(1.0, boundary_proximity))

        # Normalize scores to 0-1 range
        # Uncertainty: wider CI = more uncertain = higher value
        uncertainty_score = min(ci_width / 20.0, 1.0)  # 20mm CI → max score

        # Distance: normalize by precomputed median distance
        distance_score = min(distance / (median_dist * 2), 1.0) if median_dist > 0 else 0.5

        # Sparsity: fewer comparable shots = higher value
        sparsity_score = 1.0 / (1.0 + comparable_count * 0.1)

        # Practical relevance: near pass/fail boundary
        practical_score = boundary_proximity

        # Penalize if perforation probability is very high (test would just confirm perforation)
        if max_perf_prob > 0.9:
            practical_score *= 0.3

        # Composite score
        composite = (
            0.40 * uncertainty_score +
            0.30 * distance_score +
            0.20 * sparsity_score +
            0.10 * practical_score
        )

        # Build reason explanation
        reasons = []
        if uncertainty_score > 0.5:
            reasons.append(f"High prediction uncertainty (CI ±{ci_width/2:.1f}mm)")
        if distance_score > 0.5:
            reasons.append(f"Far from training data (distance {distance:.2f})")
        if sparsity_score > 0.7:
            reasons.append(f"Very few comparable training shots ({comparable_count})")
        if practical_score > 0.6:
            reasons.append(f"Near pass/fail boundary (predicted max BFD {max_bfd:.1f}mm vs 44mm limit)")
        if max_perf_prob > 0.9:
            reasons.append("Note: high perforation probability — test may just confirm perforation")
        if is_extrapolated:
            reasons.append(f"Out of training range: {', '.join(sorted(all_out_of_range)[:5])}")
        if not reasons:
            reasons.append("Moderate information value across all factors")

        scored.append({
            "composition": candidate["composition"],
            "vest_type": candidate.get("vest_type", "soft"),
            "total_layers": candidate["total_layers"],
            "source": candidate["source"],
            "source_detail": candidate["source_detail"],
            "predicted_mean_bfd_mm": round(mean_bfd, 2),
            "predicted_max_bfd_mm": round(max_bfd, 2),
            "predicted_min_bfd_mm": round(min_bfd, 2),
            "max_perforation_probability": round(max_perf_prob, 3),
            "extrapolation_warning": is_extrapolated,
            "out_of_range_features": sorted(all_out_of_range),
            "ci_width_mm": round(ci_width, 2),
            "feature_space_distance": round(distance, 3),
            "comparable_training_shots": comparable_count,
            "scores": {
                "uncertainty": round(uncertainty_score, 3),
                "distance": round(distance_score, 3),
                "sparsity": round(sparsity_score, 3),
                "practical": round(practical_score, 3),
                "composite": round(composite, 3),
            },
            "reason": "; ".join(reasons),
            "layers": candidate["layers"],
            "prediction_summary": prediction.get("summary", {}),
        })

    # Sort by composite score
    scored.sort(key=lambda x: x["scores"]["composite"], reverse=True)

    # Trim to requested count
    top_recommendations = scored[:max_candidates]

    return {
        "recommendations": top_recommendations,
        "summary": {
            "total_candidates_generated": len(unique_candidates),
            "total_candidates_scored": len(scored),
            "returned": len(top_recommendations),
            "model_version": metadata.get("version", "unknown"),
            "protocol_id": protocol_id,
        },
    }
