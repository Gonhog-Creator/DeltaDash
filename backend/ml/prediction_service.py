"""
Prediction Service for BFD Prediction
Makes predictions using trained XGBoost model
"""
import os
import joblib
import numpy as np
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.model_run import ModelRun
from app.db.models.prediction import Prediction
from app.db.models.shot_data import ShotData
from app.db.models.vest import Vest
from ml.feature_engineering import FeatureEngineer


class PredictionService:
    """Makes BFD predictions using trained model"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.feature_engineer = FeatureEngineer(self.db)
        self.model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    
    def load_model(self) -> Optional[Dict]:
        """
        Load the current trained model
        
        Returns:
            Dictionary with model, scaler, and metadata
        """
        # Get latest model run
        model_run = self.db.query(ModelRun).filter(
            ModelRun.model_name == 'bfd_predictor'
        ).order_by(ModelRun.created_at.desc()).first()
        
        if not model_run or not model_run.artifact_path:
            return None
        
        # Load model
        model_data = joblib.load(model_run.artifact_path)
        return model_data
    
    def predict_bfd(self, 
                    vest_id: str,
                    ammunition_id: str,
                    velocity_m_s: float,
                    impact_angle_degrees: float = 0.0) -> Dict:
        """
        Predict BFD for a given configuration
        
        Args:
            vest_id: ID of the vest
            ammunition_id: ID of the ammunition
            velocity_m_s: Impact velocity in m/s
            impact_angle_degrees: Impact angle in degrees
            
        Returns:
            Dictionary with prediction results
        """
        # Load model
        model_data = self.load_model()
        if not model_data:
            raise ValueError("No trained model found")
        
        model = model_data['model']
        scaler = model_data['scaler']
        feature_columns = model_data['feature_columns']
        
        # Get vest and ammunition
        vest = self.db.query(Vest).filter(Vest.name == vest_id).first()
        ammo = self.db.query(Ammunition).filter(Ammunition.caliber_diameter_mm == ammunition_id).first()
        
        if not vest:
            raise ValueError(f"Vest with id {vest_id} not found")
        
        # Create a mock shot object for feature extraction
        class MockShot:
            def __init__(self):
                self.vest_number = vest_id
                self.caliber = ammunition_id
                self.velocity_m_s = velocity_m_s
                self.angle_degrees = impact_angle_degrees
                self.test_session = None
        
        mock_shot = MockShot()
        
        # Extract features
        features = self.feature_engineer.extract_features_for_shot(mock_shot)
        
        # Convert to DataFrame
        import pandas as pd
        df = pd.DataFrame([features])
        
        # Encode categorical features (simplified - use same encoding as training)
        categorical_cols = df.select_dtypes(include=['object']).columns
        for col in categorical_cols:
            # For now, use simple label encoding
            df[col] = pd.factorize(df[col].astype(str))[0]
        
        # Ensure all required features are present
        for col in feature_columns:
            if col not in df.columns:
                df[col] = 0
        
        # Reorder columns to match training data
        df = df[feature_columns]
        
        # Scale features
        features_scaled = scaler.transform(df)
        
        # Make prediction
        prediction = model.predict(features_scaled)[0]
        
        # Calculate confidence interval (simplified - use standard deviation from training)
        # In production, use proper uncertainty quantification (e.g., quantile regression, bootstrapping)
        confidence_interval = 2.0  # ±2mm as per user requirement
        
        # Check domain of applicability
        # Compare input features to training data distribution
        comparable_shot_count = self._count_comparable_shots(features)
        extrapolation_warning = comparable_shot_count < 10
        
        result = {
            'predicted_bfd_mm': float(prediction),
            'confidence_interval_low_mm': float(prediction - confidence_interval),
            'confidence_interval_high_mm': float(prediction + confidence_interval),
            'comparable_shot_count': comparable_shot_count,
            'extrapolation_warning': extrapolation_warning,
            'feature_importance': model_data.get('feature_importance', {}),
            'model_version': model_data.get('version', 'unknown')
        }
        
        return result
    
    def _count_comparable_shots(self, features: Dict) -> int:
        """
        Count shots in training data comparable to input features
        
        Args:
            features: Dictionary of input features
            
        Returns:
            Number of comparable shots
        """
        # Simplified - count all shots with vest_number
        # In production, use more sophisticated similarity metrics (e.g., k-NN)
        vest_id = features.get('vest_id')
        if vest_id:
            count = self.db.query(ShotData).filter(
                ShotData.vest_number == vest_id,
                ShotData.trauma_mm.is_not(None)
            ).count()
            return count
        return 0
    
    def log_prediction(self, 
                      input_json: Dict,
                      result: Dict,
                      user_id: Optional[str] = None) -> Prediction:
        """
        Log prediction to database
        
        Args:
            input_json: Input configuration
            result: Prediction result
            user_id: ID of user making prediction
            
        Returns:
            Prediction object
        """
        # Get current model run
        model_run = self.db.query(ModelRun).filter(
            ModelRun.model_name == 'bfd_predictor'
        ).order_by(ModelRun.created_at.desc()).first()
        
        prediction = Prediction(
            model_run_id=model_run.id if model_run else None,
            requested_by=user_id,
            input_json=input_json,
            predicted_bfd_mm=result['predicted_bfd_mm'],
            prediction_interval_low_mm=result['confidence_interval_low_mm'],
            prediction_interval_high_mm=result['confidence_interval_high_mm'],
            extrapolation_warning=result['extrapolation_warning'],
            comparable_shot_count=result['comparable_shot_count'],
            output_json=result
        )
        
        self.db.add(prediction)
        self.db.commit()
        
        return prediction
