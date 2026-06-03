"""
Data fetcher for ML training - pulls training data from database.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import pandas as pd

from app.db.models import ShotData, Vest, VestLayer, Material, TestSession, Ammunition


def fetch_training_data(db: Session, verbose: bool = True) -> tuple[pd.DataFrame, list[str]]:
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
            print(f"WARNING: {msg}")
            warnings_list.append(msg)
        if missing_density:
            msg = f"{len(missing_density)} materials missing areal density (g/m²): {', '.join(missing_density[:10])}{'...' if len(missing_density) > 10 else ''}"
            print(f"WARNING: {msg}")
            warnings_list.append(msg)
        if missing_ply:
            msg = f"{len(missing_ply)} materials missing ply count: {', '.join(missing_ply[:10])}{'...' if len(missing_ply) > 10 else ''}"
            print(f"WARNING: {msg}")
            warnings_list.append(msg)
        print(f"INFO: Total materials in database: {len(materials)}")

    # Query all shot data with relationships - less restrictive
    query = (
        db.query(ShotData, TestSession, Vest)
        .outerjoin(TestSession, ShotData.test_session_id == TestSession.id)
        .outerjoin(Vest, TestSession.vest_id == Vest.id)
        .all()
    )

    if not query:
        print(f"DEBUG: Query returned no results")
        return pd.DataFrame(), warnings_list

    print(f"DEBUG: Query returned {len(query)} shot data records")

    # Count records per vest
    vest_counts = {}
    for shot_data_record, test_session, vest in query:
        vest_code = vest.vest_code if vest else "No Vest"
        vest_counts[vest_code] = vest_counts.get(vest_code, 0) + 1

    print(f"DEBUG: Records per vest:")
    for vest_code, count in sorted(vest_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {vest_code}: {count}")
    
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
        
        if vest:
            vest_layers = db.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
            for vl in sorted(vest_layers, key=lambda x: x.layer_index or 0):
                material = db.query(Material).filter(Material.id == vl.material_id).first()
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
                    
                    composition_parts.append(f"{count} {material.name}")
                    
                    if material.material_class:
                        material_types.add(material.material_class)
                    
                    layers.append({
                        'material': material,
                        'count': count
                    })
        
        vest_composition = " + ".join(composition_parts) if composition_parts else ""
        material_type_str = ", ".join(sorted(material_types)) if material_types else None
        
        # Get ammunition info
        caliber = shot_data_record.caliber
        ammunition = db.query(Ammunition).filter(Ammunition.caliber == caliber).first()
        
        # Map trauma_qualitative to perforated
        perforated = 0
        if shot_data_record.trauma_qualitative:
            trauma_lower = shot_data_record.trauma_qualitative.lower()
            if 'punct' in trauma_lower or 'perfor' in trauma_lower or 'penetr' in trauma_lower:
                perforated = 1
        
        row = {
            'vest_composition': vest_composition if vest_composition else None,
            'material_thickness_mm': total_thickness if total_thickness > 0 else None,
            'material_weight_g_m2': total_weight if total_weight > 0 else None,
            'number_of_layers': total_layers if total_layers > 0 else None,
            'ammunition_used': ammunition.name if ammunition else caliber,
            'threat_level': shot_data_record.protection_level or (vest.threat_level if vest else None),
            'shot_number': int(float(shot_data_record.shot_number)) if shot_data_record.shot_number else None,
            'impact_velocity_mps': float(shot_data_record.velocity_m_s) if shot_data_record.velocity_m_s else None,
            'impact_angle_deg': float(shot_data_record.angle_degrees) if shot_data_record.angle_degrees else None,
            'bullet_mass_g': float(ammunition.projectile_mass_grams) if ammunition and ammunition.projectile_mass_grams else None,
            'temperature_c': float(shot_data_record.temperature_c) if shot_data_record.temperature_c else None,
            'humidity_pct': float(shot_data_record.humidity_percent) if shot_data_record.humidity_percent else None,
            'condition': test_session.conditioning if test_session else None,
            'panel_side': shot_data_record.side,
            'backface_deformation_mm': float(shot_data_record.trauma_mm) if shot_data_record.trauma_mm else None,
            'perforated': perforated,
            'pass_fail': None,  # Not available in ShotData
            'material_type': material_type_str,
        }
        
        rows.append(row)
        
        # Track layer counts for analysis
        layer_counts.append(total_layers)
        aramid_counts.append(aramid_layers)

    df = pd.DataFrame(rows)
    
    # Print layer count statistics
    print(f"DEBUG: Layer count statistics:")
    print(f"  Min: {min(layer_counts) if layer_counts else 0}")
    print(f"  Max: {max(layer_counts) if layer_counts else 0}")
    print(f"  Mean: {sum(layer_counts) / len(layer_counts) if layer_counts else 0:.1f}")
    print(f"  Median: {sorted(layer_counts)[len(layer_counts) // 2] if layer_counts else 0}")
    
    # Print aramid layer statistics
    print(f"DEBUG: Aramid layer statistics:")
    print(f"  Min: {min(aramid_counts) if aramid_counts else 0}")
    print(f"  Max: {max(aramid_counts) if aramid_counts else 0}")
    print(f"  Mean: {sum(aramid_counts) / len(aramid_counts) if aramid_counts else 0:.1f}")
    print(f"  Records with >20 aramid layers: {sum(1 for c in aramid_counts if c > 20)}")
    print(f"  Records with >30 aramid layers: {sum(1 for c in aramid_counts if c > 30)}")
    print(f"  Records with >40 aramid layers: {sum(1 for c in aramid_counts if c > 40)}")
    
    # Add statistics to warnings
    warnings_list.append(f"Layer count range: {min(layer_counts) if layer_counts else 0} - {max(layer_counts) if layer_counts else 0} (mean: {sum(layer_counts) / len(layer_counts) if layer_counts else 0:.1f})")
    warnings_list.append(f"Aramid layer range: {min(aramid_counts) if aramid_counts else 0} - {max(aramid_counts) if aramid_counts else 0} (mean: {sum(aramid_counts) / len(aramid_counts) if aramid_counts else 0:.1f})")
    warnings_list.append(f"Records with >30 aramid layers: {sum(1 for c in aramid_counts if c > 30)}")

    return df, warnings_list


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
