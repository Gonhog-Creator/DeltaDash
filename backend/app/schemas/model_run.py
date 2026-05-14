from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Any


class ModelRunBase(BaseModel):
    model_name: str
    model_type: str
    version: str
    training_started_at: datetime | None = None
    training_completed_at: datetime | None = None
    training_row_count: int | None = None
    formula: str | None = None
    metrics_json: dict[str, Any] | None = None
    artifact_path: str | None = None
    notes: str | None = None
    created_by: UUID | None = None


class ModelRunCreate(ModelRunBase):
    pass


class ModelRunInDB(ModelRunBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class ModelRun(ModelRunInDB):
    pass
