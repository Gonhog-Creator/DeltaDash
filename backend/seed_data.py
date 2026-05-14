#!/usr/bin/env python3
"""
Seed script to create initial data for the ballistic analytics platform.
Run this after running database migrations.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from uuid import uuid4

from app.db.models.user import User
from app.db.models.material import Material
from app.db.models.ammunition import Ammunition
from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_seed_data():
    """Create initial seed data for testing."""
    
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=True
    )
    
    # Create session
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            # Create admin user
            admin_user = User(
                id=uuid4(),
                email="admin@ballistic.test",
                full_name="Admin User",
                hashed_password=pwd_context.hash("admin123")[:72],
                role="admin",
                is_active=True
            )
            session.add(admin_user)
            
            # Create researcher user
            researcher_user = User(
                id=uuid4(),
                email="researcher@ballistic.test",
                full_name="Research User",
                hashed_password=pwd_context.hash("research123")[:72],
                role="researcher",
                is_active=True
            )
            session.add(researcher_user)
            
            # Create some sample materials
            materials = [
                Material(
                    id=uuid4(),
                    name="Kevlar 29",
                    manufacturer="DuPont",
                    material_class="aramid",
                    fiber_type="para-aramid",
                    areal_density_g_m2=280.0,
                    thickness_mm=0.5,
                    density_g_cm3=1.44,
                    tensile_strength_mpa=3620.0,
                    modulus_gpa=125.0,
                    source_confidence="manufacturer_spec"
                ),
                Material(
                    id=uuid4(),
                    name="Dyneema HB26",
                    manufacturer="DSM",
                    material_class="UHMWPE",
                    fiber_type="UHMWPE",
                    areal_density_g_m2=260.0,
                    thickness_mm=0.4,
                    density_g_cm3=0.97,
                    tensile_strength_mpa=3500.0,
                    modulus_gpa=100.0,
                    source_confidence="manufacturer_spec"
                ),
                Material(
                    id=uuid4(),
                    name="Spectra 2000",
                    manufacturer="Honeywell",
                    material_class="UHMWPE",
                    fiber_type="UHMWPE",
                    areal_density_g_m2=200.0,
                    thickness_mm=0.35,
                    density_g_cm3=0.97,
                    tensile_strength_mpa=3200.0,
                    modulus_gpa=95.0,
                    source_confidence="manufacturer_spec"
                )
            ]
            
            for material in materials:
                session.add(material)
            
            # Create some sample ammunition
            ammunition = [
                Ammunition(
                    id=uuid4(),
                    name="9mm FMJ",
                    caliber="9mm Luger",
                    projectile_type="FMJ",
                    projectile_mass_grains=124.0,
                    projectile_mass_grams=8.04,
                    nominal_velocity_fps=1180.0,
                    nominal_velocity_m_s=359.7,
                    manufacturer="Various",
                    standard_reference="NIJ 0101.06"
                ),
                Ammunition(
                    id=uuid4(),
                    name="5.56mm FMJ",
                    caliber="5.56x45mm NATO",
                    projectile_type="FMJ",
                    projectile_mass_grains=62.0,
                    projectile_mass_grams=4.02,
                    nominal_velocity_fps=3100.0,
                    nominal_velocity_m_s=944.9,
                    manufacturer="Various",
                    standard_reference="NIJ 0101.06"
                ),
                Ammunition(
                    id=uuid4(),
                    name="7.62mm FMJ",
                    caliber="7.62x51mm NATO",
                    projectile_type="FMJ",
                    projectile_mass_grains=147.0,
                    projectile_mass_grams=9.53,
                    nominal_velocity_fps=2750.0,
                    nominal_velocity_m_s=838.2,
                    manufacturer="Various",
                    standard_reference="NIJ 0101.06"
                )
            ]
            
            for ammo in ammunition:
                session.add(ammo)
            
            # Commit all changes
            await session.commit()
            print("✅ Seed data created successfully!")
            print("\n📋 Created users:")
            print(f"  Admin: admin@ballistic.test / admin123")
            print(f"  Researcher: researcher@ballistic.test / research123")
            print(f"\n📋 Created {len(materials)} materials and {len(ammunition)} ammunition types")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error creating seed data: {e}")
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_seed_data())
