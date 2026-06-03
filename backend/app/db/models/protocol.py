from sqlalchemy import Column, String, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.db.base import Base


class Protocol(Base):
    __tablename__ = "protocols"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    # Protocol levels configuration
    # Format: [
    #   {
    #     "level_name": "RB1",
    #     "ammunition_config": [
    #       {
    #         "ammunition_id": "uuid",
    #         "reference_velocity_m_s": float,
    #         "velocity_window_m_s": float,  # plus/minus value
    #         "shots_per_panel": int
    #       }
    #     ]
    #   }
    # ]
    levels_config = Column(JSON, nullable=True)
