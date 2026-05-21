"""
ML API endpoints for BFD prediction
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.db.models.user import User
from app.api.v1.auth import get_current_user
from ml.prediction_service import PredictionService
from ml.model_training import ModelTrainer
from ml.validation_service import ValidationService
from ml.model_management import ModelManager


router = APIRouter()


class BFDPredictionRequest(BaseModel):
    vest_id: str = Field(..., description="ID of the vest")
    ammunition_id: str = Field(..., description="ID of the ammunition")
    velocity_m_s: float = Field(..., description="Impact velocity in m/s")
    impact_angle_degrees: float = Field(0.0, description="Impact angle in degrees")


class BFDPredictionResponse(BaseModel):
    predicted_bfd_mm: float
    confidence_interval_low_mm: float
    confidence_interval_high_mm: float
    comparable_shot_count: int
    extrapolation_warning: bool
    feature_importance: dict
    model_version: str


class ModelTrainRequest(BaseModel):
    n_estimators: int = Field(100, description="Number of trees in XGBoost")
    max_depth: int = Field(6, description="Maximum depth of trees")
    learning_rate: float = Field(0.1, description="Learning rate for XGBoost")
    test_size: float = Field(0.2, description="Proportion of data for testing")


@router.post("/predictions/bfd", response_model=BFDPredictionResponse)
def predict_bfd(
    request: BFDPredictionRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Predict BFD for a given vest and ammunition configuration
    """
    try:
        prediction_service = PredictionService(db)
        
        result = prediction_service.predict_bfd(
            vest_id=request.vest_id,
            ammunition_id=request.ammunition_id,
            velocity_m_s=request.velocity_m_s,
            impact_angle_degrees=request.impact_angle_degrees
        )
        
        # Log prediction to database
        prediction_service.log_prediction(
            input_json=request.dict(),
            result=result,
            user_id=str(current_user.id) if current_user else None
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/models/train")
def train_model(
    request: ModelTrainRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Train a new BFD prediction model (admin only)
    """
    # TODO: Add admin role check
    
    try:
        trainer = ModelTrainer(db)
        
        result = trainer.train_model(
            n_estimators=request.n_estimators,
            max_depth=request.max_depth,
            learning_rate=request.learning_rate,
            test_size=request.test_size
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Training failed: {str(e)}")


@router.get("/models/current")
def get_current_model(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get information about the current model
    """
    try:
        manager = ModelManager(db)
        model_info = manager.get_current_model()
        
        if not model_info:
            raise HTTPException(status_code=404, detail="No trained model found")
        
        return model_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model info: {str(e)}")


@router.post("/models/validate")
def validate_model(
    model_run_id: Optional[str] = None,
    date_range_days: int = 30,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Validate model predictions against actual test results
    """
    try:
        validation_service = ValidationService(db)
        
        result = validation_service.validate_predictions(
            model_run_id=model_run_id,
            date_range_days=date_range_days
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.get("/models/versions")
def get_model_versions(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get all versions of the BFD prediction model
    """
    try:
        manager = ModelManager(db)
        versions = manager.get_model_versions()
        
        return {"versions": versions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get model versions: {str(e)}")
