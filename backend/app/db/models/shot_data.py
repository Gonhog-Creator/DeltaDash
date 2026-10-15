from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class ShotData(Base):
    __tablename__ = "shot_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_session_id = Column(UUID(as_uuid=True), ForeignKey('test_sessions.id'), nullable=False)
    
    vest_number = Column(String)
    side = Column(String)
    conditioning = Column(String)
    angle_degrees = Column(Numeric(5, 2))
    shot_number = Column(String)
    protection_level = Column(String)
    caliber = Column(String)
    trauma_mm = Column(Numeric(10, 2))
    trauma_qualitative = Column(String)
    velocity_m_s = Column(Numeric(10, 2))
    
    temperature_c = Column(Numeric(5, 2))
    humidity_percent = Column(Numeric(5, 2))

    # Enrichment columns (additive; raw import columns above are untouched)
    outcome = Column(String)  # complete_penetration | partial_penetration | stopped | unknown
    outcome_source = Column(String)  # explicit_label | bfd_implied | unresolved
    shot_validity = Column(String)  # valid | invalid | unassessed
    validity_reason = Column(String)
    ammunition_id = Column(UUID(as_uuid=True), ForeignKey('ammunition.id'), nullable=True)
    ammunition_match_status = Column(String)  # exact_name | caliber | alias | ambiguous | unmatched
    specimen_id = Column(UUID(as_uuid=True), ForeignKey('armor_panels.id'), nullable=True)
    normalized_side = Column(String)
    normalized_conditioning = Column(String)
    normalized_protection_level = Column(String)
    duplicate_group_id = Column(UUID(as_uuid=True), index=True)
    is_superseded = Column(String)  # NULL | 'superseded' | 'canonical'

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
