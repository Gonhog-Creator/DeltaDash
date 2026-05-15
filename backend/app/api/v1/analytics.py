from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import ShotData as ShotDataModel, TestSession as TestSessionModel, Ammunition as AmmunitionModel
from app.api.v1.auth import get_current_active_user
from app.schemas.analytics import AnalyticsData, AnalyticsPoint
from app.db.models.user import User as UserModel


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
    shot_data = db.query(ShotDataModel, TestSessionModel, AmmunitionModel).join(
        TestSessionModel, ShotDataModel.test_session_id == TestSessionModel.id, isouter=True
    ).join(
        AmmunitionModel, ShotDataModel.caliber == AmmunitionModel.caliber, isouter=True
    ).all()
    
    points = []
    for shot, test_session, ammunition in shot_data:
        # Calculate bullet energy: E = 0.5 * m * v^2
        # Use actual bullet mass from ammunition data (in grams, convert to kg)
        bullet_mass_kg = None
        if ammunition and ammunition.projectile_mass_grams:
            bullet_mass_kg = float(ammunition.projectile_mass_grams) / 1000  # Convert grams to kg
        elif ammunition and ammunition.projectile_mass_grains:
            bullet_mass_kg = float(ammunition.projectile_mass_grains) * 0.06479891  # Convert grains to kg
        else:
            bullet_mass_kg = 0.010  # Fallback to 10g if no ammunition data
        
        velocity = float(shot.velocity_m_s) if shot.velocity_m_s else 0
        bullet_energy = 0.5 * bullet_mass_kg * (velocity ** 2) if velocity else None
        
        angle_degrees_value = float(shot.angle_degrees) if shot.angle_degrees is not None else None
        
        point = AnalyticsPoint(
            velocity=float(shot.velocity_m_s) if shot.velocity_m_s else None,
            bullet_energy=bullet_energy,
            bfd_mm=float(shot.trauma_mm) if shot.trauma_mm else None,
            caliber=shot.caliber,
            protection_level=shot.protection_level,
            test_session_id=str(shot.test_session_id) if shot.test_session_id else None,
            test_session_name=test_session.name if test_session else None,
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
