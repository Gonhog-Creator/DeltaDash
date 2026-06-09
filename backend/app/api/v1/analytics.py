from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db.models import ShotData as ShotDataModel, TestSession as TestSessionModel, Ammunition as AmmunitionModel, Vest as VestModel, VestLayer as VestLayerModel, Material as MaterialModel
from app.api.v1.auth import get_current_active_user
from app.schemas.analytics import AnalyticsData, AnalyticsPoint
from app.db.models.user import User as UserModel
from app.utils.equations import grams_to_kg, grains_to_kg, calculate_kinetic_energy
from app.services.test_session_service import normalize_caliber

# Create a self-referential alias for parent test session
from sqlalchemy.orm import aliased
ParentTestSession = aliased(TestSessionModel)


router = APIRouter(redirect_slashes=False)


@router.get("/velocity-vs-bfd", response_model=AnalyticsData)
def get_velocity_vs_bfd(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user)
):
    """
    Get analytics data for Velocity vs Trauma (Back Face Deformation).
    
    Queries ShotData table where test session library data is stored.
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
        
        # Get all materials from vest layers - create one data point per material
        materials_found = []
        if vest:
            vest_layers = db.query(VestLayerModel, MaterialModel).outerjoin(
                MaterialModel, VestLayerModel.material_id == MaterialModel.id
            ).filter(VestLayerModel.vest_id == vest.id).all()
            
            if vest_layers:
                for layer, material in vest_layers:
                    if material and material.name:
                        materials_found.append({
                            'name': material.name,
                            'class': material.material_class
                        })
        else:
            # Fallback: try to find vest by vest_number if vest not linked via vest_id
            if shot.vest_number:
                matching_vest = db.query(VestModel).filter(VestModel.vest_code == shot.vest_number).first()
                if matching_vest:
                    vest_layers = db.query(VestLayerModel, MaterialModel).outerjoin(
                        MaterialModel, VestLayerModel.material_id == MaterialModel.id
                    ).filter(VestLayerModel.vest_id == matching_vest.id).all()
                    
                    if vest_layers:
                        for layer, material in vest_layers:
                            if material and material.name:
                                materials_found.append({
                                    'name': material.name,
                                    'class': material.material_class
                                })
        
        # Create a data point for each material found in the vest layers
        if materials_found:
            for mat in materials_found:
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
                    material_name=mat['name'],
                    material_class=mat['class'],
                )
                points.append(point)
        else:
            # If no materials found, still add the point with null material info
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
                material_name=None,
                material_class=None,
            )
            points.append(point)
    
    analytics_data = AnalyticsData(points=points)
    return analytics_data
