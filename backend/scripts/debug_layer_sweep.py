"""One-off diagnostic: why does more layers -> higher predicted BFD?"""
from app.db.session import SessionLocal
from app.db.models import Material, Vest, VestLayer
from app.services.ml.model_bundle import get_active_bundle
from app.services.ml.data_fetcher import fetch_training_data

db = SessionLocal()
b = get_active_bundle(db)
print("bundle:", b.version, "contract:", b.feature_contract_version)

m = db.query(Material).filter(Material.name == "CS-302E").first()
print("CS-302E material_class:", getattr(m, "material_class", None))

# material properties the bundle uses for composition features
mp = getattr(b, "material_snapshot", None) or {}
if m and m.name in mp:
    print("CS-302E props:", {k: v for k, v in mp[m.name].items() if not k.startswith("_")})
else:
    print("CS-302E NOT in bundle material_snapshot; keys sample:", list(mp)[:10])

# controlled sweep: identical shot context, only composition/layer count vary
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

# what the composition features actually resolve to for one case
row = dict(base, vest_composition="20 CS-302E", number_of_layers=20)
frame = b.build_input_frame([row])
comp_cols = [c for c in frame.columns if "composition" in c and c.endswith(("_cs_302e", "_mm", "kg_m2"))]
for c in sorted(comp_cols):
    print(" ", c, "=", frame.iloc[0][c])

# training-data correlation: bfd vs layers within comparable velocity window
df, _, _ = fetch_training_data(db, verbose=False)
bfd_col = next((c for c in df.columns if "bfd" in c or "deformation" in c), None)
print("bfd col:", bfd_col)
if bfd_col and "number_of_layers" in df.columns:
    import numpy as np
    sub = df[["number_of_layers", bfd_col, "impact_velocity_mps"]].dropna()
    for lo, hi in [(0, 350), (350, 500), (500, 700), (700, 2000)]:
        w = sub[(sub.impact_velocity_mps >= lo) & (sub.impact_velocity_mps < hi)]
        if len(w) > 10:
            print(f"v[{lo},{hi}): n={len(w)}  corr(layers,bfd)={np.corrcoef(w.number_of_layers, w[bfd_col])[0,1]:+.3f}  layers range={int(w.number_of_layers.min())}-{int(w.number_of_layers.max())}")
db.close()
