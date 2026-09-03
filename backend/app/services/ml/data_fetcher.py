"""
Data fetcher for ML training - pulls training data from database.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import pandas as pd

from app.db.models import ShotData, Vest, VestLayer, Material, TestSession, Ammunition, AnchorPoint, AnchorPointLayer
from app.db.models.geometry import Geometry


def extract_ply_orientations(layers: List[Dict[str, Any]]) -> str:
    """Extract ply orientation information from material layers."""
    orientations = []
    for layer in layers:
        material = layer['material']
        if material and material.ply_orientations:
            # ply_orientations is a JSONB array of orientations
            if isinstance(material.ply_orientations, list):
                orientations.extend([str(o) for o in material.ply_orientations])
            elif isinstance(material.ply_orientations, str):
                orientations.append(material.ply_orientations)
    return ", ".join(orientations) if orientations else None


def fetch_training_data(db: Session, verbose: bool = True, ignore_anchor_points: bool = False) -> tuple[pd.DataFrame, list[str], dict]:
    """
    Fetch all training data from database for ML model training.
    
    Uses ShotData table (the real test data) instead of Shot table.
    
    More lenient approach: uses available material properties even if some relationships are missing.
    This allows training on more data points.
    
    Returns a DataFrame with columns matching the training CSV format:
    - vest_composition: string like "40 SOFT3000 + 2 UD245 + 1 PE Espumado" (if available)
    - material_thickness_mm: calculated from vest layers or from material properties (if available)
    - material_weight_g_m2: calculated from vest layers or from material properties (if available)
    - number_of_layers: total layers from vest or from composition (if available)
    - ammunition_used: ammunition name or caliber
    - threat_level: from test session or vest or shot data
    - shot_number: shot number
    - impact_velocity_mps: measured velocity
    - impact_angle_deg: impact angle
    - bullet_mass_g: projectile mass
    - temperature_c: ambient temperature
    - humidity_pct: humidity
    - condition: conditioning
    - panel_side: from shot or test session
    - backface_deformation_mm: bfd_mm
    - perforated: penetration boolean
    - pass_fail: pass_fail string
    - material_type: material class/type (aramid, UHMWPE, etc.) if available
    """
    warnings_list = []
    
    # Normalize protection levels
    def normalize_protection_level(level: str) -> str:
        if not level:
            return level
        level_upper = level.upper().strip()
        # Map ARG_RB4 to RB4
        if level_upper == 'ARG_RB4':
            return 'RB4'
        return level

    # Check material properties and warn about missing data
    materials = db.query(Material).all()
    missing_thickness = []
    missing_density = []
    missing_ply = []

    for material in materials:
        if not material.thickness_mm:
            missing_thickness.append(material.name)
        if not material.areal_density_g_m2:
            missing_density.append(material.name)
        if not material.ply_count:
            missing_ply.append(material.name)

    if verbose:
        if missing_thickness:
            msg = f"{len(missing_thickness)} materials missing thickness: {', '.join(missing_thickness[:10])}{'...' if len(missing_thickness) > 10 else ''}"
            warnings_list.append(msg)
        if missing_density:
            msg = f"{len(missing_density)} materials missing areal density (g/m²): {', '.join(missing_density[:10])}{'...' if len(missing_density) > 10 else ''}"
            warnings_list.append(msg)
        if missing_ply:
            msg = f"{len(missing_ply)} materials missing ply count: {', '.join(missing_ply[:10])}{'...' if len(missing_ply) > 10 else ''}"
            warnings_list.append(msg)

    # Query all shot data with relationships - less restrictive
    query = (
        db.query(ShotData, TestSession, Vest)
        .outerjoin(TestSession, ShotData.test_session_id == TestSession.id)
        .outerjoin(Vest, TestSession.vest_id == Vest.id)
        .all()
    )

    if not query:
        return pd.DataFrame(), warnings_list
    
    # Batch fetch all related data to avoid N+1 queries
    vest_ids = [vest.id for _, _, vest in query if vest]
    all_vest_layers = db.query(VestLayer).filter(VestLayer.vest_id.in_(vest_ids)).all() if vest_ids else []
    material_ids = list(set(vl.material_id for vl in all_vest_layers))
    all_materials = {m.id: m for m in db.query(Material).filter(Material.id.in_(material_ids)).all()} if material_ids else {}
    vest_layers_by_vest = {}
    for vl in all_vest_layers:
        if vl.vest_id not in vest_layers_by_vest:
            vest_layers_by_vest[vl.vest_id] = []
        vest_layers_by_vest[vl.vest_id].append(vl)

    geometry_ids = [ts.geometry_id for _, ts, _ in query if ts and ts.geometry_id]
    all_geometries = {g.id: g for g in db.query(Geometry).filter(Geometry.id.in_(geometry_ids)).all()} if geometry_ids else {}

    calibers = list(set(sd.caliber for sd, _, _ in query if sd.caliber))
    all_ammunition = {a.caliber: a for a in db.query(Ammunition).filter(Ammunition.caliber.in_(calibers)).all()} if calibers else {}

    # Build DataFrame
    rows = []
    layer_counts = []
    aramid_counts = []
    for shot_data_record, test_session, vest in query:
        
        # Try to get vest layers and materials
        layers = []
        total_thickness = 0.0
        total_weight = 0.0
        total_layers = 0
        composition_parts = []
        material_types = set()
        aramid_layers = 0
        
        # Aggregate per-layer mechanical properties
        total_tensile_strength = 0.0
        total_modulus = 0.0
        weave_types = set()
        has_coating = False
        
        if vest:
            vest_layers = vest_layers_by_vest.get(vest.id, [])
            for vl in sorted(vest_layers, key=lambda x: x.layer_index or 0):
                material = all_materials.get(vl.material_id)
                if material:
                    count = vl.layer_count or 1
                    total_layers += count
                    
                    # Track aramid layers
                    if material.material_class and material.material_class.lower() == 'aramid':
                        aramid_layers += count
                    
                    thickness = float(material.thickness_mm) if material.thickness_mm else 0.0
                    weight = float(material.areal_density_g_m2) if material.areal_density_g_m2 else 0.0
                    
                    total_thickness += thickness * count
                    total_weight += weight * count
                    
                    # Aggregate mechanical properties (weighted by layer count)
                    if material.tensile_strength_mpa:
                        total_tensile_strength += float(material.tensile_strength_mpa) * count
                    if material.modulus_gpa:
                        total_modulus += float(material.modulus_gpa) * count
                    
                    if material.weave_type:
                        weave_types.add(material.weave_type)
                    if material.coating:
                        has_coating = True
                    
                    composition_parts.append(f"{count} {material.name}")
                    
                    if material.material_class:
                        material_types.add(material.material_class)
                    
                    layers.append({
                        'material': material,
                        'count': count
                    })
        
        vest_composition = " + ".join(composition_parts) if composition_parts else ""
        material_type_str = ", ".join(sorted(material_types)) if material_types else None
        
        # Get geometry surface area for the tested size
        panel_surface_area_m2 = None
        geometry_name = None
        if test_session and test_session.geometry_id:
            geometry = all_geometries.get(test_session.geometry_id)
            if geometry:
                geometry_name = geometry.name
                surface_areas = geometry.surface_areas or {}
                tested_size = test_session.size or 'M'
                size_areas = surface_areas.get(tested_size)
                if size_areas:
                    front_area = float(size_areas.get('front', 0))
                    back_area = float(size_areas.get('back', 0))
                    panel_surface_area_m2 = front_area + back_area
        
        # Get ammunition info
        caliber = shot_data_record.caliber
        ammunition = all_ammunition.get(caliber)
        
        # Map trauma_qualitative to perforated
        # Use None (missing) when trauma_qualitative is not recorded, so the
        # classifier training excludes unknown shots rather than treating them as negatives.
        perforated = None
        if shot_data_record.trauma_qualitative:
            trauma_lower = shot_data_record.trauma_qualitative.lower()
            if 'punct' in trauma_lower or 'perfor' in trauma_lower or 'penetr' in trauma_lower:
                perforated = 1
            elif 'no punct' in trauma_lower or 'no perfor' in trauma_lower or 'no penetr' in trauma_lower or 'sin perfor' in trauma_lower or 'no paso' in trauma_lower:
                perforated = 0
        
        row = {
            'vest_code': vest.vest_code if vest else None,
            'protocol': test_session.protocol if test_session else None,
            'vest_composition': vest_composition if vest_composition else None,
            'material_thickness_mm': total_thickness if total_thickness > 0 else None,
            'material_weight_g_m2': total_weight if total_weight > 0 else None,
            'number_of_layers': total_layers if total_layers > 0 else None,
            'ammunition_used': ammunition.name if ammunition else caliber,
            'threat_level': normalize_protection_level(shot_data_record.protection_level or (vest.threat_level if vest else None)),
            'shot_number': int(float(shot_data_record.shot_number)) if shot_data_record.shot_number else None,
            'impact_velocity_mps': float(shot_data_record.velocity_m_s) if shot_data_record.velocity_m_s else None,
            'impact_angle_deg': float(shot_data_record.angle_degrees) if shot_data_record.angle_degrees else None,
            'bullet_mass_g': float(ammunition.projectile_mass_grams) if ammunition and ammunition.projectile_mass_grams else None,
            'temperature_c': float(shot_data_record.temperature_c) if shot_data_record.temperature_c else None,
            'humidity_pct': float(shot_data_record.humidity_percent) if shot_data_record.humidity_percent else None,
            'condition': test_session.conditioning if test_session else None,
            'panel_side': shot_data_record.side,
            'backface_deformation_mm': float(shot_data_record.trauma_mm) if shot_data_record.trauma_mm is not None else None,
            'perforated': perforated,
            'pass_fail': None,  # Not available in ShotData
            'material_type': material_type_str,
            'caliber_diameter_mm': float(ammunition.caliber_diameter_mm) if ammunition and ammunition.caliber_diameter_mm else None,
            'caliber_length_mm': float(ammunition.caliber_length_mm) if ammunition and ammunition.caliber_length_mm else None,
            'vest_type': vest.vest_type if vest else None,
            'is_female': vest.is_female if vest else False,
            'ply_orientations': extract_ply_orientations(layers),
            # Vest construction features
            'flexibility_rating': int(vest.flexibility_rating) if vest and vest.flexibility_rating is not None else 0,
            'is_panel_sewn': int(vest.is_panel_sewn) if vest and vest.is_panel_sewn is not None else 0,
            'weight_g': float(vest.weight_g) if vest and vest.weight_g else None,
            # Geometry features
            'panel_surface_area_m2': panel_surface_area_m2,
            'geometry_name': geometry_name,
            # Material mechanical properties (aggregated across layers)
            'total_tensile_strength_mpa': total_tensile_strength if total_tensile_strength > 0 else None,
            'total_modulus_gpa': total_modulus if total_modulus > 0 else None,
            'primary_weave_type': ', '.join(sorted(weave_types)) if weave_types else None,
            'has_coating': int(has_coating),
        }
        
        rows.append(row)
        
        # Track layer counts for analysis
        layer_counts.append(total_layers)
        aramid_counts.append(aramid_layers)

    df = pd.DataFrame(rows)

    # Fetch and merge anchor points (unless explicitly disabled)
    anchor_df = pd.DataFrame()
    anchor_metadata = {"anchor_point_count": 0, "anchor_point_training_rows": 0}

    if not ignore_anchor_points:
        anchor_df, anchor_metadata = fetch_anchor_points_as_training_data(db)
        if not anchor_df.empty:
            if verbose:
                warnings_list.append(f"Added {len(anchor_df)} anchor points to training data")
            df = pd.concat([df, anchor_df], ignore_index=True)
    else:
        if verbose:
            warnings_list.append("Anchor points were excluded from training data")

    # Build metadata
    metadata = {
        "shot_data_count": len(rows),
        "anchor_point_count": anchor_metadata.get("anchor_point_count", 0),
        "anchor_point_training_rows": len(anchor_df) if not anchor_df.empty else 0,
        "total_training_rows": len(df),
    }

    return df, warnings_list, metadata


def fetch_anchor_points_as_training_data(db: Session) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Fetch anchor points and convert them to training data format.
    
    Anchor points are synthetic data points used for model training
    that represent known boundary conditions (e.g., 10,000 layers will stop any bullet).
    
    Returns a DataFrame with the same columns as fetch_training_data,
    plus metadata about the anchor points.
    """
    anchor_points = db.query(AnchorPoint).all()
    
    if not anchor_points:
        return pd.DataFrame(), {"anchor_point_count": 0, "anchor_point_training_rows": 0}
    
    rows = []
    
    for ap in anchor_points:
        # Get anchor point layers
        ap_layers = db.query(AnchorPointLayer, Material).join(
            Material, AnchorPointLayer.material_id == Material.id
        ).filter(AnchorPointLayer.anchor_point_id == ap.id).order_by(AnchorPointLayer.layer_index).all()
        
        # Build composition string and calculate totals
        composition_parts = []
        total_thickness = 0.0
        total_weight = 0.0
        total_layers = 0
        material_types = set()
        
        for apl, material in ap_layers:
            count = apl.layer_count or 1
            total_layers += count
            
            thickness = float(material.thickness_mm) if material.thickness_mm else 0.0
            weight = float(material.areal_density_g_m2) if material.areal_density_g_m2 else 0.0
            
            total_thickness += thickness * count
            total_weight += weight * count
            
            composition_parts.append(f"{count} {material.name}")
            
            if material.material_class:
                material_types.add(material.material_class)
        
        vest_composition = " + ".join(composition_parts) if composition_parts else ""
        material_type_str = ", ".join(sorted(material_types)) if material_types else None
        
        # Determine which ammunition to use
        ammunition_list = []
        
        if ap.ammunition_scope == 'all':
            # Use all ammunition
            ammunition_list = db.query(Ammunition).all()
        elif ap.ammunition_scope == 'calibers' and ap.caliber_ids:
            # Use all ammunition matching the caliber list
            ammos = db.query(Ammunition).filter(Ammunition.caliber.in_(ap.caliber_ids)).all()
            ammunition_list = ammos
        
        # Generate a row for each ammunition
        for ammo in ammunition_list:
            # Use custom velocity if provided, else use nominal velocity
            velocity = ap.custom_velocity_mps if ap.custom_velocity_mps else ammo.nominal_velocity_m_s
            if velocity is None:
                velocity = 0.0
            else:
                velocity = float(velocity)
            
            # Convert perforated to integer
            perforated_int = 1 if ap.expected_perforated else 0
            
            row = {
                'vest_composition': vest_composition if vest_composition else None,
                'material_thickness_mm': total_thickness if total_thickness > 0 else None,
                'material_weight_g_m2': total_weight if total_weight > 0 else None,
                'number_of_layers': total_layers if total_layers > 0 else None,
                'ammunition_used': ammo.name,
                'threat_level': None,  # Anchor points don't have threat levels
                'shot_number': 1,  # Default to first shot
                'impact_velocity_mps': velocity,
                'impact_angle_deg': 0.0,  # Default to 0 degrees
                'bullet_mass_g': float(ammo.projectile_mass_grams) if ammo.projectile_mass_grams else None,
                'temperature_c': 22.0,  # Default to standard conditions
                'humidity_pct': 50.0,  # Default to standard conditions
                'condition': None,
                'panel_side': None,
                'backface_deformation_mm': float(ap.expected_bfd_mm) if ap.expected_bfd_mm is not None else None,
                'perforated': perforated_int,
                'pass_fail': 'fail' if ap.expected_perforated else 'pass',
                'material_type': material_type_str,
                'caliber_diameter_mm': float(ammo.caliber_diameter_mm) if ammo.caliber_diameter_mm else None,
                'caliber_length_mm': float(ammo.caliber_length_mm) if ammo.caliber_length_mm else None,
                'vest_type': 'soft',  # Default to soft armor for anchor points
                'is_female': False,  # Anchor points default to male/unisex
                'ply_orientations': None,  # Anchor points don't have ply orientations
                'flexibility_rating': 0,
                'is_panel_sewn': 0,
                'weight_g': None,
                'panel_surface_area_m2': None,
                'geometry_name': None,
                'total_tensile_strength_mpa': None,
                'total_modulus_gpa': None,
                'primary_weave_type': None,
                'has_coating': 0,
            }
            
            rows.append(row)
    
    metadata = {
        "anchor_point_count": len(anchor_points),
        "anchor_point_training_rows": len(rows),
    }
    
    return pd.DataFrame(rows), metadata


