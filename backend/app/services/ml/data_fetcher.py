"""
Data fetcher for ML training - pulls training data from database.
"""
import re
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

    # shot_data.caliber may contain an ammunition NAME rather than a caliber;
    # key the lookup by both, and prefer the canonical ammunition_id FK.
    all_ammo_rows = db.query(Ammunition).all()
    all_ammunition = {}
    all_ammunition_by_id = {}
    for a in all_ammo_rows:
        all_ammunition_by_id[a.id] = a
        if a.caliber:
            all_ammunition.setdefault(a.caliber, a)
        if a.name:
            all_ammunition.setdefault(a.name, a)

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
        
        # Get ammunition info (canonical FK first, then name/caliber fallback)
        caliber = shot_data_record.caliber
        ammunition = None
        if getattr(shot_data_record, 'ammunition_id', None):
            ammunition = all_ammunition_by_id.get(shot_data_record.ammunition_id)
        if ammunition is None:
            ammunition = all_ammunition.get(caliber)

        # Map trauma_qualitative to perforated
        # Use None (missing) when trauma_qualitative is not recorded, so the
        # classifier training excludes unknown shots rather than treating them as negatives.
        # Negated labels are checked BEFORE positive substrings so
        # "no perforado"/"sin perforación" cannot match 'perfor'.
        perforated = None
        if shot_data_record.trauma_qualitative:
            trauma_lower = shot_data_record.trauma_qualitative.lower()
            if 'no punct' in trauma_lower or 'no perfor' in trauma_lower or 'no penetr' in trauma_lower or 'sin perfor' in trauma_lower or 'no paso' in trauma_lower:
                perforated = 0
            elif 'punct' in trauma_lower or 'perfor' in trauma_lower or 'penetr' in trauma_lower:
                perforated = 1
        # Fallback: a recorded BFD means the bullet was stopped behind the
        # panel -> the shot did not perforate. Shots with no BFD and no
        # qualitative note stay None (excluded from classifier training).
        if perforated is None and shot_data_record.trauma_mm is not None:
            perforated = 0

        # Derived pass/fail: perforation or BFD over the NIJ 44mm backface
        # limit means fail; a recorded stop under the limit means pass.
        pass_fail = None
        if perforated == 1 or (shot_data_record.trauma_mm is not None
                               and float(shot_data_record.trauma_mm) > 44.0):
            pass_fail = 'fail'
        elif perforated == 0 or shot_data_record.trauma_mm is not None:
            pass_fail = 'pass'

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
            'condition': shot_data_record.conditioning or (test_session.conditioning if test_session else None),
            'panel_side': shot_data_record.side,
            'backface_deformation_mm': float(shot_data_record.trauma_mm) if shot_data_record.trauma_mm is not None else None,
            'perforated': perforated,
            'pass_fail': pass_fail,  # Derived: perforated or BFD > 44mm -> fail
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
        physics_df = generate_physics_anchor_rows(db)
        if not physics_df.empty:
            anchor_df = pd.concat([anchor_df, physics_df], ignore_index=True)
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


