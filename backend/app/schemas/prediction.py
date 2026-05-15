from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Any, Optional


class PredictionBase(BaseModel):
    model_run_id: Optional[UUID] = None
    requested_by: Optional[UUID] = None
    input_json: dict[str, Any]
    predicted_bfd_mm: Optional[Decimal] = None
    prediction_interval_low_mm: Optional[Decimal] = None
    prediction_interval_high_mm: Optional[Decimal] = None
    probability_bfd_gt_44: Optional[Decimal] = None
    probability_penetration: Optional[Decimal] = None
    extrapolation_warning: bool = False
    comparable_shot_count: Optional[int] = None
    output_json: dict[str, Any] | None = None


class PredictionCreate(PredictionBase):
    pass


class PredictionInDB(PredictionBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class Prediction(PredictionInDB):
    pass
