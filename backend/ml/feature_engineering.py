"""
Feature Engineering Service for BFD Prediction
Extracts and computes features from database for ML model training and prediction
"""
import numpy as np
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.db.models.shot import Shot
from app.db.models.vest import Vest
from app.db.models.vest_layer import VestLayer
from app.db.models.material import Material
from app.db.models.ammunition import Ammunition


class FeatureEngineer:
    """Extracts and computes features for BFD prediction model"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def extract_features_for_shot(self, shot: Shot) -> Dict:
        """
        Extract all features for a single shot
        
        Args:
            shot: Shot object with loaded relationships
            
        Returns:
            Dictionary of feature names to values
        """
        features = {}
        
        # Projectile features
        features.update(self._extract_projectile_features(shot))
        
        # Vest features
        if shot.vest:
            features.update(self._extract_vest_features(shot.vest))
        
        # Environmental features
        features.update(self._extract_environmental_features(shot))
        
        return features
    
    def _extract_projectile_features(self, shot: Shot) -> Dict:
        """Extract projectile-related features"""
        features = {}
        
        if shot.ammunition:
            ammo = shot.ammunition
            
            # Basic projectile data
            features['caliber'] = ammo.caliber_diameter_mm if ammo.caliber_diameter_mm else 0
            features['projectile_mass_grains'] = float(ammo.projectile_mass_grains) if ammo.projectile_mass_grains else 0
            features['projectile_mass_grams'] = float(ammo.projectile_mass_grams) if ammo.projectile_mass_grams else (float(ammo.projectile_mass_grains) / 15.432) if ammo.projectile_mass_grains else 0
        
        # Velocity data (prefer measured over nominal)
        velocity_m_s = float(shot.measured_velocity_m_s) if shot.measured_velocity_m_s else 0
        if velocity_m_s == 0 and shot.ammunition:
            velocity_m_s = float(shot.ammunition.nominal_velocity_m_s) if shot.ammunition.nominal_velocity_m_s else 0
        
        features['velocity_m_s'] = velocity_m_s
        
        # Derived features (physics-informed)
        projectile_mass_g = features.get('projectile_mass_grams', 0) / 1000.0  # Convert to kg
        features['kinetic_energy_joules'] = 0.5 * projectile_mass_g * (velocity_m_s ** 2) if projectile_mass_g > 0 else 0
        features['momentum'] = projectile_mass_g * velocity_m_s if projectile_mass_g > 0 else 0
        
        # Strain-rate indicator (velocity × material type interaction)
        features['strain_rate_indicator'] = velocity_m_s  # Will be combined with material type later
        
        # Impact angle
        features['impact_angle_degrees'] = float(shot.impact_angle_degrees) if shot.impact_angle_degrees else 0
        
        # Projectile type encoding (simplified - will need proper encoding in production)
        if shot.ammunition and shot.ammunition.projectile_type:
            features['projectile_type'] = shot.ammunition.projectile_type
        else:
            features['projectile_type'] = 'unknown'
        
        return features
    
    def _extract_vest_features(self, vest: Vest) -> Dict:
        """Extract vest-related features"""
        features = {}
        
        # Basic vest data
        features['total_layers'] = vest.total_layers if vest.total_layers else 0
        features['total_thickness_mm'] = float(vest.total_thickness_mm) if vest.total_thickness_mm else 0
        
        # Get vest layers with materials
        layers = self.db.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
        
        if layers:
            # Calculate total areal density
            total_areal_density = 0
            fabric_types = []
            
            for layer in layers:
                if layer.material:
                    material = layer.material
                    if material.areal_density_g_m2:
                        total_areal_density += float(material.areal_density_g_m2)
                    
                    if material.fiber_type:
                        fabric_types.append(material.fiber_type)
            
            features['total_areal_density_g_m2'] = total_areal_density
            features['layer_count'] = len(layers)
            
            # Fabric type distribution (simplified - will need proper encoding in production)
            features['primary_fabric_type'] = fabric_types[0] if fabric_types else 'unknown'
            
            # Energy absorption capacity (areal density × material properties)
            # For now, use areal density as proxy (will add material properties when available)
            features['energy_absorption_capacity'] = total_areal_density
        else:
            features['total_areal_density_g_m2'] = 0
            features['layer_count'] = 0
            features['primary_fabric_type'] = 'unknown'
            features['energy_absorption_capacity'] = 0
        
        return features
    
    def _extract_environmental_features(self, shot: Shot) -> Dict:
        """Extract environmental-related features"""
        features = {}
        
        if shot.test_session:
            session = shot.test_session
            
            # Clay temperature
            features['clay_temperature_c'] = float(session.clay_temperature_c) if session.clay_temperature_c else 20.0
            
            # Humidity
            features['humidity_percent'] = float(session.humidity_percent) if session.humidity_percent else 50.0
            
            # Conditioning state
            features['conditioning'] = session.conditioning if session.conditioning else 'dry'
            
            # Vest size
            features['vest_size'] = session.size if session.size else 'medium'
        else:
            features['clay_temperature_c'] = 20.0
            features['humidity_percent'] = 50.0
            features['conditioning'] = 'dry'
            features['vest_size'] = 'medium'
        
        return features
    
    def extract_training_data(self) -> Tuple[List[Dict], List[float]]:
        """
        Extract all training data from database
        
        Returns:
            Tuple of (features_list, targets_list)
        """
        shots = self.db.query(Shot).filter(
            Shot.bfd_mm.isnot_(None),
            Shot.vest_id.isnot_(None)
        ).all()
        
        features_list = []
        targets_list = []
        
        for shot in shots:
            features = self.extract_features_for_shot(shot)
            features_list.append(features)
            targets_list.append(float(shot.bfd_mm))
        
        return features_list, targets_list
    
    def encode_categorical_features(self, features_list: List[Dict]) -> List[Dict]:
        """
        Encode categorical features for ML model
        
        Args:
            features_list: List of feature dictionaries
            
        Returns:
            List of feature dictionaries with encoded categorical variables
        """
        # For now, return as-is. In production, use proper encoding (OneHot, LabelEncoder, etc.)
        return features_list
    
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
