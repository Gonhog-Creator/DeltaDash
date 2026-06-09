"""
Feature Engineering Service for BFD Prediction
Extracts and computes features from database for ML model training and prediction
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.db.models.shot_data import ShotData
from app.db.models.vest import Vest
from app.db.models.vest_layer import VestLayer
from app.db.models.material import Material
from app.db.models.ammunition import Ammunition


class FeatureEngineer:
    """Extracts and computes features for BFD prediction model"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def extract_features_for_shot(self, shot: ShotData) -> Dict:
        """
        Extract all features for a single shot
        
        Args:
            shot: ShotData object with loaded relationships
            
        Returns:
            Dictionary of feature names to values
        """
        features = {}
        
        # Projectile features
        features.update(self._extract_projectile_features(shot))
        
        # Vest features (from vest_number)
        if shot.vest_number:
            features.update(self._extract_vest_features_by_number(shot.vest_number))
        
        # Environmental features
        features.update(self._extract_environmental_features(shot))
        
        # Panel side feature
        features['panel_side'] = getattr(shot, 'panel_side', 'front')
        
        # Add interaction features
        features.update(self._compute_interaction_features(features))
        
        return features
    
    def _extract_projectile_features(self, shot: ShotData) -> Dict:
        """Extract projectile-related features"""
        features = {}
        
        # Caliber / ammunition used
        features['ammunition_used'] = shot.caliber or 'unknown'
        
        # Velocity
        velocity_m_s = float(shot.velocity_m_s) if shot.velocity_m_s else 0
        features['impact_velocity_mps'] = velocity_m_s
        
        # Get ammunition info from caliber
        ammo = self.db.query(Ammunition).filter(Ammunition.caliber == shot.caliber).first()
        
        # Projectile mass (from ammunition if available)
        if ammo:
            if ammo.projectile_mass_grains:
                features['projectile_mass_grains'] = float(ammo.projectile_mass_grains)
            if ammo.projectile_mass_grams:
                features['bullet_mass_g'] = float(ammo.projectile_mass_grams)
            elif ammo.projectile_mass_grains:
                features['bullet_mass_g'] = float(ammo.projectile_mass_grains) / 15.432
            # Use nominal velocity if measured not available
            if velocity_m_s == 0 and ammo.nominal_velocity_m_s:
                velocity_m_s = float(ammo.nominal_velocity_m_s)
                features['impact_velocity_mps'] = velocity_m_s
        else:
            features['projectile_mass_grains'] = 0
            features['bullet_mass_g'] = 0
        
        # Impact angle
        features['impact_angle_deg'] = float(shot.angle_degrees) if shot.angle_degrees else 0
        
        # Projectile type
        features['projectile_type'] = ammo.projectile_type if ammo and ammo.projectile_type else 'unknown'
        
        return features
    
    def _extract_vest_features_by_number(self, vest_number: str) -> Dict:
        """Extract vest-related features by vest number"""
        features = {}
        
        # Try to find vest by vest_code
        vest = self.db.query(Vest).filter(Vest.vest_code == vest_number).first()
        
        if vest:
            # Basic vest data
            features['number_of_layers'] = vest.total_layers if vest.total_layers else 0
            features['total_thickness_mm'] = float(vest.total_thickness_mm) if vest.total_thickness_mm else 0
            features['vest_id'] = str(vest.id)
            
            # Get vest layers with materials
            layers = self.db.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
            
            if layers:
                # Calculate total areal density and extract material properties
                total_areal_density = 0
                fabric_types = []
                material_types = []
                material_thicknesses = []
                material_elongations = []
                vest_composition_parts = []
                
                for layer in layers:
                    if layer.material:
                        material = layer.material
                        if material.areal_density_g_m2:
                            total_areal_density += float(material.areal_density_g_m2)
                        
                        if material.fiber_type:
                            fabric_types.append(material.fiber_type)
                        
                        if material.material_class:
                            material_types.append(material.material_class)
                        
                        if material.thickness_mm:
                            material_thicknesses.append(float(material.thickness_mm))
                        
                        # Add elongation if available (use longitudinal as primary)
                        if material.elongation_longitudinal_percent:
                            material_elongations.append(float(material.elongation_longitudinal_percent))
                        elif material.elongation_transverse_percent:
                            material_elongations.append(float(material.elongation_transverse_percent))
                        
                        # Build vest composition string
                        vest_composition_parts.append(f"{material.name}x{layer.layer_count}")
                
                features['total_areal_density_g_m2'] = total_areal_density
                features['layer_count'] = len(layers)
                features['primary_fabric_type'] = fabric_types[0] if fabric_types else 'unknown'
                features['energy_absorption_capacity'] = total_areal_density
                
                # New material features
                features['material_thickness_mm'] = sum(material_thicknesses) if material_thicknesses else 0
                features['material_elongation_percent'] = sum(material_elongations) / len(material_elongations) if material_elongations else 0
                features['material_type'] = material_types[0] if material_types else 'unknown'
                features['vest_composition'] = ', '.join(vest_composition_parts) if vest_composition_parts else 'unknown'
                
                # Add composition-specific features for each material type
                for material_type in set(material_types):
                    type_count = material_types.count(material_type)
                    features[f'composition_count_{material_type.lower().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")}'] = type_count
            else:
                features['total_areal_density_g_m2'] = 0
                features['layer_count'] = 0
                features['primary_fabric_type'] = 'unknown'
                features['energy_absorption_capacity'] = 0
                features['material_thickness_mm'] = 0
                features['material_elongation_percent'] = 0
                features['material_type'] = 'unknown'
                features['vest_composition'] = 'unknown'
        else:
            # Default values if vest not found
            features['number_of_layers'] = 0
            features['total_thickness_mm'] = 0
            features['total_areal_density_g_m2'] = 0
            features['layer_count'] = 0
            features['primary_fabric_type'] = 'unknown'
            features['energy_absorption_capacity'] = 0
            features['material_thickness_mm'] = 0
            features['material_elongation_percent'] = 0
            features['material_type'] = 'unknown'
            features['vest_composition'] = 'unknown'
            features['vest_id'] = vest_number  # Use vest_number as fallback
        
        return features
    
    def _extract_environmental_features(self, shot: ShotData) -> Dict:
        """Extract environmental-related features"""
        features = {}
        
        if shot.test_session:
            session = shot.test_session
            
            # Clay temperature
            features['temperature_c'] = float(session.ambient_temperature_c) if session.ambient_temperature_c else 20.0
            
            # Humidity
            features['humidity_pct'] = float(session.humidity_percent) if session.humidity_percent else 50.0
            
            # Conditioning state
            features['condition'] = session.conditioning if session.conditioning else 'dry'
            
            # Vest size
            features['vest_size'] = session.size if session.size else 'medium'
        else:
            features['temperature_c'] = 20.0
            features['humidity_pct'] = 50.0
            features['condition'] = 'dry'
            features['vest_size'] = 'medium'
        
        return features
    
    def _compute_interaction_features(self, features: Dict) -> Dict:
        """
        Compute interaction features from base features
        
        Args:
            features: Dictionary of base features
            
        Returns:
            Dictionary of interaction features
        """
        interaction_features = {}
        
        # Extract numerical values with defaults
        velocity = features.get('impact_velocity_mps', 0)
        bullet_mass = features.get('bullet_mass_g', 0)
        areal_density = features.get('total_areal_density_g_m2', 0)
        thickness = features.get('material_thickness_mm', 0)
        layer_count = features.get('layer_count', 0)
        impact_angle = features.get('impact_angle_deg', 0)
        
        # Kinetic energy: 0.5 * mass * velocity^2
        if bullet_mass > 0 and velocity > 0:
            interaction_features['kinetic_energy_j'] = 0.5 * bullet_mass * (velocity ** 2)
        else:
            interaction_features['kinetic_energy_j'] = 0
        
        # Velocity × areal density (impact energy per unit area)
        interaction_features['velocity_areal_density'] = velocity * areal_density
        
        # Velocity × thickness (impact through material)
        interaction_features['velocity_thickness'] = velocity * thickness
        
        # Bullet mass × areal density (momentum transfer)
        interaction_features['mass_areal_density'] = bullet_mass * areal_density
        
        # Layer count × thickness (total material resistance)
        interaction_features['layer_thickness'] = layer_count * thickness
        
        # Velocity × cos(angle) (effective velocity perpendicular to surface)
        import math
        interaction_features['effective_velocity'] = velocity * math.cos(math.radians(impact_angle))
        
        # Kinetic energy per unit areal density
        if areal_density > 0:
            interaction_features['energy_per_density'] = interaction_features['kinetic_energy_j'] / areal_density
        else:
            interaction_features['energy_per_density'] = 0
        
        # Velocity squared (non-linear relationship)
        interaction_features['velocity_squared'] = velocity ** 2
        
        # Material density ratio (areal density / thickness)
        if thickness > 0:
            interaction_features['density_ratio'] = areal_density / thickness
        else:
            interaction_features['density_ratio'] = 0
        
        return interaction_features
    
    def extract_training_data(self) -> Tuple[List[Dict], List[float]]:
        """
        Extract all training data from database
        
        Returns:
            Tuple of (features_list, targets_list)
        """
        shots = self.db.query(ShotData).filter(
            ShotData.trauma_mm.is_not(None),
            ShotData.vest_number.is_not(None)
        ).all()
        
        features_list = []
        targets_list = []
        
        for shot in shots:
            features = self.extract_features_for_shot(shot)
            features_list.append(features)
            targets_list.append(float(shot.trauma_mm))
        
        return features_list, targets_list
    
    def encode_categorical_features(self, features_list: List[Dict]) -> List[Dict]:
        """
        Encode categorical features for ML model
        
        Args:
            features_list: List of feature dictionaries
            
        Returns:
            List of feature dictionaries with encoded categorical variables
        """
        if not features_list:
            return features_list
        
        # Convert to DataFrame for easier encoding
        import pandas as pd
        df = pd.DataFrame(features_list)
        
        # Define low-cardinality features (use OneHot encoding)
        low_cardinality_features = [
            'panel_side', 'condition', 'vest_size', 'primary_fabric_type'
        ]
        
        # Define high-cardinality features (use Label encoding)
        high_cardinality_features = [
            'ammunition_used', 'projectile_type', 'material_type', 'vest_composition'
        ]
        
        # OneHot encode low-cardinality features
        for col in low_cardinality_features:
            if col in df.columns:
                # Get dummies and drop first to avoid multicollinearity
                dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
                df = pd.concat([df, dummies], axis=1)
                df = df.drop(col, axis=1)
        
        # Label encode high-cardinality features
        from sklearn.preprocessing import LabelEncoder
        label_encoders = {}
        for col in high_cardinality_features:
            if col in df.columns:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].astype(str))
                label_encoders[col] = le
        
        # Convert back to list of dictionaries
        return df.to_dict('records')
    
    def normalize_features(self, features_list: List[Dict]) -> np.ndarray:
        """
        Normalize numerical features for ML model
        
        Args:
            features_list: List of feature dictionaries
            
        Returns:
            Normalized feature matrix
        """
        # For now, return as-is. In production, use proper normalization (StandardScaler, MinMaxScaler, etc.)
        return features_list
