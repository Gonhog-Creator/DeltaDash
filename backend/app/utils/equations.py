"""
Centralized equations and unit conversions for ballistic calculations.

This module serves as the single source of truth for all physics equations
and unit conversions used throughout the DeltaDash application.
"""

from typing import Optional


# Unit Conversions
def grains_to_kg(grains: float) -> float:
    """
    Convert mass from grains to kilograms.
    
    Args:
        grains: Mass in grains
        
    Returns:
        Mass in kilograms
        
    Formula:
        1 grain = 0.00006479891 kg
    """
    return grains * 0.00006479891


def grams_to_kg(grams: float) -> float:
    """
    Convert mass from grams to kilograms.
    
    Args:
        grams: Mass in grams
        
    Returns:
        Mass in kilograms
        
    Formula:
        1 gram = 0.001 kg
    """
    return grams / 1000.0


def fps_to_m_s(fps: float) -> float:
    """
    Convert velocity from feet per second to meters per second.
    
    Args:
        fps: Velocity in feet per second
        
    Returns:
        Velocity in meters per second
        
    Formula:
        1 fps = 0.3048 m/s
    """
    return fps * 0.3048


def m_s_to_fps(m_s: float) -> float:
    """
    Convert velocity from meters per second to feet per second.
    
    Args:
        m_s: Velocity in meters per second
        
    Returns:
        Velocity in feet per second
        
    Formula:
        1 m/s = 3.28084 fps
    """
    return m_s / 0.3048


# Physics Equations
def calculate_kinetic_energy(mass_kg: float, velocity_m_s: float) -> Optional[float]:
    """
    Calculate kinetic energy in Joules.
    
    Args:
        mass_kg: Mass in kilograms
        velocity_m_s: Velocity in meters per second
        
    Returns:
        Kinetic energy in Joules, or None if inputs are invalid
        
    Formula:
        KE = 0.5 * m * v²
    """
    if mass_kg is None or velocity_m_s is None or velocity_m_s == 0:
        return None
    return 0.5 * mass_kg * (velocity_m_s ** 2)


def calculate_momentum(mass_kg: float, velocity_m_s: float) -> Optional[float]:
    """
    Calculate momentum in kg·m/s.
    
    Args:
        mass_kg: Mass in kilograms
        velocity_m_s: Velocity in meters per second
        
    Returns:
        Momentum in kg·m/s, or None if inputs are invalid
        
    Formula:
        p = m * v
    """
    if mass_kg is None or velocity_m_s is None:
        return None
    return mass_kg * velocity_m_s


# Combined Calculations
def calculate_bullet_energy_from_grains_and_fps(
    grains: float, 
    fps: float
) -> Optional[float]:
    """
    Calculate bullet energy in Joules from mass in grains and velocity in fps.
    
    Args:
        grains: Bullet mass in grains
        fps: Bullet velocity in feet per second
        
    Returns:
        Kinetic energy in Joules, or None if inputs are invalid
    """
    mass_kg = grains_to_kg(grains)
    velocity_m_s = fps_to_m_s(fps)
    return calculate_kinetic_energy(mass_kg, velocity_m_s)


def calculate_bullet_energy_from_grams_and_m_s(
    grams: float, 
    m_s: float
) -> Optional[float]:
    """
    Calculate bullet energy in Joules from mass in grams and velocity in m/s.
    
    Args:
        grams: Bullet mass in grams
        m_s: Bullet velocity in meters per second
        
    Returns:
        Kinetic energy in Joules, or None if inputs are invalid
    """
    mass_kg = grams_to_kg(grams)
    return calculate_kinetic_energy(mass_kg, m_s)


def calculate_momentum_from_grains_and_fps(
    grains: float, 
    fps: float
) -> Optional[float]:
    """
    Calculate bullet momentum in kg·m/s from mass in grains and velocity in fps.
    
    Args:
        grains: Bullet mass in grains
        fps: Bullet velocity in feet per second
        
    Returns:
        Momentum in kg·m/s, or None if inputs are invalid
    """
    mass_kg = grains_to_kg(grains)
    velocity_m_s = fps_to_m_s(fps)
    return calculate_momentum(mass_kg, velocity_m_s)


def calculate_momentum_from_grams_and_m_s(
    grams: float, 
    m_s: float
) -> Optional[float]:
    """
    Calculate bullet momentum in kg·m/s from mass in grams and velocity in m/s.
    
    Args:
        grams: Bullet mass in grams
        m_s: Bullet velocity in meters per second
        
    Returns:
        Momentum in kg·m/s, or None if inputs are invalid
    """
    mass_kg = grams_to_kg(grams)
    return calculate_momentum(mass_kg, m_s)
