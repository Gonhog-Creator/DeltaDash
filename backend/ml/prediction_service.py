"""
Prediction Service for BFD Prediction
Makes predictions using trained XGBoost model
"""
import os
import joblib
import numpy as np
from typing import Dict, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.model_run import ModelRun
from app.db.models.prediction import Prediction
from app.db.models.shot_data import ShotData
from app.db.models.vest import Vest
from app.db.models.vest_layer import VestLayer
from app.db.models.material import Material
from app.db.models.protocol import Protocol as ProtocolModel
from app.db.models.ammunition import Ammunition
from app.services.ml.ballistic_ml import add_engineered_features, fetch_material_properties
from ml.feature_engineering import FeatureEngineer


class PredictionService:
    """Makes BFD predictions using trained model"""
    
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.feature_engineer = FeatureEngineer(self.db)
        self.model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'models')
    
    def load_model(self, version: str = None) -> Optional[Dict]:
        """
        Load the current trained model from file system
        
        Args:
            version: Optional version string to load a specific model version
        
        Returns:
            Dictionary with model, scaler, and metadata
        """
        import os
        import json
        import joblib
        
        # Model directory - prediction_service.py is in backend/ml, so we need to go up to backend
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        model_dir = os.path.join(backend_dir, "storage", "model_artifacts", "ballistic")
        
        # Load metadata
        metadata_path = os.path.join(model_dir, "metadata.json")
        if not os.path.exists(metadata_path):
            return None
        
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        
        # If version is specified, load that version
        if version:
            version_dir = os.path.join(model_dir, "versions", version)
            if not os.path.exists(version_dir):
                return None
            version_metadata_path = os.path.join(version_dir, "metadata.json")
            with open(version_metadata_path, "r") as f:
                metadata = json.load(f)
            preprocessor_path = os.path.join(version_dir, "preprocessor.pkl")
            model_path = os.path.join(version_dir, "backface_deformation_mm.pkl")
        else:
            # Load current model
            preprocessor_path = os.path.join(model_dir, "preprocessor.pkl")
            model_path = os.path.join(model_dir, "backface_deformation_mm.pkl")
        
        # Load preprocessor
        if not os.path.exists(preprocessor_path):
            return None
        
        preprocessor = joblib.load(preprocessor_path)
        
        # Load model
        if not os.path.exists(model_path):
            return None

        loaded = joblib.load(model_path)

        # Handle new dict structure with log transform flag
        if isinstance(loaded, dict) and "model" in loaded:
            actual_model = loaded["model"]
            use_log_transform = loaded.get("use_log_transform", False)
        else:
            actual_model = loaded
            use_log_transform = False

        # Try to load perforation classifier
        perforation_model = None
        perforation_path = os.path.join(model_dir if not version else version_dir, "perforated.pkl")
        if os.path.exists(perforation_path):
            perforation_loaded = joblib.load(perforation_path)
            if isinstance(perforation_loaded, dict) and "model" in perforation_loaded:
                perforation_model = perforation_loaded["model"]
            else:
                perforation_model = perforation_loaded

        # Return model data
        return {
            'model': actual_model,
            'perforation_model': perforation_model,
            'scaler': preprocessor,
            'feature_columns': metadata.get('feature_columns', []),
            'version': metadata.get('version', 'unknown'),
            'use_log_transform': use_log_transform,
        }
    
    def predict_bfd_for_protocol(self, 
                                  vest_id: str,
                                  protocol_id: str,
                                  level_index: int = None,
                                  version: str = None) -> Dict:
        """
        Predict BFD for a vest using a protocol (optionally for a specific level)
        
        Args:
            vest_id: ID of the vest
            protocol_id: ID of the protocol
            level_index: Optional index of the protocol level to predict for
            version: Optional version string to use a specific model version
            
        Returns:
            Dictionary with prediction results for all shots in the protocol/level
        """
        # Get protocol
        protocol = self.db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
        if not protocol:
            raise ValueError(f"Protocol with id {protocol_id} not found")
        
        if not protocol.levels_config:
            raise ValueError(f"Protocol {protocol.name} has no levels configuration")
        
        # Get vest
        vest = self.db.query(Vest).filter(Vest.id == vest_id).first()
        if not vest:
            raise ValueError(f"Vest with id {vest_id} not found")

        # Load model
        model_data = self.load_model(version)
        if not model_data:
            raise ValueError("No trained model found")

        model = model_data['model']
        perforation_model = model_data.get('perforation_model')
        scaler = model_data['scaler']
        feature_columns = model_data['feature_columns']
        use_log_transform = model_data.get('use_log_transform', False)

        # Determine which levels to process
        if level_index is not None:
            if level_index < 0 or level_index >= len(protocol.levels_config):
                raise ValueError(f"Invalid level index {level_index} for protocol {protocol.name}")
            levels_to_process = [protocol.levels_config[level_index]]
            level_name = levels_to_process[0].get('level_name', f'Level {level_index + 1}')
        else:
            levels_to_process = protocol.levels_config
            level_name = 'All Levels'
        
        # Generate predictions for all shots in the selected level(s)
        all_predictions = []
        
        for level in levels_to_process:
            level_name = level.get('level_name', 'Unknown Level')
            ammunition_config = level.get('ammunition_config', [])
            
            for ammo_config in ammunition_config:
                ammo_id = ammo_config.get('ammunition_id')
                reference_velocity = ammo_config.get('reference_velocity_m_s')
                shots_per_panel = ammo_config.get('shots_per_panel', 6)
                
                # Get ammunition
                ammo = self.db.query(Ammunition).filter(Ammunition.id == ammo_id).first()
                if not ammo:
                    raise ValueError(f"Ammunition with id {ammo_id} not found")
                
                # Generate predictions for all conditions: front/back, dry/wet
                conditions = [
                    {'side': 'front', 'conditioning': 'dry'},
                    {'side': 'front', 'conditioning': 'wet'},
                    {'side': 'back', 'conditioning': 'dry'},
                    {'side': 'back', 'conditioning': 'wet'},
                ]
                
                for condition in conditions:
                    for shot_num in range(shots_per_panel):
                        # Create a feature dictionary matching training format
                        import pandas as pd
                        
                        # Get material properties for feature engineering
                        material_properties = fetch_material_properties(self.db)
                        
                        # Build vest composition string from vest layers
                        vest_layers = self.db.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
                        composition_parts = []
                        for layer in sorted(vest_layers, key=lambda x: x.layer_index or 0):
                            material = self.db.query(Material).filter(Material.id == layer.material_id).first()
                            if material:
                                count = layer.layer_count or 1
                                composition_parts.append(f"{count} {material.name}")
                        
                        vest_composition = " + ".join(composition_parts) if composition_parts else ""
                        
                        # Create feature row matching training format
                        features = {
                            'vest_composition': vest_composition,
                            'material_thickness_mm': float(vest.total_thickness_mm) if vest.total_thickness_mm else 0,
                            'material_weight_g_m2': 0,  # Will be calculated from composition
                            'number_of_layers': vest.total_layers if vest.total_layers else 0,
                            'ammunition_used': ammo.name if ammo else ammo.caliber,
                            'threat_level': vest.threat_level if vest else None,
                            'shot_number': shot_num + 1,
                            'impact_velocity_mps': reference_velocity,
                            'impact_angle_deg': 0.0,
                            'bullet_mass_g': float(ammo.projectile_mass_grams) if ammo and ammo.projectile_mass_grams else 0,
                            'temperature_c': 20.0,
                            'humidity_pct': 50.0,
                            'condition': condition['conditioning'],
                            'panel_side': condition['side'],
                            'material_type': None,  # Will be extracted from composition
                        }
                        
                        # Convert to DataFrame and apply engineering features
                        df = pd.DataFrame([features])
                        df = add_engineered_features(df, material_properties, validate=False)
                        
                        # Encode categorical features (simple label encoding)
                        categorical_cols = df.select_dtypes(include=['object']).columns
                        for col in categorical_cols:
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

                        # Apply inverse transform if log transform was used
                        if use_log_transform:
                            prediction = float(np.expm1(prediction))

                        # Predict perforation if classifier is available
                        perforation_probability = None
                        if perforation_model:
                            perforation_probability = float(perforation_model.predict_proba(features_scaled)[0, 1])

                        # Calculate confidence interval
                        confidence_interval = 2.0  # ±2mm

                        # Check domain of applicability
                        comparable_shot_count = self._count_comparable_shots(features)
                        extrapolation_warning = comparable_shot_count < 10

                        prediction_result = {
                            'shot_number': shot_num + 1,
                            'level_name': level_name,
                            'side': condition['side'],
                            'conditioning': condition['conditioning'],
                            'ammunition_id': ammo_id,
                            'ammunition_name': ammo.name if ammo.name else ammo.caliber,
                            'reference_velocity_m_s': reference_velocity,
                            'predicted_bfd_mm': float(prediction),
                            'perforation_probability': perforation_probability,
                            'confidence_interval_low_mm': float(prediction - confidence_interval),
                            'confidence_interval_high_mm': float(prediction + confidence_interval),
                            'comparable_shot_count': comparable_shot_count,
                            'extrapolation_warning': extrapolation_warning,
                        }
                        
                        all_predictions.append(prediction_result)
        
        # Calculate summary statistics
        all_bfd_values = [p['predicted_bfd_mm'] for p in all_predictions]
        first_3_bfd_values = all_bfd_values[:3] if len(all_bfd_values) >= 3 else all_bfd_values

        # Generate velocity curves for each shot number
        velocity_curves = {}
        velocity_range = [200, 250, 300, 350, 400, 450, 500]  # m/s
        
        # Use a representative bullet mass from ammunition (assumed constant for a given ammo type)
        bullet_mass = 0
        if ammo:
            if ammo.projectile_mass_grams:
                bullet_mass = float(ammo.projectile_mass_grams)
            elif ammo.projectile_mass_grains:
                bullet_mass = float(ammo.projectile_mass_grains) / 15.432
        
        # If still no bullet mass, use a reasonable default (9mm FMJ ~8g)
        if bullet_mass == 0:
            bullet_mass = 8.0
        
        # Group predictions by shot number
        shot_predictions = {}
        for pred in all_predictions:
            shot_num = pred['shot_number']
            if shot_num not in shot_predictions:
                shot_predictions[shot_num] = pred
        
        # Generate velocity curves for each shot number
        for shot_num in sorted(shot_predictions.keys()):
            base_pred = shot_predictions[shot_num]
            curve_data = []
            for velocity in velocity_range:
                # Re-run prediction for this velocity
                try:
                    # Re-extract features with new velocity
                    features = {
                        'vest_composition': vest_composition,
                        'material_thickness_mm': float(vest.total_thickness_mm) if vest.total_thickness_mm else 0,
                        'material_weight_g_m2': 0,
                        'number_of_layers': vest.total_layers if vest.total_layers else 0,
                        'ammunition_used': ammo.name if ammo else ammo.caliber,
                        'threat_level': vest.threat_level if vest else None,
                        'shot_number': base_pred['shot_number'],
                        'impact_velocity_mps': velocity,
                        'impact_angle_deg': 0.0,
                        'bullet_mass_g': bullet_mass,
                        'temperature_c': 20.0,
                        'humidity_pct': 50.0,
                        'condition': base_pred['conditioning'],
                        'panel_side': base_pred['side'],
                        'material_type': None,
                    }
                    
                    df = pd.DataFrame([features])
                    df = add_engineered_features(df, material_properties, validate=False)
                    
                    categorical_cols = df.select_dtypes(include=['object']).columns
                    for col in categorical_cols:
                        df[col] = pd.factorize(df[col].astype(str))[0]
                    
                    for col in feature_columns:
                        if col not in df.columns:
                            df[col] = 0
                    
                    df = df[feature_columns]
                    features_scaled = scaler.transform(df)
                    prediction = model.predict(features_scaled)[0]

                    # Apply inverse transform if log transform was used
                    if use_log_transform:
                        prediction = float(np.expm1(prediction))

                    curve_data.append({
                        'velocity_mps': velocity,
                        'predicted_bfd_mm': float(prediction)
                    })
                except Exception as e:
                    print(f"Error generating velocity curve point: {e}")
                    curve_data.append({
                        'velocity_mps': velocity,
                        'predicted_bfd_mm': 0.0
                    })
            
            velocity_curves[str(shot_num)] = curve_data
        
        summary = {
            'protocol_id': protocol_id,
            'protocol_name': protocol.name,
            'vest_id': vest_id,
            'vest_code': vest.vest_code,
            'level_name': level_name,
            'total_shots': len(all_predictions),
            'predictions': all_predictions,
            'summary': {
                'mean_bfd_mm': float(np.mean(first_3_bfd_values)),
                'max_bfd_mm': float(np.max(all_bfd_values)),
                'min_bfd_mm': float(np.min(all_bfd_values)),
                'std_bfd_mm': float(np.std(all_bfd_values)),
            },
            'model_version': model_data.get('version', 'unknown'),
            'velocity_curves': velocity_curves,
        }
        
        return summary

    def predict_bfd_for_custom_vest(self,
                                     custom_vest: Dict,
                                     protocol_id: str,
                                     level_index: int = None,
                                     version: str = None) -> Dict:
        """
        Predict BFD for a custom vest using a protocol (optionally for a specific level)

        Args:
            custom_vest: Dictionary with custom vest configuration (layers, vest_type, etc.)
            protocol_id: ID of the protocol
            level_index: Optional index of the protocol level to predict for
            version: Optional version string to use a specific model version

        Returns:
            Dictionary with prediction results for all shots in the protocol/level
        """
        # Get protocol
        protocol = self.db.query(ProtocolModel).filter(ProtocolModel.id == protocol_id).first()
        if not protocol:
            raise ValueError(f"Protocol with id {protocol_id} not found")

        if not protocol.levels_config:
            raise ValueError(f"Protocol {protocol.name} has no levels configuration")

        # Load model
        model_data = self.load_model(version)
        if not model_data:
            raise ValueError("No trained model found")

        model = model_data['model']
        perforation_model = model_data.get('perforation_model')
        scaler = model_data['scaler']
        feature_columns = model_data['feature_columns']
        use_log_transform = model_data.get('use_log_transform', False)

        # Determine which levels to process
        if level_index is not None:
            if level_index < 0 or level_index >= len(protocol.levels_config):
                raise ValueError(f"Invalid level index {level_index} for protocol {protocol.name}")
            levels_to_process = [protocol.levels_config[level_index]]
            level_name = levels_to_process[0].get('level_name', f'Level {level_index + 1}')
        else:
            levels_to_process = protocol.levels_config
            level_name = 'All Levels'

        # Build vest composition string from custom vest layers
        vest_layers = custom_vest.get('layers', [])
        composition_parts = []
        for layer in vest_layers:
            material_id = layer.get('material_id')
            layer_count = layer.get('layer_count', 1)
            material = self.db.query(Material).filter(Material.id == material_id).first()
            if material:
                composition_parts.append(f"{layer_count} {material.name}")

        vest_composition = " + ".join(composition_parts) if composition_parts else ""

        # Generate predictions for all shots in the selected level(s)
        all_predictions = []

        for level in levels_to_process:
            level_name = level.get('level_name', 'Unknown Level')
            ammunition_config = level.get('ammunition_config', [])

            for ammo_config in ammunition_config:
                ammo_id = ammo_config.get('ammunition_id')
                reference_velocity = ammo_config.get('reference_velocity_m_s')
                shots_per_panel = ammo_config.get('shots_per_panel', 6)

                # Get ammunition
                ammo = self.db.query(Ammunition).filter(Ammunition.id == ammo_id).first()
                if not ammo:
                    raise ValueError(f"Ammunition with id {ammo_id} not found")

                # Generate predictions for all conditions: front/back, dry/wet
                conditions = [
                    {'side': 'front', 'conditioning': 'dry'},
                    {'side': 'front', 'conditioning': 'wet'},
                    {'side': 'back', 'conditioning': 'dry'},
                    {'side': 'back', 'conditioning': 'wet'},
                ]

                for condition in conditions:
                    for shot_num in range(shots_per_panel):
                        # Create a feature dictionary matching training format
                        import pandas as pd

                        # Get material properties for feature engineering
                        material_properties = fetch_material_properties(self.db)

                        # Create feature row matching training format
                        features = {
                            'vest_composition': vest_composition,
                            'material_thickness_mm': float(custom_vest.get('total_thickness_mm', 0)),
                            'material_weight_g_m2': float(custom_vest.get('material_areal_density_g_m2', 0)),
                            'number_of_layers': int(custom_vest.get('total_layers', 0)),
                            'ammunition_used': ammo.name if ammo else ammo.caliber,
                            'threat_level': None,  # Custom vest doesn't have threat level
                            'shot_number': shot_num + 1,
                            'impact_velocity_mps': reference_velocity,
                            'impact_angle_deg': 0.0,
                            'bullet_mass_g': float(ammo.projectile_mass_grams) if ammo and ammo.projectile_mass_grams else 0,
                            'temperature_c': 20.0,
                            'humidity_pct': 50.0,
                            'condition': condition['conditioning'],
                            'panel_side': condition['side'],
                            'material_type': None,  # Will be extracted from composition
                        }

                        # Convert to DataFrame and apply engineering features
                        df = pd.DataFrame([features])
                        df = add_engineered_features(df, material_properties, validate=False)

                        # Encode categorical features (simple label encoding)
                        categorical_cols = df.select_dtypes(include=['object']).columns
                        for col in categorical_cols:
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

                        # Apply inverse transform if log transform was used
                        if use_log_transform:
                            prediction = float(np.expm1(prediction))

                        # Predict perforation if classifier is available
                        perforation_probability = None
                        if perforation_model:
                            perforation_probability = float(perforation_model.predict_proba(features_scaled)[0, 1])

                        # Calculate confidence interval
                        confidence_interval = 2.0  # ±2mm

                        # Check domain of applicability
                        comparable_shot_count = self._count_comparable_shots(features)
                        extrapolation_warning = comparable_shot_count < 10

                        prediction_result = {
                            'shot_number': shot_num + 1,
                            'level_name': level_name,
                            'side': condition['side'],
                            'conditioning': condition['conditioning'],
                            'ammunition_id': ammo_id,
                            'ammunition_name': ammo.name if ammo.name else ammo.caliber,
                            'reference_velocity_m_s': reference_velocity,
                            'predicted_bfd_mm': float(prediction),
                            'perforation_probability': perforation_probability,
                            'confidence_interval_low_mm': float(prediction - confidence_interval),
                            'confidence_interval_high_mm': float(prediction + confidence_interval),
                            'comparable_shot_count': comparable_shot_count,
                            'extrapolation_warning': extrapolation_warning,
                        }

                        all_predictions.append(prediction_result)

        # Calculate summary statistics
        all_bfd_values = [p['predicted_bfd_mm'] for p in all_predictions]
        first_3_bfd_values = all_bfd_values[:3] if len(all_bfd_values) >= 3 else all_bfd_values

        # Generate velocity curves for each shot number
        velocity_curves = {}
        velocity_range = [200, 250, 300, 350, 400, 450, 500]  # m/s

        # Use a representative bullet mass from ammunition (assumed constant for a given ammo type)
        bullet_mass = 0
        if ammo:
            if ammo.projectile_mass_grams:
                bullet_mass = float(ammo.projectile_mass_grams)
            elif ammo.projectile_mass_grains:
                bullet_mass = float(ammo.projectile_mass_grains) / 15.432

        # If still no bullet mass, use a reasonable default (9mm FMJ ~8g)
        if bullet_mass == 0:
            bullet_mass = 8.0

        # Group predictions by shot number
        shot_predictions = {}
        for pred in all_predictions:
            shot_num = pred['shot_number']
            if shot_num not in shot_predictions:
                shot_predictions[shot_num] = pred

        # Generate velocity curves for each shot number
        for shot_num in sorted(shot_predictions.keys()):
            base_pred = shot_predictions[shot_num]
            curve_data = []
            for velocity in velocity_range:
                # Re-run prediction for this velocity
                try:
                    # Re-extract features with new velocity
                    features = {
                        'vest_composition': vest_composition,
                        'material_thickness_mm': float(custom_vest.get('total_thickness_mm', 0)),
                        'material_weight_g_m2': float(custom_vest.get('material_areal_density_g_m2', 0)),
                        'number_of_layers': int(custom_vest.get('total_layers', 0)),
                        'ammunition_used': ammo.name if ammo else ammo.caliber,
                        'threat_level': None,
                        'shot_number': base_pred['shot_number'],
                        'impact_velocity_mps': velocity,
                        'impact_angle_deg': 0.0,
                        'bullet_mass_g': bullet_mass,
                        'temperature_c': 20.0,
                        'humidity_pct': 50.0,
                        'condition': base_pred['conditioning'],
                        'panel_side': base_pred['side'],
                        'material_type': None,
                    }

                    df = pd.DataFrame([features])
                    df = add_engineered_features(df, material_properties, validate=False)

                    categorical_cols = df.select_dtypes(include=['object']).columns
                    for col in categorical_cols:
                        df[col] = pd.factorize(df[col].astype(str))[0]

                    for col in feature_columns:
                        if col not in df.columns:
                            df[col] = 0

                    df = df[feature_columns]
                    features_scaled = scaler.transform(df)
                    prediction = model.predict(features_scaled)[0]

                    # Apply inverse transform if log transform was used
                    if use_log_transform:
                        prediction = float(np.expm1(prediction))

                    curve_data.append({
                        'velocity_mps': velocity,
                        'predicted_bfd_mm': float(prediction)
                    })
                except Exception as e:
                    print(f"Error generating velocity curve point: {e}")
                    curve_data.append({
                        'velocity_mps': velocity,
                        'predicted_bfd_mm': 0.0
                    })

            velocity_curves[str(shot_num)] = curve_data

        summary = {
            'protocol_id': protocol_id,
            'protocol_name': protocol.name,
            'vest_id': 'custom',
            'vest_code': 'Custom Vest',
            'level_name': level_name,
            'total_shots': len(all_predictions),
            'predictions': all_predictions,
            'summary': {
                'mean_bfd_mm': float(np.mean(first_3_bfd_values)),
                'max_bfd_mm': float(np.max(all_bfd_values)),
                'min_bfd_mm': float(np.min(all_bfd_values)),
                'std_bfd_mm': float(np.std(all_bfd_values)),
            },
            'model_version': model_data.get('version', 'unknown'),
            'velocity_curves': velocity_curves,
        }

        return summary

    def predict_bfd(self, 
                    vest_id: str,
                    ammunition_id: str,
                    velocity_m_s: float,
                    impact_angle_degrees: float = 0.0) -> Dict:
        """
        Predict BFD for a given configuration (legacy method for single shot)
        
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
        vest = self.db.query(Vest).filter(Vest.vest_code == vest_id).first()
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
            predicted_bfd_mm=result.get('predicted_bfd_mm') or result.get('summary', {}).get('mean_bfd_mm'),
            prediction_interval_low_mm=result.get('confidence_interval_low_mm') or result.get('summary', {}).get('min_bfd_mm'),
            prediction_interval_high_mm=result.get('confidence_interval_high_mm') or result.get('summary', {}).get('max_bfd_mm'),
            extrapolation_warning=result.get('extrapolation_warning', False),
            comparable_shot_count=result.get('comparable_shot_count', 0),
            output_json=result
        )
        
        self.db.add(prediction)
        self.db.commit()
        
        return prediction
