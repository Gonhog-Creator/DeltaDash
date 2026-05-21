"""
Model Management Service for BFD Prediction
Manages model lifecycle, versioning, and A/B testing
"""
import os
import shutil
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.model_run import ModelRun


class ModelManager:
    """Manages model lifecycle and versioning"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
        os.makedirs(self.model_dir, exist_ok=True)
    
    def get_model_versions(self, model_name: str = 'bfd_predictor') -> List[Dict]:
        """
        Get all versions of a model
        
        Args:
            model_name: Name of the model
            
        Returns:
            List of model version information
        """
        model_runs = self.db.query(ModelRun).filter(
            ModelRun.model_name == model_name
        ).order_by(ModelRun.created_at.desc()).all()
        
        versions = []
        for run in model_runs:
            versions.append({
                'id': str(run.id),
                'version': run.version,
                'created_at': run.created_at.isoformat(),
                'training_row_count': run.training_row_count,
                'metrics': run.metrics_json,
                'artifact_path': run.artifact_path,
                'is_current': run == model_runs[0]  # First one is current
            })
        
        return versions
    
    def get_current_model(self, model_name: str = 'bfd_predictor') -> Optional[Dict]:
        """
        Get the current active model
        
        Args:
            model_name: Name of the model
            
        Returns:
            Dictionary with current model information
        """
        model_run = self.db.query(ModelRun).filter(
            ModelRun.model_name == model_name
        ).order_by(ModelRun.created_at.desc()).first()
        
        if not model_run:
            return None
        
        return {
            'id': str(model_run.id),
            'version': model_run.version,
            'created_at': model_run.created_at.isoformat(),
            'training_row_count': model_run.training_row_count,
            'metrics': model_run.metrics_json,
            'artifact_path': model_run.artifact_path
        }
    
    def set_current_model(self, model_run_id: str) -> Dict:
        """
        Set a specific model version as current
        
        Args:
            model_run_id: ID of the model run to set as current
            
        Returns:
            Dictionary with updated model information
        """
        model_run = self.db.query(ModelRun).filter(
            ModelRun.id == model_run_id
        ).first()
        
        if not model_run:
            raise ValueError(f"Model run {model_run_id} not found")
        
        # In a more sophisticated system, this would update a "current_model" table
        # For now, the "current" model is simply the most recently created one
        # This method is a placeholder for future enhancement
        
        return {
            'id': str(model_run.id),
            'version': model_run.version,
            'message': 'Model marked as current (placeholder implementation)'
        }
    
    def rollback_model(self, model_run_id: str) -> Dict:
        """
        Rollback to a previous model version
        
        Args:
            model_run_id: ID of the model run to rollback to
            
        Returns:
            Dictionary with rollback information
        """
        model_run = self.db.query(ModelRun).filter(
            ModelRun.id == model_run_id
        ).first()
        
        if not model_run:
            raise ValueError(f"Model run {model_run_id} not found")
        
        # For now, this is a placeholder
        # In production, this would:
        # 1. Copy the model artifact to a "current" location
        # 2. Update a "current_model" table
        # 3. Log the rollback event
        
        return {
            'rolled_back_to': str(model_run.id),
            'version': model_run.version,
            'message': 'Rollback completed (placeholder implementation)'
        }
    
    def delete_model(self, model_run_id: str, delete_artifact: bool = False) -> Dict:
        """
        Delete a model version
        
        Args:
            model_run_id: ID of the model run to delete
            delete_artifact: Whether to delete the model artifact file
            
        Returns:
            Dictionary with deletion information
        """
        model_run = self.db.query(ModelRun).filter(
            ModelRun.id == model_run_id
        ).first()
        
        if not model_run:
            raise ValueError(f"Model run {model_run_id} not found")
        
        artifact_path = model_run.artifact_path
        
        # Delete from database
        self.db.delete(model_run)
        self.db.commit()
        
        # Delete artifact file if requested
        if delete_artifact and artifact_path and os.path.exists(artifact_path):
            os.remove(artifact_path)
        
        return {
            'deleted_id': str(model_run_id),
            'artifact_deleted': delete_artifact,
            'message': 'Model deleted successfully'
        }
    
    def compare_models(self, model_run_ids: List[str]) -> Dict:
        """
        Compare multiple model versions
        
        Args:
            model_run_ids: List of model run IDs to compare
            
        Returns:
            Dictionary with comparison results
        """
        models = []
        
        for model_id in model_run_ids:
            model_run = self.db.query(ModelRun).filter(
                ModelRun.id == model_id
            ).first()
            
            if model_run:
                models.append({
                    'id': str(model_run.id),
                    'version': model_run.version,
                    'created_at': model_run.created_at.isoformat(),
                    'metrics': model_run.metrics_json
                })
        
        if len(models) < 2:
            return {
                'message': 'Need at least 2 models to compare',
                'models': models
            }
        
        # Compare metrics
        comparison = {
            'models': models,
            'comparison': {}
        }
        
        # Compare RMSE
        rmse_values = [m['metrics'].get('rmse', float('inf')) for m in models if m['metrics']]
        if rmse_values:
            comparison['comparison']['best_rmse'] = min(rmse_values)
            comparison['comparison']['worst_rmse'] = max(rmse_values)
        
        # Compare R²
        r2_values = [m['metrics'].get('r2', -float('inf')) for m in models if m['metrics']]
        if r2_values:
            comparison['comparison']['best_r2'] = max(r2_values)
            comparison['comparison']['worst_r2'] = min(r2_values)
        
        return comparison
