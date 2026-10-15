"""Verify the v1 bundle: areal density live + layer-count response."""
import sys
from app.db.session import SessionLocal
from app.services.ml.model_bundle import get_model_bundle

db = SessionLocal()
version = sys.argv[1] if len(sys.argv) > 1 else "20261015_134943"
b = get_model_bundle(version, db_session=db)
print("bundle:", b.version, "contract:", b.feature_contract_version)

base = {
    "ammunition_used": ".38 Special",
    "bullet_mass_g": 10.2,
    "caliber_diameter_mm": 9.0,
    "caliber_length_mm": 29.0,
    "impact_velocity_mps": 265.0,
    "shot_number": 1,
    "panel_side": "front",
    "impact_angle_deg": None,
    "condition": None,
    "vest_type": "soft",
    "is_female": False,
    "threat_level": None,
    "flexibility_rating": 0,
    "is_panel_sewn": 0,
    "weight_g": None,
    "ply_orientations": None,
    "geometry_name": None,
    "temperature_c": 21.0,
    "humidity_pct": 50.0,
    "material_type": "UHMWPE",
}
for n in (5, 10, 15, 20, 40):
    row = dict(base)
    row["vest_composition"] = f"{n} CS-302E"
    row["number_of_layers"] = n
    bfd = b.predict_bfd([row])[0]
    perf = b.predict_perforation_score([row])
    print(f"layers={n:3d}  bfd={bfd:7.2f}  perf={None if perf is None else round(float(perf[0]), 4)}")

row = dict(base, vest_composition="20 CS-302E", number_of_layers=20)
frame = b.build_input_frame([row])
for c in ("composition_calculated_areal_density_kg_m2",
          "composition_calculated_thickness_mm",
          "composition_areal_density_kg_m2_cs_302e"):
    print(" ", c, "=", frame.iloc[0].get(c))
db.close()
