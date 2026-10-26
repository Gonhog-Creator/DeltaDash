from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db.models import ShotData as ShotDataModel, TestSession as TestSessionModel, Ammunition as AmmunitionModel, Vest as VestModel, VestLayer as VestLayerModel, Material as MaterialModel
from app.db.models.material_property_spec import MaterialPropertySpec as MaterialPropertySpecModel
from app.db.models.material_property_distribution import MaterialPropertyDistribution as MaterialPropertyDistributionModel
from app.db.models.material_property_measurement import MaterialPropertyMeasurement as MaterialPropertyMeasurementModel
from app.db.models.material_document import MaterialDocument as MaterialDocumentModel
from app.api.v1.auth import get_current_active_user
from app.schemas.analytics import AnalyticsData, AnalyticsPoint
from app.db.models.user import User as UserModel
from app.utils.equations import grams_to_kg, grains_to_kg, calculate_kinetic_energy
from app.services.test_session_service import normalize_caliber
from pydantic import BaseModel

# Create a self-referential alias for parent test session
from sqlalchemy.orm import aliased
ParentTestSession = aliased(TestSessionModel)


class MaterialAnalyticsData(BaseModel):
    material_classes: List[dict]
    materials: List[dict]


router = APIRouter(redirect_slashes=False)


@router.get("/velocity-vs-bfd", response_model=AnalyticsData)
def get_velocity_vs_bfd(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get analytics data for Velocity vs Trauma (Back Face Deformation).
    
    Queries ShotData table where test session library data is stored.
    Returns one data point per shot (not per material) for efficiency.
    """
    # Query shot data with test session names and vest information
    shot_data = db.query(ShotDataModel, TestSessionModel, ParentTestSession, VestModel).outerjoin(
        TestSessionModel, ShotDataModel.test_session_id == TestSessionModel.id
    ).outerjoin(
        ParentTestSession, TestSessionModel.parent_test_group_id == ParentTestSession.id
    ).outerjoin(
        VestModel, TestSessionModel.vest_id == VestModel.id
    ).all()
    
    # Get all ammunition data for intelligent matching
    ammunition_data = db.query(AmmunitionModel).all()
    
    # Create a mapping of normalized calibers to ammunition records
    caliber_to_ammo = {}
    for ammo in ammunition_data:
        if ammo.caliber:
            normalized = normalize_caliber(ammo.caliber)
            caliber_to_ammo[normalized] = ammo
    
    # Helper function to extract numeric value from caliber string
    def extract_caliber_number(caliber_str):
        import re
        # Try to extract a number from the caliber string
        # e.g., "9 mm" -> 9, ".357 MAG" -> 0.357, "9x19mm" -> 9
        # Match numbers that start with a decimal point or have digits first
        match = re.search(r'(\.\d+|\d+\.?\d*)', caliber_str)
        if match:
            return float(match.group(1))
        return None
    
    # Normalize protection levels
    def normalize_protection_level(level: str) -> str:
        if not level:
            return level
        level_upper = level.upper().strip()
        # Map ARG_RB4 to RB4
        if level_upper == 'ARG_RB4':
            return 'RB4'
        return level
    
    points = []
    for shot, test_session, parent_session, vest in shot_data:
        # Intelligent caliber matching to find correct ammunition
        ammunition = None
        standardized_caliber = None
        if shot.caliber:
            normalized_shot_caliber = normalize_caliber(shot.caliber)
            shot_caliber_number = extract_caliber_number(shot.caliber)
            
            # Try exact match first on text caliber field
            if normalized_shot_caliber in caliber_to_ammo:
                ammunition = caliber_to_ammo[normalized_shot_caliber]
                standardized_caliber = ammunition.caliber
            else:
                # Try fuzzy matching on text caliber field
                for ammo_normalized, ammo in caliber_to_ammo.items():
                    # Check if one is a substring of the other
                    if normalized_shot_caliber in ammo_normalized or ammo_normalized in normalized_shot_caliber:
                        ammunition = ammo
                        standardized_caliber = ammunition.caliber
                        break
                    # Check for common variations (e.g., .357 vs .357 mag)
                    if normalized_shot_caliber.replace('.', '').replace('mag', '') == ammo_normalized.replace('.', '').replace('mag', ''):
                        ammunition = ammo
                        standardized_caliber = ammunition.caliber
                        break
            
            # If text matching failed, try numeric matching using diameter fields
            if not ammunition and shot_caliber_number:
                for ammo in ammunition_data:
                    # Try matching against caliber_diameter_mm (for metric calibers like 9mm)
                    if ammo.caliber_diameter_mm and abs(float(ammo.caliber_diameter_mm) - shot_caliber_number) < 0.1:
                        ammunition = ammo
                        standardized_caliber = ammunition.caliber
                        break
                    # Try matching against caliber_inch (for imperial calibers like .357)
                    if ammo.caliber_inch and abs(float(ammo.caliber_inch) - shot_caliber_number) < 0.01:
                        ammunition = ammo
                        standardized_caliber = ammunition.caliber
                        break
            
            # If no ammunition match found, use normalized caliber as fallback
            if not standardized_caliber:
                standardized_caliber = normalized_shot_caliber
        
        # Convert bullet mass to kg using centralized equations
        bullet_mass_kg = None
        if ammunition and ammunition.projectile_mass_grams:
            bullet_mass_kg = grams_to_kg(float(ammunition.projectile_mass_grams))
        elif ammunition and ammunition.projectile_mass_grains:
            bullet_mass_kg = grains_to_kg(float(ammunition.projectile_mass_grains))
        else:
            bullet_mass_kg = 0.010  # Fallback to 10g if no ammunition data
        
        velocity = float(shot.velocity_m_s) if shot.velocity_m_s else 0
        bullet_energy = calculate_kinetic_energy(bullet_mass_kg, velocity)
        
        angle_degrees_value = float(shot.angle_degrees) if shot.angle_degrees is not None else None
        
        # Get the dominant material for this vest
        material_name = None
        material_class = None
        if vest:
            # Get vest layers with materials
            vest_layers = db.query(VestLayerModel, MaterialModel).outerjoin(
                MaterialModel, VestLayerModel.material_id == MaterialModel.id
            ).filter(VestLayerModel.vest_id == vest.id).all()
            
            if vest_layers:
                # Calculate dominant material based on layer_count * thickness
                material_scores = {}
                for layer, material in vest_layers:
                    if material:
                        # Score = layer_count * material_thickness
                        thickness = float(material.thickness_mm) if material.thickness_mm else 1.0
                        layer_count = layer.layer_count if layer.layer_count else 1
                        score = layer_count * thickness
                        
                        material_key = material.id
                        if material_key not in material_scores:
                            material_scores[material_key] = {
                                'name': material.name,
                                'material_class': material.material_class,
                                'score': 0
                            }
                        material_scores[material_key]['score'] += score
                
                # Find the material with the highest score
                if material_scores:
                    dominant_material = max(material_scores.values(), key=lambda x: x['score'])
                    material_name = dominant_material['name']
                    material_class = dominant_material['material_class']
        
        # Create one data point per shot (not per material) for efficiency
        point = AnalyticsPoint(
            velocity=float(shot.velocity_m_s) if shot.velocity_m_s else None,
            bullet_energy=bullet_energy,
            bfd_mm=float(shot.trauma_mm) if shot.trauma_mm else None,
            caliber=ammunition.name if ammunition and ammunition.name else standardized_caliber,
            protection_level=normalize_protection_level(shot.protection_level),
            test_session_id=str(shot.test_session_id) if shot.test_session_id else None,
            test_session_name=test_session.name if test_session else None,
            parent_test_session_name=parent_session.name if parent_session else None,
            vest_number=shot.vest_number,
            side=shot.side,
            shot_number=shot.shot_number,
            angle_degrees=angle_degrees_value,
            trauma_qualitative=shot.trauma_qualitative,
            is_official=test_session.is_official if test_session else None,
            material_name=material_name,
            material_class=material_class,
        )
        points.append(point)
    
    analytics_data = AnalyticsData(points=points)
    return analytics_data


@router.get("/material-analytics", response_model=MaterialAnalyticsData)
def get_material_analytics(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get aggregated material analytics data.
    Returns counts and average BFD by material class and material name.
    """
    # Query shot data with vest information
    shot_data = db.query(ShotDataModel, TestSessionModel, VestModel).outerjoin(
        TestSessionModel, ShotDataModel.test_session_id == TestSessionModel.id
    ).outerjoin(
        VestModel, TestSessionModel.vest_id == VestModel.id
    ).all()
    
    # Aggregate material data
    material_class_data = {}
    material_data = {}
    
    for shot, test_session, vest in shot_data:
        if not vest or not shot.trauma_mm:
            continue
            
        # Get vest layers with materials
        vest_layers = db.query(VestLayerModel, MaterialModel).outerjoin(
            MaterialModel, VestLayerModel.material_id == MaterialModel.id
        ).filter(VestLayerModel.vest_id == vest.id).all()
        
        for layer, material in vest_layers:
            if not material:
                continue
                
            # Aggregate by material class
            material_class = material.material_class or 'Unknown'
            if material_class not in material_class_data:
                material_class_data[material_class] = {'sum': 0, 'count': 0}
            material_class_data[material_class]['sum'] += float(shot.trauma_mm)
            material_class_data[material_class]['count'] += 1
            
            # Aggregate by material name
            material_name = material.name or 'Unknown'
            material_key = f"{material_class}::{material_name}"
            if material_key not in material_data:
                material_data[material_key] = {
                    'material_class': material_class,
                    'material_name': material_name,
                    'sum': 0,
                    'count': 0
                }
            material_data[material_key]['sum'] += float(shot.trauma_mm)
            material_data[material_key]['count'] += 1
    
    # Calculate averages
    material_classes = [
        {
            'material_class': mc,
            'avg_bfd': data['sum'] / data['count'],
            'count': data['count']
        }
        for mc, data in material_class_data.items()
    ]
    
    materials = [
        {
            'material_class': data['material_class'],
            'material_name': data['material_name'],
            'avg_bfd': data['sum'] / data['count'],
            'count': data['count']
        }
        for data in material_data.values()
    ]
    
    return MaterialAnalyticsData(material_classes=material_classes, materials=materials)


# ---------------------------------------------------------------------------
# Data completeness ("what are we missing") report
# ---------------------------------------------------------------------------
# Curated lists of fields the models/sims rely on, plus fields that matter for
# engineering traceability. Each entry: (column, human label, critical?).
_MATERIAL_FIELDS = [
    ("areal_density_g_m2",       "areal density (g/m²)",            True),
    ("thickness_mm",             "thickness (mm)",                  True),
    ("density_g_cm3",            "density (g/cm³)",                 False),
    ("tensile_strength_mpa",     "tensile strength (MPa)",          True),
    ("modulus_gpa",              "modulus (GPa)",                   True),
    ("areal_density_tolerance",  "areal density tolerance",         False),
    ("thickness_tolerance_mm",   "thickness tolerance (mm)",        False),
    ("supplier",                 "supplier",                        False),
    ("manufacturer",             "manufacturer",                    False),
    ("fiber_type",               "fiber type",                      False),
    ("weave_type",               "weave type",                      False),
    ("material_class",           "material class",                  False),
    ("mss_file_path",            "MSS document",                    False),
    ("sds_file_path",            "SDS document",                    False),
]
_VEST_FIELDS = [
    ("total_layers",             "total layers",                    True),
    ("total_thickness_mm",       "total thickness (mm)",            True),
    ("weight_g",                 "weight (g)",                      True),
    ("threat_level",             "threat level",                    True),
    ("protection_class",         "protection class",                False),
    ("trauma_homologation",      "trauma homologation",             False),
    ("size_curve",               "size curve",                      False),
    ("compatible_geometry_ids",  "compatible geometries",           False),
    ("is_panel_sewn",            "panel sewn flag",                 False),
    ("stitch_pattern",           "stitch pattern",                  False),
    ("is_female",                "male/female flag",                False),
]
_AMMO_FIELDS = [
    ("projectile_mass_grams",    "projectile mass (g)",             True),
    ("nominal_velocity_m_s",     "nominal velocity (m/s)",          True),
    ("caliber_diameter_mm",      "caliber diameter (mm)",           True),
    ("caliber_length_mm",        "caliber length (mm)",             True),
    ("caliber_inch",             "caliber (in)",                    False),
    ("lot_number",               "lot number",                      False),
    ("standard_reference",       "standard reference",              False),
]
_SESSION_FIELDS = [
    ("excel_file_path",          "source Excel file",               False),
    ("vest_id",                  "linked vest",                     True),
    ("geometry_id",              "geometry",                        False),
    ("ballistic_limit",          "ballistic limit",                 False),
    ("clay_temperature_c",       "clay temperature",                False),
    ("ambient_temperature_c",    "ambient temperature",             False),
    ("humidity_percent",         "humidity",                        False),
    ("conditioning",             "conditioning",                    False),
]


def _missing_fields(row, spec):
    """Return [{'field', 'label', 'critical'}] for fields that are null/empty."""
    out = []
    for col, label, critical in spec:
        v = getattr(row, col, None)
        if v is None or (isinstance(v, str) and not v.strip()) or v == [] or v == {}:
            out.append({"field": col, "label": label, "critical": critical})
    return out


@router.get("/data-gaps")
def get_data_gaps(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    """Per-entity completeness report: which fields are missing per material,
    vest, ammunition, and test session — so an engineer can see exactly what
    data still needs to be collected.
    """
    # ---- materials -----------------------------------------------------------
    spec_counts = dict(
        db.query(MaterialPropertySpecModel.material_id, func.count())
        .group_by(MaterialPropertySpecModel.material_id).all()
    )
    dist_counts = dict(
        db.query(MaterialPropertyDistributionModel.material_id, func.count())
        .group_by(MaterialPropertyDistributionModel.material_id).all()
    )
    meas_counts = dict(
        db.query(MaterialPropertyMeasurementModel.material_id, func.count())
        .group_by(MaterialPropertyMeasurementModel.material_id).all()
    )
    doc_counts = dict(
        db.query(MaterialDocumentModel.material_id, func.count())
        .group_by(MaterialDocumentModel.material_id).all()
    )
    # materials actually used in vests — gaps here matter most
    used_material_ids = {
        r[0] for r in db.query(VestLayerModel.material_id)
        .filter(VestLayerModel.material_id.isnot(None)).all()
    }
    materials = []
    for m in db.query(MaterialModel).all():
        missing = _missing_fields(m, _MATERIAL_FIELDS)
        if not spec_counts.get(m.id):
            missing.append({"field": "property_specs", "label": "property spec limits", "critical": False})
        if not dist_counts.get(m.id):
            missing.append({"field": "property_distributions",
                            "label": "property distributions (MC sampling)", "critical": True})
        if not meas_counts.get(m.id):
            missing.append({"field": "property_measurements",
                            "label": "coupon/measurement data", "critical": True})
        if not doc_counts.get(m.id):
            missing.append({"field": "documents", "label": "linked documents", "critical": False})
        materials.append({
            "id": str(m.id), "name": m.name, "used_in_vests": m.id in used_material_ids,
            "missing": missing,
        })
    materials.sort(key=lambda r: (not r["used_in_vests"], -len(r["missing"])))

    # ---- vests ----------------------------------------------------------------
    layer_counts = dict(
        db.query(VestLayerModel.vest_id, func.sum(VestLayerModel.layer_count))
        .group_by(VestLayerModel.vest_id).all()
    )
    session_counts = dict(
        db.query(TestSessionModel.vest_id, func.count())
        .group_by(TestSessionModel.vest_id).all()
    )
    shot_counts = dict(
        db.query(TestSessionModel.vest_id, func.count(ShotDataModel.id))
        .join(ShotDataModel, ShotDataModel.test_session_id == TestSessionModel.id)
        .group_by(TestSessionModel.vest_id).all()
    )
    vests = []
    for v in db.query(VestModel).all():
        missing = _missing_fields(v, _VEST_FIELDS)
        if not layer_counts.get(v.id):
            missing.append({"field": "vest_layers", "label": "layer configuration", "critical": True})
        vests.append({
            "id": str(v.id), "name": v.vest_code or str(v.id),
            "threat_level": v.threat_level,
            "layers_configured": int(layer_counts.get(v.id) or 0),
            "test_sessions": int(session_counts.get(v.id) or 0),
            "shots": int(shot_counts.get(v.id) or 0),
            "missing": missing,
        })
    vests.sort(key=lambda r: (-len(r["missing"])))

    # ---- ammunition -------------------------------------------------------------
    ammo = []
    for a in db.query(AmmunitionModel).all():
        ammo.append({
            "id": str(a.id), "name": a.name or str(a.id), "caliber": a.caliber,
            "missing": _missing_fields(a, _AMMO_FIELDS),
        })
    ammo.sort(key=lambda r: -len(r["missing"]))

    # ---- test sessions -----------------------------------------------------------
    sessions = []
    for s in db.query(TestSessionModel).all():
        sessions.append({
            "id": str(s.id), "name": s.name or str(s.id), "test_date": str(s.test_date),
            "missing": _missing_fields(s, _SESSION_FIELDS),
        })
    sessions.sort(key=lambda r: -len(r["missing"]))

    # shot-level aggregate gaps (too many rows for per-shot listing)
    total_shots = db.query(func.count()).select_from(ShotDataModel).scalar() or 0
    shot_gaps = {
        "total_shots": total_shots,
        "missing_velocity": db.query(func.count()).select_from(ShotDataModel)
            .filter(ShotDataModel.velocity_m_s.is_(None)).scalar(),
        "missing_bfd": db.query(func.count()).select_from(ShotDataModel)
            .filter(ShotDataModel.trauma_mm.is_(None)).scalar(),
        "missing_outcome": db.query(func.count()).select_from(ShotDataModel)
            .filter(ShotDataModel.outcome.is_(None)).scalar(),
        "missing_ammo": db.query(func.count()).select_from(ShotDataModel)
            .filter(ShotDataModel.ammunition_id.is_(None)).scalar(),
    }

    return {
        "materials": materials,
        "vests": vests,
        "ammunition": ammo,
        "test_sessions": sessions,
        "shot_data": shot_gaps,
    }
