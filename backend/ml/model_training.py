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
from app.services.ml.ballistic_ml import fetch_training_data, add_engineered_features


class ModelTrainer:
    """Trains XGBoost model for BFD prediction"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        # Use Railway persistent storage if enabled
        if os.getenv('USE_RAILWAY_STORAGE') == 'true':
            self.model_dir = '/app/storage/model_artifacts/ballistic'
        else:
            backend_dir = os.path.dirname(os.path.dirname(__file__))
            self.model_dir = os.path.join(backend_dir, 'storage', 'model_artifacts', 'ballistic')
        os.makedirs(self.model_dir, exist_ok=True)
    
    def prepare_training_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data from database using existing feature engineering
        
        Returns:
            Tuple of (X features, y targets)
        """
        # Use existing fetch_training_data from ballistic_ml
        from app.services.ml.data_fetcher import fetch_material_properties
        
        df = fetch_training_data(self.db)
        
        if df is None or df.empty:
            raise ValueError("No training data found in database")
        
        # Get material properties for feature engineering
        material_properties = fetch_material_properties(self.db)
        
        # Add engineered features using existing system
        df = add_engineered_features(df, material_properties, validate=False)
        
        # Separate features and target
        target_col = 'backface_deformation_mm'
        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found in training data")
        
        # Remove rows with missing target
        df = df.dropna(subset=[target_col])
        
        # Separate features and target
        y = df[target_col]
        X = df.drop(columns=[target_col])
        
        # Encode categorical features
        categorical_cols = X.select_dtypes(include=['object']).columns
        label_encoders = {}
        
        for col in categorical_cols:
            le = LabelEncoder()
            X[col] = le.fit_transform(X[col].astype(str))
            label_encoders[col] = le
        
        # Fill missing values with 0
        X = X.fillna(0)
        
        return X, y
    
    def train_model(self,
                   n_estimators: int = 300,
                   max_depth: int = 6,
                   learning_rate: float = 0.05,
                   test_size: float = 0.2,
                   subsample: float = 0.8,
                   colsample_bytree: float = 0.8,
                   min_child_weight: int = 3,
                   gamma: float = 0,
                   reg_alpha: float = 0,
                   reg_lambda: float = 1) -> Dict:
        """
        Train XGBoost model for BFD prediction
        
        Args:
            n_estimators: Number of trees in XGBoost
            max_depth: Maximum depth of trees
            learning_rate: Learning rate for XGBoost
            test_size: Proportion of data for testing
            subsample: Subsample ratio of training instances
            colsample_bytree: Subsample ratio of columns when constructing each tree
            min_child_weight: Minimum sum of instance weight needed in a child
            gamma: Minimum loss reduction required to make a split
            reg_alpha: L1 regularization term on weights
            reg_lambda: L2 regularization term on weights
            
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
            objective='reg:squarederror',
            subsample=subsample,
            colsample_bytree=colsample_bytree,
            min_child_weight=min_child_weight,
            gamma=gamma,
            reg_alpha=reg_alpha,
            reg_lambda=reg_lambda,
            n_jobs=-1,  # Use all available CPU cores
            tree_method='hist',  # Faster histogram-based algorithm
            enable_categorical=False,  # Disable categorical optimization for speed
        )
        
        model.fit(X_train_scaled, y_train)
        
        # Evaluate on test split
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
        
        # Create version directory
        version_dir = os.path.join(self.model_dir, 'versions', timestamp)
        os.makedirs(version_dir, exist_ok=True)
        
        # Save model, scaler, and metadata separately (matching prediction_service format)
        joblib.dump(model, os.path.join(version_dir, 'backface_deformation_mm.pkl'))
        joblib.dump(scaler, os.path.join(version_dir, 'preprocessor.pkl'))
        
        # Save metadata
        metadata = {
            'version': timestamp,
            'feature_columns': X.columns.tolist(),
            'feature_importance': feature_importance,
            'metrics': metrics,
            'training_date': timestamp,
            'model_type': 'XGBoostRegressor',
            'model_name': 'bfd_predictor'
        }
        
        with open(os.path.join(version_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Also save as current model (copy to main directory)
        joblib.dump(model, os.path.join(self.model_dir, 'backface_deformation_mm.pkl'))
        joblib.dump(scaler, os.path.join(self.model_dir, 'preprocessor.pkl'))
        with open(os.path.join(self.model_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        model_path = version_dir
        
        # Now evaluate on test session data (same as manual health check)
        try:
            from app.services.ml.ballistic_ml import evaluate_model_on_test_sessions
            health_check_results = evaluate_model_on_test_sessions(self.db, version=None, protocol_filter=None)
            
            if health_check_results.get('total_points', 0) > 0:
                # Calculate average error from health check results
                point_data = health_check_results.get('point_data', [])
                if point_data:
                    errors = [abs(point.get('predicted', 0) - point.get('actual', 0)) 
                             for point in point_data if point.get('actual') is not None]
                    if errors:
                        metrics['health_check_mae'] = np.mean(errors)
                        metrics['health_check_rmse'] = np.sqrt(np.mean([e**2 for e in errors]))
                        metrics['health_check_points'] = len(errors)
        except Exception as e:
            # If health check fails, continue with training metrics
            print(f"Warning: Could not run health check evaluation: {str(e)}")
        
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
        
        # Create version directory
        version_dir = os.path.join(self.model_dir, 'versions', timestamp)
        os.makedirs(version_dir, exist_ok=True)
        
        # Save model, scaler, and metadata separately (matching prediction_service format)
        joblib.dump(model, os.path.join(version_dir, 'backface_deformation_mm.pkl'))
        joblib.dump(scaler, os.path.join(version_dir, 'preprocessor.pkl'))
        
        # Save metadata
        metadata = {
            'version': timestamp,
            'feature_columns': X.columns.tolist(),
            'feature_importance': feature_importance,
            'metrics': metrics,
            'training_date': timestamp,
            'model_type': 'XGBoostRegressor',
            'model_name': 'bfd_predictor'
        }
        
        with open(os.path.join(version_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Also save as current model (copy to main directory)
        joblib.dump(model, os.path.join(self.model_dir, 'backface_deformation_mm.pkl'))
        joblib.dump(scaler, os.path.join(self.model_dir, 'preprocessor.pkl'))
        with open(os.path.join(self.model_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        model_path = version_dir
        
        # Log to database
        # Save model and preprocessor as binary data for Railway persistence
        import io
        model_buffer = io.BytesIO()
        joblib.dump(model, model_buffer)
        model_buffer.seek(0)
        
        preprocessor_buffer = io.BytesIO()
        joblib.dump(scaler, preprocessor_buffer)
        preprocessor_buffer.seek(0)
        
        model_run = ModelRun(
            model_name='bfd_predictor',
            model_type='XGBoostRegressor',
            version=timestamp,
            training_started_at=datetime.now(),
            training_completed_at=datetime.now(),
            training_row_count=len(X),
            metrics_json=metrics,
            artifact_path=model_path,
            model_file=model_buffer.read(),
            preprocessor_file=preprocessor_buffer.read()
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
