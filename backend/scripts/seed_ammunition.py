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
            # NIJ 0101.07 Standard Ammunition
            {
                "name": "9mm Luger FMJ - NIJ Standard",
                "caliber": "9mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 9.0,
                "caliber_length_mm": 19.15,
                "projectile_mass_grains": 124,
                "nominal_velocity_fps": 1250,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard handgun ammunition"
            },
            {
                "name": ".40 S&W FMJ - NIJ Standard",
                "caliber": ".40 S&W",
                "caliber_unit": "inches",
                "caliber_diameter_mm": 10.0,
                "caliber_length_mm": 21.59,
                "projectile_mass_grains": 180,
                "nominal_velocity_fps": 980,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard handgun ammunition"
            },
            {
                "name": ".357 SIG FMJ - NIJ Standard",
                "caliber": ".357 SIG",
                "caliber_unit": "inches",
                "caliber_diameter_mm": 9.0,
                "caliber_length_mm": 21.97,
                "projectile_mass_grains": 125,
                "nominal_velocity_fps": 1350,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard handgun ammunition"
            },
            {
                "name": ".45 ACP FMJ - NIJ Standard",
                "caliber": ".45 ACP",
                "caliber_unit": "inches",
                "caliber_inch": 0.45,
                "projectile_mass_grains": 230,
                "nominal_velocity_fps": 850,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard handgun ammunition"
            },
            {
                "name": "7.62x39mm FMJ - NIJ Standard",
                "caliber": "7.62x39mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 7.62,
                "caliber_length_mm": 39.0,
                "projectile_mass_grains": 123,
                "nominal_velocity_fps": 2395,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard rifle ammunition"
            },
            {
                "name": "5.56x45mm M855 FMJ - NIJ Standard",
                "caliber": "5.56x45mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 5.56,
                "caliber_length_mm": 45.0,
                "projectile_mass_grains": 62,
                "nominal_velocity_fps": 3100,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard rifle ammunition (green tip)"
            },
            {
                "name": "7.62x51mm M80 FMJ - NIJ Standard",
                "caliber": "7.62x51mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 7.62,
                "caliber_length_mm": 51.0,
                "projectile_mass_grains": 147,
                "nominal_velocity_fps": 2750,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard rifle ammunition"
            },
            {
                "name": ".30-06 Springfield FMJ - NIJ Standard",
                "caliber": ".30-06",
                "caliber_unit": "inches",
                "caliber_inch": 0.30,
                "projectile_mass_grains": 150,
                "nominal_velocity_fps": 2700,
                "projectile_type": "FMJ",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard rifle ammunition"
            },
            {
                "name": "12 Gauge Slug - NIJ Standard",
                "caliber": "12 Gauge",
                "caliber_unit": "inches",
                "caliber_inch": 0.729,
                "projectile_mass_grains": 438,
                "nominal_velocity_fps": 1600,
                "projectile_type": "Slug",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard shotgun slug"
            },
            {
                "name": "12 Gauge 00 Buckshot - NIJ Standard",
                "caliber": "12 Gauge",
                "caliber_unit": "inches",
                "caliber_inch": 0.729,
                "projectile_mass_grains": 438,
                "nominal_velocity_fps": 1300,
                "projectile_type": "Buckshot",
                "manufacturer": "Various",
                "standard_reference": "NIJ 0101.07",
                "notes": "NIJ standard shotgun buckshot (9 pellets)"
            },
            # Argentine Government Standards
            {
                "name": "9mm Luger FMJ - FM Argentine",
                "caliber": "9mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 9.0,
                "caliber_length_mm": 19.15,
                "projectile_mass_grains": 124,
                "nominal_velocity_fps": 1250,
                "projectile_type": "FMJ",
                "manufacturer": "FM (Fábrica Militar)",
                "standard_reference": "FM Argentine Standard",
                "notes": "Argentine military standard 9mm"
            },
            {
                "name": "9mm Luger FMJ - Bersa",
                "caliber": "9mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 9.0,
                "caliber_length_mm": 19.15,
                "projectile_mass_grains": 124,
                "nominal_velocity_fps": 1250,
                "projectile_type": "FMJ",
                "manufacturer": "Bersa",
                "standard_reference": "Civilian Standard",
                "notes": "Argentine civilian 9mm ammunition"
            },
            {
                "name": ".45 ACP FMJ - FM Argentine",
                "caliber": ".45 ACP",
                "caliber_unit": "inches",
                "caliber_inch": 0.45,
                "projectile_mass_grains": 230,
                "nominal_velocity_fps": 850,
                "projectile_type": "FMJ",
                "manufacturer": "FM (Fábrica Militar)",
                "standard_reference": "FM Argentine Standard",
                "notes": "Argentine military .45 ACP"
            },
            {
                "name": "5.56x45mm FMJ - FM Argentine",
                "caliber": "5.56x45mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 5.56,
                "caliber_length_mm": 45.0,
                "projectile_mass_grains": 62,
                "nominal_velocity_fps": 3100,
                "projectile_type": "FMJ",
                "manufacturer": "FM (Fábrica Militar)",
                "standard_reference": "FM Argentine Standard",
                "notes": "Argentine military 5.56mm"
            },
            {
                "name": "7.62x51mm FMJ - FM Argentine",
                "caliber": "7.62x51mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 7.62,
                "caliber_length_mm": 51.0,
                "projectile_mass_grains": 147,
                "nominal_velocity_fps": 2750,
                "projectile_type": "FMJ",
                "manufacturer": "FM (Fábrica Militar)",
                "standard_reference": "FM Argentine Standard",
                "notes": "Argentine military 7.62mm NATO"
            },
            {
                "name": "7.62x39mm FMJ - FM Argentine",
                "caliber": "7.62x39mm",
                "caliber_unit": "mm",
                "caliber_diameter_mm": 7.62,
                "caliber_length_mm": 39.0,
                "projectile_mass_grains": 123,
                "nominal_velocity_fps": 2395,
                "projectile_type": "FMJ",
                "manufacturer": "FM (Fábrica Militar)",
                "standard_reference": "FM Argentine Standard",
                "notes": "Argentine military 7.62x39mm"
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
