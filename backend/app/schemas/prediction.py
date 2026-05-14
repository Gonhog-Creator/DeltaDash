from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from typing import Any


class PredictionBase(BaseModel):
    model_run_id: UUID | None = None
    requested_by: UUID | None = None
    input_json: dict[str, Any]
    predicted_bfd_mm: Decimal | None = None
    prediction_interval_low_mm: Decimal | None = None
    prediction_interval_high_mm: Decimal | None = None
    probability_bfd_gt_44: Decimal | None = None
    probability_penetration: Decimal | None = None
    extrapolation_warning: bool = False
    comparable_shot_count: int | None = None
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