def fetch_material_properties(db: Session) -> Dict[str, Dict[str, float]]:
    """
    Fetch all material properties from database for dynamic feature engineering.
    
    Returns a dict mapping material name to properties:
    {
        "SOFT3000": {
            "density_g_cm3": 1.10,
            "thickness_mm": 0.30,
            "areal_density_g_m2": 6500,
            "tensile_strength_mpa": 3000,
            "elongation_percent": 3.5,
            "material_class": "Aramid",
            "ply_count": 200,
            ...
        },
        ...
    }
    """
    materials = db.query(Material).all()
    
    properties = {}
    for material in materials:
        props = {}
        
        if material.density_g_cm3:
            props['density_g_cm3'] = float(material.density_g_cm3)
        if material.thickness_mm:
            props['thickness_mm'] = float(material.thickness_mm)
        if material.areal_density_g_m2:
            props['areal_density_g_m2'] = float(material.areal_density_g_m2)
        if material.tensile_strength_mpa:
            props['tensile_strength_mpa'] = float(material.tensile_strength_mpa)
        if material.modulus_gpa:
            props['modulus_gpa'] = float(material.modulus_gpa)
        
        # Extract force values and convert to force per cm based on stretch test length
        stretch_length_cm = 5.0  # default to 5cm
        if material.stretch_test_length:
            try:
                # Parse stretch test length (e.g., "2.5cm" or "5cm")
                if '2.5' in material.stretch_test_length or '2,5' in material.stretch_test_length:
                    stretch_length_cm = 2.5
                elif '5' in material.stretch_test_length:
                    stretch_length_cm = 5.0
            except:
                pass
        
        # Longitudinal force per cm
        if material.force_longitudinal_newtons:
            props['force_longitudinal_n_per_cm'] = float(material.force_longitudinal_newtons) / stretch_length_cm
        if material.force_longitudinal_error_percent:
            props['force_longitudinal_error_percent'] = float(material.force_longitudinal_error_percent)
        
        # Transverse force per cm
        if material.force_transverse_newtons:
            props['force_transverse_n_per_cm'] = float(material.force_transverse_newtons) / stretch_length_cm
        if material.force_transverse_error_percent:
            props['force_transverse_error_percent'] = float(material.force_transverse_error_percent)
        
        # Keep elongation_percent for backward compatibility (use longitudinal as primary)
        if material.elongation_longitudinal_percent:
            props['elongation_percent'] = float(material.elongation_longitudinal_percent)
        elif material.elongation_transverse_percent:
            props['elongation_percent'] = float(material.elongation_transverse_percent)
        
        if material.material_class:
            props['material_class'] = material.material_class
        if material.ply_count:
            props['ply_count'] = int(material.ply_count)
        
        properties[material.name] = props
    
    return properties
