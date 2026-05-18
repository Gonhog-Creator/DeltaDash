from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db.models import ShotData as ShotDataModel, TestSession as TestSessionModel, Ammunition as AmmunitionModel
from app.api.v1.auth import get_current_active_user
from app.schemas.analytics import AnalyticsData, AnalyticsPoint
from app.db.models.user import User as UserModel
from app.utils.equations import grams_to_kg, grains_to_kg, calculate_kinetic_energy

# Create a self-join alias for parent test session
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
    # Query shot data with test session names and ammunition data
    # Join on normalized caliber (remove spaces, lowercase) to handle variations
    shot_data = db.query(ShotDataModel, TestSessionModel, AmmunitionModel, ParentTestSession).outerjoin(
        TestSessionModel, ShotDataModel.test_session_id == TestSessionModel.id
    ).outerjoin(
        ParentTestSession, TestSessionModel.parent_test_group_id == ParentTestSession.id
    ).outerjoin(
        AmmunitionModel,
        func.lower(func.replace(ShotDataModel.caliber, ' ', '')) == func.lower(func.replace(AmmunitionModel.caliber, ' ', ''))
    ).all()
    
    points = []
    for shot, test_session, ammunition, parent_session in shot_data:
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
        
        point = AnalyticsPoint(
            velocity=float(shot.velocity_m_s) if shot.velocity_m_s else None,
            bullet_energy=bullet_energy,
            bfd_mm=float(shot.trauma_mm) if shot.trauma_mm else None,
            caliber=shot.caliber,
            protection_level=shot.protection_level,
            test_session_id=str(shot.test_session_id) if shot.test_session_id else None,
            test_session_name=test_session.name if test_session else None,
            parent_test_session_name=parent_session.name if parent_session else None,
            vest_number=shot.vest_number,
            side=shot.side,
            shot_number=shot.shot_number,
            angle_degrees=angle_degrees_value,
            trauma_qualitative=shot.trauma_qualitative,
        )
        points.append(point)
    
    analytics_data = AnalyticsData(points=points)
    # Log the serialized JSON to check if angle_degrees is included
    import json
    json_str = analytics_data.model_dump_json()
    print(f"DEBUG: Serialized JSON length: {len(json_str)}")
    if 'angle_degrees' in json_str and '45' in json_str:
        print(f"DEBUG: Found angle_degrees with 45 in JSON")
    else:
        print(f"DEBUG: angle_degrees not found or not 45 in JSON")
    
    return analytics_data
