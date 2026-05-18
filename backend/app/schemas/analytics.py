from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class AnalyticsPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    velocity: Optional[float] = None  # Velocity in m/s
    bullet_energy: Optional[float] = None  # Bullet energy in Joules
    bfd_mm: Optional[float] = None  # Back face deformation in mm
    caliber: Optional[str] = None
    protection_level: Optional[str] = None
    test_session_id: Optional[str] = None
    test_session_name: Optional[str] = None
    parent_test_session_name: Optional[str] = None  # Parent test session name
    vest_number: Optional[str] = None
    side: Optional[str] = None  # Front or back
    shot_number: Optional[str] = None
    angle_degrees: Optional[float] = None  # Angle in degrees
    trauma_qualitative: Optional[str] = None  # Test result (OK, punctured, perforada)


class AnalyticsData(BaseModel):
    points: List[AnalyticsPoint]
