from sqlalchemy import Column, String, Numeric, DateTime, func, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.db.base import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    normalized_name = Column(String, index=True)
    manufacturer = Column(String, index=True)
    supplier = Column(String)
    material_class = Column(String, index=True)
    fiber_type = Column(String)
    weave_type = Column(String)
    coating = Column(String)
    color = Column(String)
    ply_count = Column(Integer, nullable=True)  # Number of plies in this material
    ply_orientations = Column(JSONB, nullable=True)  # Array of orientations for each ply
    areal_density_g_m2 = Column(Numeric(10, 2))
    thickness_mm = Column(Numeric(10, 3))
    thickness_tolerance_mm = Column(String)
    density_g_cm3 = Column(Numeric(10, 3))
    tensile_strength_mpa = Column(Numeric(10, 2))
    has_tensile_strength = Column(String)
    modulus_gpa = Column(Numeric(10, 2))
    has_modulus = Column(String)
    elongation_percent = Column(Numeric(10, 2))
    has_elongation = Column(String)
    material_function = Column(String, index=True)
    created_by_username = Column(String, index=True)
    mss_file_path = Column(String)
    sds_file_path = Column(String)
    mss_original_filename = Column(String)
    sds_original_filename = Column(String)
    notes = Column(String)
    source_confidence = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
