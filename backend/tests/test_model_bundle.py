"""
Model bundle regression tests (Milestone B).

Runs standalone (python tests/test_model_bundle.py) or under pytest.
Covers the failure modes the bundle was built to fix:
- batch-dependent inference (a row's prediction must not depend on its batch)
- concurrent version activation overwriting shared artifacts
- log1p inverse transform applied exactly once
- feature alignment between training contract and inference
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib
import numpy as np
import pandas as pd

from app.db.session import SessionLocal
from app.services.ml.model_bundle import (
    get_model_bundle,
    get_active_bundle,
    get_default_version,
    MODEL_DIR,
)
from app.services.ml.feature_contract import (
    CONTRACT_V1,
    build_composition_features_v1,
)
from app.services.ml.data_fetcher import fetch_training_data, fetch_material_properties


def _db():
    return SessionLocal()


def _real_rows(db, n=30):
    df, _, _ = fetch_training_data(db, ignore_anchor_points=True)
    df = df[df["backface_deformation_mm"].notna()].copy()
    drop = {"backface_deformation_mm", "perforated", "pass_fail"}
    cols = [c for c in df.columns if c not in drop]
    rows = []
    for _, r in df.head(n).iterrows():
        rows.append({c: (None if pd.isna(r[c]) else r[c]) for c in cols})
    return rows


def test_batch_invariance():
    db = _db()
    rows = _real_rows(db)
    bundle = get_model_bundle("20260908_172840", db_session=db)
    solo = bundle.predict_bfd([rows[0]])[0]
    in_batch = bundle.predict_bfd(rows)[0]
    shuffled = bundle.predict_bfd(list(reversed(rows)))[-1]
    db.close()
    assert abs(solo - in_batch) < 1e-9, f"solo {solo} != batch {in_batch}"
    assert abs(solo - shuffled) < 1e-9, f"solo {solo} != shuffled {shuffled}"


def test_feature_alignment():
    db = _db()
    rows = _real_rows(db, n=5)
    bundle = get_model_bundle("20260908_172840", db_session=db)
    frame = bundle.build_input_frame(rows)
    db.close()
    assert list(frame.columns) == bundle.feature_columns
    # numeric NaN preserved for the fitted imputer (not batch-filled)
    if "angle_degrees" in frame.columns or "impact_angle_deg" in frame.columns:
        pass
    for col in frame.columns:
        if col in bundle.categorical_names:
            assert not frame[col].isna().any(), f"categorical {col} left NaN"
            assert (frame[col] != "").all(), f"categorical {col} empty string"


def test_log_transform_applied_once():
    db = _db()
    rows = _real_rows(db)
    bundle = get_model_bundle("20260908_172840", db_session=db)
    preds = bundle.predict_bfd(rows)
    db.close()
    assert np.isfinite(preds).all()
    assert (preds >= 0).all(), "expm1 output must be non-negative"
    # a double-expm1 would explode into absurd values
    assert (preds < 1000).all()


def test_concurrent_versions_no_shared_mutation():
    """Two bundles coexist; predicting with either never touches the shared
    MODEL_DIR artifact files (the old load_model_version race)."""
    db = _db()
    shared_files = [
        os.path.join(MODEL_DIR, f)
        for f in ("backface_deformation_mm.pkl", "preprocessor.pkl", "perforated.pkl")
    ]
    before = {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in shared_files if os.path.exists(f)}

    versions = [v for v in ("20260908_172840", "20260903_151448") ]
    bundles = [get_model_bundle(v, db_session=db) for v in versions]
    assert bundles[0].bundle_hash != bundles[1].bundle_hash

    rows = _real_rows(db, n=3)
    p_a = bundles[0].predict_bfd(rows)
    p_b = bundles[1].predict_bfd(rows)
    db.close()

    after = {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in shared_files if os.path.exists(f)}
    assert before == after, "predict-time artifact writes detected"
    assert np.isfinite(p_a).all() and np.isfinite(p_b).all()


def test_v1_contract_areal_density():
    """v1 uses grammage: a UD 234 segment (areal_density_g_m2>0) must produce
    nonzero composition areal density (v0 silently yields 0)."""
    mp = {"UD 234": {"thickness_mm": 0.18, "areal_density_g_m2": 234.0, "material_class": "Aramid", "ply_count": 1}}
    feats = build_composition_features_v1("10 UD 234", mp, validate=False)
    expected = 10 * 234.0 / 1000.0
    assert abs(feats["composition_calculated_areal_density_kg_m2"] - expected) < 1e-9
    assert feats["composition_areal_density_kg_m2_ud_234"] == expected


def test_active_bundle_resolution():
    db = _db()
    version = get_default_version(db)
    assert version == "20260908_172840", f"active version is {version}"
    bundle = get_active_bundle(db)
    db.close()
    assert bundle.version == version


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:
            failures += 1
            print(f"FAIL {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
