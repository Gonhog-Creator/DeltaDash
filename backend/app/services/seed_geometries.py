import json
import os
from typing import List

from sqlalchemy.orm import Session

from app.db.models.geometry import Geometry


DEFAULT_FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "fixtures",
    "geometries.json",
)


def seed_geometries(db: Session, fixture_path: str = DEFAULT_FIXTURE_PATH) -> List[Geometry]:
    """Upsert geometries from a JSON fixture keyed by name."""
    if not os.path.exists(fixture_path):
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    upserted = []
    for entry in data:
        name = entry.get("name")
        if not name:
            continue

        geometry = db.query(Geometry).filter(Geometry.name == name).first()
        if not geometry:
            geometry = Geometry()
            db.add(geometry)

        for key, value in entry.items():
            if hasattr(geometry, key):
                setattr(geometry, key, value)

        upserted.append(geometry)

    db.commit()
    for geometry in upserted:
        db.refresh(geometry)

    return upserted
