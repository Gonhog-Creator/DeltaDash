from sqlalchemy import Column, String, Numeric, Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

from app.db.base import Base


class AnchorPoint(Base):
    __tablename__ = "anchor_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    
    # Ammunition scope: 'all' for all ammunition, 'calibers' for specific calibers
    ammunition_scope = Column(String, nullable=False, default='all')  # 'all' or 'calibers'
    
    # For 'calibers' scope: list of caliber strings (e.g., ['9mm', '.44 MAG'])
    caliber_ids = Column(ARRAY(String), nullable=True)
    
    # Expected outcomes
    expected_perforated = Column(Boolean, nullable=False)
    expected_bfd_mm = Column(Numeric(10, 2), nullable=True)  # Only if not perforated
    
    # Velocity override (optional, uses nominal velocity from ammo if not specified)
    custom_velocity_mps = Column(Numeric(10, 2), nullable=True)
    
    # Audit
    created_by_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Batch tracking for grouping related anchor points
    batch_id = Column(UUID(as_uuid=True), nullable=True)


class AnchorPointLayer(Base):
    __tablename__ = "anchor_point_layers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    anchor_point_id = Column(UUID(as_uuid=True), ForeignKey('anchor_points.id', ondelete='CASCADE'), nullable=False)
    material_id = Column(UUID(as_uuid=True), ForeignKey('materials.id'), nullable=False)
    layer_count = Column(Integer, nullable=False, default=1)
    layer_index = Column(Integer, nullable=False)  # Order in the composition
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
