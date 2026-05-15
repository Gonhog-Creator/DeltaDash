from sqlalchemy import Column, String, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
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
    areal_density_g_m2 = Column(Numeric(10, 2))
    thickness_mm = Column(Numeric(10, 3))
    density_g_cm3 = Column(Numeric(10, 3))
    tensile_strength_mpa = Column(Numeric(10, 2))
    modulus_gpa = Column(Numeric(10, 2))
    elongation_percent = Column(Numeric(10, 2))
    material_function = Column(String, index=True)
    created_by_username = Column(String, index=True)
    mss_file_path = Column(String)
    sds_file_path = Column(String)
    notes = Column(String)
    source_confidence = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
