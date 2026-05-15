from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Any, Optional


class ModelRunBase(BaseModel):
    model_name: str
    model_type: str
    version: str
    training_started_at: Optional[datetime] = None
    training_completed_at: Optional[datetime] = None
    training_row_count: Optional[int] = None
    formula: Optional[str] = None
    metrics_json: dict[str, Any] | None = None
    artifact_path: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[UUID] = None


class ModelRunCreate(ModelRunBase):
    pass


class ModelRunInDB(ModelRunBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ModelRun(ModelRunInDB):
    pass
