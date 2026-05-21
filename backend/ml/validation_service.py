"""
Validation Service for BFD Prediction
Compares predictions against actual test results and tracks model performance
"""
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.prediction import Prediction
from app.db.models.shot import Shot
from app.db.models.model_run import ModelRun


class ValidationService:
    """Validates model predictions against actual test results"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
    
    def validate_predictions(self, 
                           model_run_id: Optional[str] = None,
                           date_range_days: int = 30) -> Dict:
        """
        Validate predictions against actual test results
        
        Args:
            model_run_id: ID of model run to validate (None for current model)
            date_range_days: Number of days to look back for validation
            
        Returns:
            Dictionary of validation metrics
        """
        # Get model run
        if model_run_id:
            model_run = self.db.query(ModelRun).filter(
                ModelRun.id == model_run_id
            ).first()
        else:
            model_run = self.db.query(ModelRun).filter(
                ModelRun.model_name == 'bfd_predictor'
            ).order_by(ModelRun.created_at.desc()).first()
        
        if not model_run:
            raise ValueError("Model run not found")
        
        # Get predictions within date range
        cutoff_date = datetime.now() - timedelta(days=date_range_days)
        
        predictions = self.db.query(Prediction).filter(
            Prediction.model_run_id == model_run.id,
            Prediction.created_at >= cutoff_date
        ).all()
        
        if not predictions:
            return {
                'model_run_id': str(model_run.id),
                'validation_count': 0,
                'message': 'No predictions found for validation'
            }
        
        # Match predictions with actual shots
        validation_results = []
        
        for prediction in predictions:
            # Try to find a shot that matches the prediction
            # This is simplified - in production, use more sophisticated matching
            input_data = prediction.input_json
            
            # Look for shot with matching vest_id and ammunition_id
            shot = self.db.query(Shot).filter(
                Shot.vest_id == input_data.get('vest_id'),
                Shot.ammunition_id == input_data.get('ammunition_id'),
                Shot.bfd_mm.isnot_(None)
            ).first()
            
            if shot:
                error = abs(float(prediction.predicted_bfd_mm) - float(shot.bfd_mm))
                validation_results.append({
                    'prediction_id': str(prediction.id),
                    'predicted_bfd': float(prediction.predicted_bfd_mm),
                    'actual_bfd': float(shot.bfd_mm),
                    'error_mm': error
                })
        
        if not validation_results:
            return {
                'model_run_id': str(model_run.id),
                'validation_count': 0,
                'message': 'No matching shots found for validation'
            }
        
        # Calculate metrics
        errors = [r['error_mm'] for r in validation_results]
        
        metrics = {
            'model_run_id': str(model_run.id),
            'validation_count': len(validation_results),
            'rmse': np.sqrt(np.mean([e ** 2 for e in errors])),
            'mae': np.mean(errors),
            'max_error': max(errors),
            'min_error': min(errors),
            'within_2mm': sum(1 for e in errors if e <= 2.0),
            'within_2mm_percent': (sum(1 for e in errors if e <= 2.0) / len(errors)) * 100,
            'validation_date': datetime.now().isoformat()
        }
        
        return metrics
    
    def detect_model_drift(self, 
                          model_run_id: Optional[str] = None,
                          threshold_rmse: float = 3.0) -> Dict:
        """
        Detect if model performance has degraded
        
        Args:
            model_run_id: ID of model run to check
            threshold_rmse: RMSE threshold for drift detection
            
        Returns:
            Dictionary with drift detection results
        """
        # Get model run metrics
        if model_run_id:
            model_run = self.db.query(ModelRun).filter(
                ModelRun.id == model_run_id
            ).first()
        else:
            model_run = self.db.query(ModelRun).filter(
                ModelRun.model_name == 'bfd_predictor'
            ).order_by(ModelRun.created_at.desc()).first()
        
        if not model_run or not model_run.metrics_json:
            return {
                'drift_detected': False,
                'message': 'No model metrics found'
            }
        
        training_rmse = model_run.metrics_json.get('rmse', 0)
        
        # Validate current performance
        validation_metrics = self.validate_predictions(model_run_id=model_run.id)
        
        if validation_metrics.get('validation_count', 0) == 0:
            return {
                'drift_detected': False,
                'message': 'Insufficient validation data'
            }
        
        current_rmse = validation_metrics.get('rmse', 0)
        
        # Detect drift
        drift_detected = current_rmse > training_rmse * 1.5 or current_rmse > threshold_rmse
        
        result = {
            'drift_detected': drift_detected,
            'training_rmse': training_rmse,
            'current_rmse': current_rmse,
            'rmse_increase': current_rmse - training_rmse,
            'rmse_increase_percent': ((current_rmse - training_rmse) / training_rmse * 100) if training_rmse > 0 else 0,
            'threshold_rmse': threshold_rmse,
            'validation_count': validation_metrics.get('validation_count', 0)
        }
        
        return result
    
    def get_model_performance_history(self, 
                                    model_run_id: str,
                                    days: int = 30) -> List[Dict]:
        """
        Get model performance over time
        
        Args:
            model_run_id: ID of model run
            days: Number of days to look back
            
        Returns:
            List of performance metrics over time
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        predictions = self.db.query(Prediction).filter(
            Prediction.model_run_id == model_run_id,
            Prediction.created_at >= cutoff_date
        ).order_by(Prediction.created_at).all()
        
        history = []
        
        for prediction in predictions:
            history.append({
                'date': prediction.created_at.isoformat(),
                'predicted_bfd': float(prediction.predicted_bfd_mm),
                'confidence_interval': {
                    'low': float(prediction.prediction_interval_low_mm),
                    'high': float(prediction.prediction_interval_high_mm)
                },
                'extrapolation_warning': prediction.extrapolation_warning,
                'comparable_shot_count': prediction.comparable_shot_count
            })
        
        return history
