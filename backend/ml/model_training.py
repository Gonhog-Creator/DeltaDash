"""
Model Training Service for BFD Prediction
Trains XGBoost model for backface deformation prediction
"""
import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler, LabelEncoder

from app.db.session import SessionLocal
from app.db.models.model_run import ModelRun
from app.db.models.shot import Shot
from ml.feature_engineering import FeatureEngineer


class ModelTrainer:
    """Trains XGBoost model for BFD prediction"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.feature_engineer = FeatureEngineer(self.db)
        self.model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        os.makedirs(self.model_dir, exist_ok=True)
    
    def prepare_training_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from database
        
        Returns:
            Tuple of (X features, y targets)
        """
        features_list, targets_list = self.feature_engineer.extract_training_data()
        
        if not features_list:
            raise ValueError("No training data found in database")
        
        # Convert to DataFrame
        df = pd.DataFrame(features_list)
        
        # Encode categorical features
        categorical_cols = df.select_dtypes(include=['object']).columns
        label_encoders = {}
        
        for col in categorical_cols:
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            label_encoders[col] = le
        
        # Convert targets to Series
        y = pd.Series(targets_list)
        
        return df, y
    
    def train_model(self, 
                   n_estimators: int = 100,
                   max_depth: int = 6,
                   learning_rate: float = 0.1,
                   test_size: float = 0.2) -> Dict:
        """
        Train XGBoost model for BFD prediction
        
        Args:
            n_estimators: Number of trees in XGBoost
            max_depth: Maximum depth of trees
            learning_rate: Learning rate for XGBoost
            test_size: Proportion of data for testing
            
        Returns:
            Dictionary of training results
        """
        # Prepare data
        X, y = self.prepare_training_data()
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model
        model = XGBRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=42,
            objective='reg:squarederror'
        )
        
        model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = model.predict(X_test_scaled)
        
        metrics = {
            'rmse': np.sqrt(mean_squared_error(y_test, y_pred)),
            'mae': mean_absolute_error(y_test, y_pred),
            'r2': r2_score(y_test, y_pred),
            'training_samples': len(X_train),
            'test_samples': len(X_test)
        }
        
        # Cross-validation
        cv_scores = cross_val_score(
            model, X_train_scaled, y_train, cv=5, scoring='neg_mean_squared_error'
        )
        metrics['cv_rmse'] = np.sqrt(-cv_scores.mean())
        metrics['cv_rmse_std'] = np.sqrt(-cv_scores).std()
        
        # Feature importance
        feature_importance = dict(zip(X.columns, model.feature_importances_))
        metrics['feature_importance'] = feature_importance
        
        # Save model
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_filename = f'bfd_predictor_{timestamp}.pkl'
        model_path = os.path.join(self.model_dir, model_filename)
        
        # Save model and scaler
        joblib.dump({
            'model': model,
            'scaler': scaler,
            'feature_columns': X.columns.tolist(),
            'feature_importance': feature_importance,
            'metrics': metrics,
            'training_date': timestamp
        }, model_path)
        
        # Log to database
        model_run = ModelRun(
            model_name='bfd_predictor',
            model_type='XGBoostRegressor',
            version=timestamp,
            training_started_at=datetime.now(),
            training_completed_at=datetime.now(),
            training_row_count=len(X),
            metrics_json=metrics,
            artifact_path=model_path
        )
        
        self.db.add(model_run)
        self.db.commit()
        
        metrics['model_run_id'] = str(model_run.id)
        metrics['model_path'] = model_path
        metrics['version'] = timestamp
        
        return metrics
    
    def get_current_model(self) -> Optional[Dict]:
        """
        Get the current trained model
        
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
    
    def retrain_model(self, **kwargs) -> Dict:
        """
        Retrain the model with current data
        
        Returns:
            Dictionary of training results
        """
        return self.train_model(**kwargs)
