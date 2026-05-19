#!/usr/bin/env python3
"""
Seed ammunition script.
Populates the ammunition table with NIJ 0101.07 and Argentine government standard ammunition.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.ammunition import Ammunition


def seed_ammunition():
    db: Session = SessionLocal()
    try:
        ammunition_data = [
            {
                "name": "9 mm FMJ - Standard",
                "caliber": "9 mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 9.0,
                "caliber_length_mm": 19.15,
                "projectile_mass_grains": 124,
                "nominal_velocity_fps": 1250,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "Standard",
                "notes": "Standard 9mm ammunition (space variant)"
            },
            {
                "name": ".357 Magnum FMJ - Standard",
                "caliber": ".357 MAG",
                "caliber_unit": "inches",
                "caliber_diameter_mm": 9.07,
                "caliber_length_mm": 33.0,
                "caliber_inch": 0.357,
                "projectile_mass_grains": 158,
                "nominal_velocity_fps": 1250,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "Standard",
                "notes": "Standard .357 Magnum ammunition"
            },
        ]

        for ammo_data in ammunition_data:
            existing = db.query(Ammunition).filter(Ammunition.name == ammo_data["name"]).first()
            if not existing:
                print(f"Adding ammunition: {ammo_data['name']}")
                ammo = Ammunition(**ammo_data)
                db.add(ammo)
            else:
                print(f"Ammunition already exists: {ammo_data['name']}")

        db.commit()
        print("Ammunition seeding completed successfully.")

    except Exception as e:
        print(f"Error seeding ammunition: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_ammunition()
