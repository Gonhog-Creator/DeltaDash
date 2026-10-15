"""Milestone D: grouped validation manifest + v1_corrected retrain + calibration.

Pipeline:
  1. Fetch REAL shot data (no anchor points) and anchor points separately.
  2. Grouped holdout: whole vests assigned to validation by deterministic hash
     of vest_id (~20% of vest groups). No vest appears in both train and val,
     so metrics reflect generalization to unseen designs.
  3. Train on train-split + anchor points under the v1_corrected contract.
  4. Evaluate the NEW bundle on the held-out vests:
       BFD: MAE / MAPE / bias / residual sigma (for MC noise in sims)
       perforated: AUC / Brier + isotonic calibration curve
  5. Write validation manifest JSON, update bundle metadata.json + ModelRun
     metrics_json with "validation" and "calibration" sections.

Usage:
    PYTHONPATH=. ./venv/bin/python scripts/train_v1_manifest.py [--holdout-frac 0.2]
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

from app.db.session import SessionLocal
from app.services.ml.data_fetcher import (
    fetch_anchor_points_as_training_data,
    generate_physics_anchor_rows,
    fetch_material_properties,
    fetch_training_data,
)
from app.services.ml.ballistic_ml import train_from_dataframe
from app.services.ml.feature_contract import CONTRACT_V1
from app.services.ml.model_bundle import get_model_bundle, _BUNDLE_CACHE, _version_dir

BFD_TARGET = "backface_deformation_mm"
CLASS_TARGET = "perforated"
MANIFEST_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "manifests")


def grouped_holdout(df: pd.DataFrame, frac: float, seed: int) -> pd.Series:
    """Boolean mask: True -> validation. Deterministic per (vest_id, seed)."""
    group = df["vest_id"].astype(str) if "vest_id" in df.columns else df["vest_code"].astype(str)
    keys = group.map(lambda g: int.from_bytes(
        hashlib.sha256(f"{g}|{seed}".encode()).digest()[:8], "big") / 2**64)
    # hold out whole groups until ~frac of rows is covered
    group_sizes = df.groupby(group).size().sort_values(ascending=False)
    n_target = max(1, int(len(df) * frac))
    chosen, covered = set(), 0
    for g, n in group_sizes.items():
        if covered >= n_target and covered > 0:
            break
        chosen.add(g)
        covered += n
    return group.isin(chosen)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--model-name", type=str, default=None)
    args = ap.parse_args()

    db = SessionLocal()
    print("fetching training data…")
    df_real, warnings, data_meta = fetch_training_data(db, verbose=False, ignore_anchor_points=True)
    anchor_df, anchor_meta = fetch_anchor_points_as_training_data(db)
    physics_df = generate_physics_anchor_rows(db)
    if not physics_df.empty:
        anchor_df = pd.concat([anchor_df, physics_df], ignore_index=True)
    material_properties = fetch_material_properties(db)
    print(f"real rows: {len(df_real)} | anchor rows: {len(anchor_df)} | materials: {len(material_properties)}")

    if df_real.empty:
        raise SystemExit("no real shot data — cannot validate")

    group_col = "vest_id" if "vest_id" in df_real.columns else "vest_code"
    holdout_mask = grouped_holdout(df_real, args.holdout_frac, args.seed)
    df_val = df_real[holdout_mask].copy()
    df_train = pd.concat([df_real[~holdout_mask], anchor_df], ignore_index=True)
    n_groups_val = df_val[group_col].nunique()
    n_groups_train = df_real[~holdout_mask][group_col].nunique()
    print(f"train: {len(df_train)} rows / {n_groups_train} vests (+{len(anchor_df)} anchors)")
    print(f"val:   {len(df_val)} rows / {n_groups_val} vests")
    if len(df_val) < 10:
        raise SystemExit("validation split too small — lower --holdout-frac")

    merged_meta = dict(data_meta or {})
    merged_meta.update({
        "anchor_point_training_rows": len(anchor_df),
        "validation_manifest": {
            "holdout_frac": args.holdout_frac,
            "seed": args.seed,
            "group_column": group_col,
            "n_train_rows": int(len(df_train)),
            "n_val_rows": int(len(df_val)),
            "n_val_groups": int(n_groups_val),
            "val_groups": sorted(df_val[group_col].astype(str).unique().tolist()),
        },
    })

    model_name = args.model_name or f"NPOptimized-v1-{datetime.utcnow():%m%d}"
    print(f"training under {CONTRACT_V1} as '{model_name}'…")
    metadata, preprocessor_bytes, model_files = train_from_dataframe(
        df_train,
        material_properties,
        model_name=model_name,
        warnings=warnings,
        data_metadata=merged_meta,
        use_log_transform=True,
        contract_version=CONTRACT_V1,
    )
    version = metadata["version"]
    print("version:", version)

    # persist ModelRun row (train_from_dataframe doesn't)
    from app.db.models.model_run import ModelRun
    run = ModelRun(
        model_name=model_name,
        model_type="ballistic",
        version=version,
        training_completed_at=datetime.utcnow(),
        training_row_count=len(df_train),
        metrics_json=metadata["metrics"],
        hyperparameters_json=metadata.get("hyperparameters"),
        artifact_path=f"ballistic/versions/{version}",
        preprocessor_file=preprocessor_bytes,
        model_file=model_files.get(f"{BFD_TARGET}.pkl"),
        classifier_file=model_files.get(f"{CLASS_TARGET}.pkl"),
    )
    db.add(run)
    db.commit()

    # evaluate the fresh bundle on held-out vests
    _BUNDLE_CACHE.pop(version, None)
    bundle = get_model_bundle(version, db_session=db)
    val_rows = df_val.drop(columns=[BFD_TARGET, CLASS_TARGET, "pass_fail"], errors="ignore").to_dict("records")
    frame = bundle.build_input_frame(val_rows)
    bfd_pred = bundle.predict_frame(frame)
    perf_pred = bundle.predict_perforation_frame(frame)

    y_bfd = df_val[BFD_TARGET].astype(float).values
    resid = bfd_pred - y_bfd
    valid = ~np.isnan(y_bfd)
    bfd_metrics = {
        "n": int(valid.sum()),
        "mae_mm": float(np.abs(resid[valid]).mean()) if valid.any() else None,
        "mape": float(np.mean(np.abs(resid[valid]) / np.clip(y_bfd[valid], 1e-6, None))) if valid.any() else None,
        "bias_mm": float(resid[valid].mean()) if valid.any() else None,
        "residual_sigma_mm": float(resid[valid].std()) if valid.any() else None,
        "r": float(np.corrcoef(bfd_pred[valid], y_bfd[valid])[0, 1]) if valid.sum() > 3 else None,
    }
    per_vest = []
    for g, idx in df_val.groupby(group_col).groups.items():
        r = resid[df_val.index.isin(idx)]
        y = y_bfd[df_val.index.isin(idx)]
        v = ~np.isnan(y)
        if v.any():
            per_vest.append({
                "group": str(g), "n": int(v.sum()),
                "mae_mm": float(np.abs(r[v]).mean()),
                "bias_mm": float(r[v].mean()),
            })

    perf_eval, calibration = None, None
    if CLASS_TARGET in df_val.columns and perf_pred is not None:
        y_perf = pd.to_numeric(df_val[CLASS_TARGET], errors="coerce").values
        m = ~np.isnan(y_perf)
        n_pos = int((y_perf[m] == 1).sum())
        n_neg = int((y_perf[m] == 0).sum())
        if m.sum() and n_pos and n_neg:
            from sklearn.metrics import roc_auc_score, brier_score_loss
            auc = float(roc_auc_score(y_perf[m], perf_pred[m]))
            brier = float(brier_score_loss(y_perf[m], perf_pred[m]))
            perf_eval = {"n": int(m.sum()), "n_pos": n_pos, "n_neg": n_neg,
                         "auc": auc, "brier": brier}
            # isotonic calibration on holdout scores
            from sklearn.isotonic import IsotonicRegression
            iso = IsotonicRegression(out_of_bounds="clip").fit(perf_pred[m], y_perf[m])
            xs = np.linspace(0.0, 1.0, 21)
            calibration = {
                "method": "isotonic",
                "x": xs.tolist(),
                "y": iso.predict(xs).tolist(),
                "fit_n": int(m.sum()), "fit_pos": n_pos,
            }
            print(f"perforation: AUC={auc:.3f} Brier={brier:.3f} (pos={n_pos}, neg={n_neg})")
        else:
            perf_eval = {"n": int(m.sum()), "n_pos": n_pos, "n_neg": n_neg,
                         "auc": None, "brier": None,
                         "note": "insufficient positives/negatives in holdout for AUC"}
            print(f"perforation: insufficient class balance (pos={n_pos}, neg={n_neg})")

    print(f"BFD holdout: MAE={bfd_metrics['mae_mm']:.2f}mm MAPE={bfd_metrics['mape']:.1%} "
          f"bias={bfd_metrics['bias_mm']:.2f} sigma={bfd_metrics['residual_sigma_mm']:.2f} r={bfd_metrics['r']}")

    # Grouped 5-fold CV over real rows — a more stable generalization estimate
    # than a single 2-vest holdout. Reuses the fitted preprocessor; a fresh
    # regressor per fold with the tree count early stopping discovered.
    cv_metrics = None
    try:
        import io as _io
        import joblib
        from sklearn.model_selection import GroupKFold
        from app.services.ml.ballistic_ml import build_regressor
        from app.services.ml.feature_contract import build_features

        df_cv = df_real[df_real[BFD_TARGET].notna() & df_real[group_col].notna()].copy()
        if df_cv[group_col].nunique() >= 5:
            df_cv = build_features(df_cv, material_properties, contract_version=CONTRACT_V1)
            pre = joblib.load(_io.BytesIO(preprocessor_bytes))
            feat_cols = metadata["feature_columns"]
            Xc = pre.transform(df_cv[feat_cols])
            yc_log = np.log1p(np.clip(df_cv[BFD_TARGET].astype(float).values, 0, None))
            n_est = ((metadata.get("metrics", {}).get(f"{BFD_TARGET}_regression") or {})
                     .get("n_estimators_used") or 300)
            maes, mapes = [], []
            for tr, te in GroupKFold(5).split(Xc, groups=df_cv[group_col].astype(str).values):
                m = build_regressor(n_estimators=n_est)
                m.set_params(early_stopping_rounds=None)
                m.fit(Xc[tr], yc_log[tr])
                pred = np.expm1(m.predict(Xc[te]))
                y_te = np.expm1(yc_log[te])
                maes.append(float(np.abs(pred - y_te).mean()))
                mapes.append(float(np.mean(np.abs(pred - y_te) / np.clip(y_te, 1e-6, None))))
            cv_metrics = {
                "folds": len(maes),
                "mae_mm_mean": float(np.mean(maes)), "mae_mm_std": float(np.std(maes)),
                "mape_mean": float(np.mean(mapes)), "mape_std": float(np.std(mapes)),
            }
            print(f"BFD 5-fold CV: MAE={cv_metrics['mae_mm_mean']:.2f}±{cv_metrics['mae_mm_std']:.2f}mm "
                  f"MAPE={cv_metrics['mape_mean']:.1%}")
    except Exception as e:
        print(f"CV skipped: {e}")

    validation = {
        "evaluated_at": datetime.utcnow().isoformat(),
        "manifest": merged_meta["validation_manifest"],
        "bfd_holdout": bfd_metrics,
        "bfd_cv": cv_metrics,
        "bfd_per_vest": per_vest,
        "perforation_holdout": perf_eval,
    }
    calibration_meta = {
        "bfd_residual_sigma_mm": bfd_metrics["residual_sigma_mm"],
        "bfd_residual_bias_mm": bfd_metrics["bias_mm"],
        "perforation_isotonic": calibration,
    }

    # write manifest file
    os.makedirs(MANIFEST_DIR, exist_ok=True)
    manifest_path = os.path.join(MANIFEST_DIR, f"{version}_validation.json")
    with open(manifest_path, "w") as f:
        json.dump(validation, f, indent=2)
    print("manifest:", manifest_path)

    # update metadata.json + ModelRun metrics
    meta_path = os.path.join(_version_dir(version), "metadata.json")
    with open(meta_path) as f:
        meta = json.load(f)
    meta["validation"] = validation
    meta["calibration"] = calibration_meta
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    run.metrics_json = {**(run.metrics_json or {}), "validation": validation}
    db.commit()
    db.close()
    print("done — metadata + ModelRun updated")


if __name__ == "__main__":
    sys.exit(main())
