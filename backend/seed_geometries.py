import os
import sys

# Ensure backend is on path when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from app.db.session import SessionLocal
from app.services.seed_geometries import seed_geometries


def main():
    db = SessionLocal()
    try:
        geometries = seed_geometries(db)
        print(f"Seeded {len(geometries)} geometries")
    finally:
        db.close()


if __name__ == "__main__":
    main()