def generate_physics_anchor_rows(db: Session) -> pd.DataFrame:
    """
    Physics-generated anchor rows that fill the layer-count gap between the
    hand-authored anchors (1-5 layers perforate / 200 layers stops).

    Crude membrane model, deliberately conservative:
      per-ply capacity  E_ply ~ F_break[N/cm] x engaged_width[cm] x delta_break[m]
      stack capacity    E_cap  = N x E_ply
      bullet energy     KE     = 0.5 x m x v^2

    This underpredicts real ballistic resistance (ignores stress-wave load
    spreading, yarn pull-out, friction), so anchors are only emitted in the
    certain regimes:
      perforated=1  when  E_cap <  KE / MARGIN
      perforated=0  when  E_cap >  KE * MARGIN
    The transition band between them gets no anchor — real data interpolates.

    Rows mirror fetch_anchor_points_as_training_data output columns.
    """
    MARGIN = 3.0
    GAUGE_M = 0.05  # strip-test gauge length, 5 cm
    MAX_LAYERS = 250

    material_properties = fetch_material_properties(db)
    ammunitions = db.query(Ammunition).all()

    rows = []
    for mat_name, props in material_properties.items():
        force_n_per_cm = props.get('force_longitudinal_n_per_cm')
        elong_pct = props.get('elongation_percent')
        thickness = props.get('thickness_mm')
        areal = props.get('areal_density_g_m2')
        if not force_n_per_cm or not elong_pct or not thickness:
            continue
        delta_break_m = (elong_pct / 100.0) * GAUGE_M
        mat_class = props.get('material_class')

        for ammo in ammunitions:
            # grams/fps are the populated fields; fall back through units
            mass_g = ammo.projectile_mass_grams
            if not mass_g and ammo.projectile_mass_grains:
                mass_g = float(ammo.projectile_mass_grains) * 0.0647989
            velocity = ammo.nominal_velocity_m_s
            if not velocity and ammo.nominal_velocity_fps:
                velocity = float(ammo.nominal_velocity_fps) * 0.3048
            diameter_mm = ammo.caliber_diameter_mm
            if not diameter_mm and ammo.caliber:
                m = re.match(r'^\s*\.(\d+)', ammo.caliber)       # '.38 Special' -> inches
                if m:
                    diameter_mm = float(f'0.{m.group(1)}') * 25.4
                else:
                    m = re.match(r'^\s*(\d+(?:\.\d+)?)', ammo.caliber)  # '5.56x45mm', '9mm'
                    if m and float(m.group(1)) < 30:
                        diameter_mm = float(m.group(1))
            if not mass_g or not diameter_mm or not velocity:
                continue
            engaged_width_cm = float(diameter_mm) / 10.0
            e_ply_j = force_n_per_cm * engaged_width_cm * delta_break_m
            if e_ply_j <= 0:
                continue
            ke_j = 0.5 * (float(mass_g) / 1000.0) * float(velocity) ** 2

            n_certain_perf = int((ke_j / MARGIN) / e_ply_j)       # max N still certain-perforate
            n_certain_stop = int((ke_j * MARGIN) / e_ply_j) + 1   # min N certain-stop

            candidate_ns = []
            for n in {n_certain_perf, int(n_certain_perf * 0.6)}:
                if 6 <= n <= MAX_LAYERS:          # below 6 the authored anchors already cover it
                    candidate_ns.append((n, 1))
            for n in {n_certain_stop, int(n_certain_stop * 1.3)}:
                if n <= MAX_LAYERS:
                    candidate_ns.append((n, 0))

            for n_layers, label in candidate_ns:
                rows.append({
                    'vest_composition': f"{n_layers} {mat_name}",
                    'material_thickness_mm': n_layers * thickness,
                    'material_weight_g_m2': n_layers * areal if areal else None,
                    'number_of_layers': n_layers,
                    'ammunition_used': ammo.name,
                    'threat_level': None,
                    'shot_number': 1,
                    'impact_velocity_mps': float(velocity),
                    'impact_angle_deg': 0.0,
                    'bullet_mass_g': float(mass_g),
                    'temperature_c': 22.0,
                    'humidity_pct': 50.0,
                    'condition': None,
                    'panel_side': None,
                    'backface_deformation_mm': None,
                    'perforated': label,
                    'pass_fail': 'fail' if label else 'pass',
                    'material_type': mat_class,
                    'caliber_diameter_mm': float(diameter_mm),
                    'caliber_length_mm': float(ammo.caliber_length_mm) if ammo.caliber_length_mm else None,
                    'vest_type': 'soft',
                    'is_female': False,
                    'ply_orientations': None,
                    'flexibility_rating': 0,
                    'is_panel_sewn': 0,
                    'weight_g': None,
                    'panel_surface_area_m2': None,
                    'geometry_name': None,
                    'total_tensile_strength_mpa': None,
                    'total_modulus_gpa': None,
                    'primary_weave_type': None,
                    'has_coating': 0,
                })

    return pd.DataFrame(rows)


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
            props['elongation_longitudinal_percent'] = float(material.elongation_longitudinal_percent)
        elif material.elongation_transverse_percent:
            props['elongation_percent'] = float(material.elongation_transverse_percent)
        if material.elongation_transverse_percent:
            props['elongation_transverse_percent'] = float(material.elongation_transverse_percent)

        # Derive apparent fabric-level strength from strip-test force when
        # tensile_strength_mpa / modulus_gpa were never recorded directly.
        # Strip test: F per cm width -> sigma[MPa] = F/(10mm x thickness mm) = N/mm2
        # Apparent chord modulus: E[GPa] = sigma[MPa]/1000 / epsilon_break
        if ('tensile_strength_mpa' not in props
                and 'force_longitudinal_n_per_cm' in props
                and props.get('thickness_mm')):
            props['tensile_strength_mpa'] = (
                props['force_longitudinal_n_per_cm'] / (10.0 * props['thickness_mm'])
            )
            props['tensile_strength_derived'] = True
        if ('modulus_gpa' not in props
                and 'tensile_strength_mpa' in props
                and props.get('elongation_percent')):
            props['modulus_gpa'] = (
                (props['tensile_strength_mpa'] / 1000.0)
                / (props['elongation_percent'] / 100.0)
            )
            props['modulus_derived'] = True

        if material.material_class:
            props['material_class'] = material.material_class
        if material.ply_count:
            props['ply_count'] = int(material.ply_count)
        
        properties[material.name] = props
    
    return properties
