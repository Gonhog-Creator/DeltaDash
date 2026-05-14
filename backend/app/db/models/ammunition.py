from sqlalchemy import Column, String, Numeric, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class Ammunition(Base):
    __tablename__ = "ammunition"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    caliber = Column(String, index=True)
    projectile_type = Column(String)
    projectile_mass_grains = Column(Numeric(10, 2))
    projectile_mass_grams = Column(Numeric(10, 3))
    nominal_velocity_fps = Column(Numeric(10, 2))
    nominal_velocity_m_s = Column(Numeric(10, 2))
    manufacturer = Column(String)
    lot_number = Column(String)
    standard_reference = Column(String)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
