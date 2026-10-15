"""
Immutable model bundles for prediction and simulation.

Every bundle is resolved by (model_version, content hash): preprocessor,
regressors, classifiers, feature contract, material snapshot, and metadata
travel together. Loading a bundle never writes shared files, so concurrent
runs against different versions cannot overwrite each other's artifacts.

Artifact source order per version:
  1. model_runs DB blobs (preprocessor_file / model_file / classifier_file)
  2. storage/model_artifacts/ballistic/versions/<version>/ files
"""
import hashlib
import io
import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from app.services.ml.feature_contract import (
    CONTRACT_V0,
    align_to_contract,
    build_features,
    categorical_feature_names,
)

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "storage", "model_artifacts", "ballistic",
)
VERSIONS_DIR = os.path.join(MODEL_DIR, "versions")

BFD_TARGET = "backface_deformation_mm"
PERFORATION_TARGET = "perforated"
PASS_FAIL_TARGET = "pass_fail"


@dataclass(frozen=True)
class ModelBundle:
    """An immutable, fully-resolved model artifact set."""

    version: str
    model_name: str
    bundle_hash: str
    feature_contract_version: str

    metadata: Dict[str, Any]
    feature_columns: List[str]
    categorical_columns: List[str]
    numeric_columns: List[str]
    feature_toggles: Optional[Dict[str, bool]]
    training_ranges: Dict[str, Any]
    material_snapshot: Dict[str, Dict[str, Any]]

    preprocessor: Any
    bfd_artifact: Optional[Any]          # {"model": XGBRegressor, "use_log_transform": bool} or raw model
    perforation_model: Optional[Any]
    pass_fail_model: Optional[Any]
    categorical_names: frozenset = field(default=frozenset)

    # -- feature + prediction API -------------------------------------------

    def build_input_frame(self, rows: List[Dict[str, Any]],
                          property_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
                          validate: bool = False) -> pd.DataFrame:
        """Build the contract-aligned feature frame for raw input rows.

        property_overrides replaces material snapshot properties for this
        batch only (the frozen snapshot itself is never mutated).
        """
        material_properties = self.material_snapshot
        if property_overrides is not None:
            material_properties = {k: dict(v) for k, v in material_properties.items()}
            for mat, props in property_overrides.items():
                material_properties.setdefault(mat, {}).update(props)

        df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
        engineered = build_features(
            df,
            material_properties,
            feature_toggles=self.feature_toggles,
            contract_version=self.feature_contract_version,
            validate=validate,
        )
        return align_to_contract(engineered, self.feature_columns, set(self.categorical_names))

    def _transform(self, frame: pd.DataFrame) -> Any:
        return self.preprocessor.transform(frame)

    def predict_frame(self, frame: pd.DataFrame) -> np.ndarray:
        """BFD in millimetres for an already contract-aligned frame.
        Applies the stored log1p inverse transform exactly once."""
        if self.bfd_artifact is None:
            raise RuntimeError(f"Bundle {self.version} has no BFD regressor")
        artifact = self.bfd_artifact
        if isinstance(artifact, dict):
            model = artifact["model"]
            use_log_transform = bool(artifact.get("use_log_transform", False))
        else:
            model = artifact
            use_log_transform = False
        preds = np.asarray(model.predict(self._transform(frame)), dtype=float)
        if use_log_transform:
            preds = np.expm1(preds)
        return preds

    def predict_perforation_frame(self, frame: pd.DataFrame) -> Optional[np.ndarray]:
        """Raw classifier score for an aligned frame. Exploratory only —
        not a calibrated penetration probability."""
        if self.perforation_model is None:
            return None
        return np.asarray(self.perforation_model.predict_proba(self._transform(frame))[:, 1], dtype=float)

    def classifier_probabilities(self, frame: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Per-row positive-class scores for every available classifier
        ({'perforated': array, 'pass_fail': array}). Raw scores, exploratory."""
        out: Dict[str, np.ndarray] = {}
        for name, model in (
            (PERFORATION_TARGET, self.perforation_model),
            (PASS_FAIL_TARGET, self.pass_fail_model),
        ):
            if model is not None:
                out[name] = np.asarray(
                    model.predict_proba(self._transform(frame))[:, 1], dtype=float
                )
        return out

    def predict_bfd(self, rows: List[Dict[str, Any]],
                    property_overrides: Optional[Dict[str, Dict[str, Any]]] = None) -> np.ndarray:
        frame = self.build_input_frame(rows, property_overrides=property_overrides)
        return self.predict_frame(frame)

    def predict_perforation_score(self, rows: List[Dict[str, Any]],
                                  property_overrides: Optional[Dict[str, Dict[str, Any]]] = None
                                  ) -> Optional[np.ndarray]:
        if self.perforation_model is None:
            return None
        frame = self.build_input_frame(rows, property_overrides=property_overrides)
        return self.predict_perforation_frame(frame)


# ---------------------------------------------------------------------------
# Loading and caching
# ---------------------------------------------------------------------------

_BUNDLE_CACHE: Dict[str, ModelBundle] = {}
_CACHE_LOCK = threading.Lock()


def _version_dir(version: str) -> str:
    return os.path.join(VERSIONS_DIR, version)


def _load_version_metadata(version: str, model_run) -> Dict[str, Any]:
    """metadata.json carries feature_columns/toggles/material snapshot; fall
    back to the model_runs row when the filesystem metadata is missing."""
    meta_path = os.path.join(_version_dir(version), "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            return json.load(f)

    if model_run is None:
        raise ValueError(f"Model version {version} has no metadata (neither filesystem nor DB)")

    return {
        "version": model_run.version,
        "model_name": model_run.model_name,
        "trained_at": model_run.training_completed_at.isoformat()
            if model_run.training_completed_at else None,
        "metrics": model_run.metrics_json,
        "hyperparameters": model_run.hyperparameters_json,
        "training_data_count": model_run.training_row_count,
    }


def _artifact_bytes(version: str, model_run) -> Dict[str, Optional[bytes]]:
    """Collect raw artifact bytes: DB blobs first, filesystem fallback.
    Keys: preprocessor, backface_deformation_mm, perforated, pass_fail."""
    out: Dict[str, Optional[bytes]] = {
        "preprocessor": None, BFD_TARGET: None, PERFORATION_TARGET: None, PASS_FAIL_TARGET: None,
    }
    if model_run is not None:
        out["preprocessor"] = model_run.preprocessor_file
        out[BFD_TARGET] = model_run.model_file
        out[PERFORATION_TARGET] = model_run.classifier_file

    vdir = _version_dir(version)
    for key, filename in (
        ("preprocessor", "preprocessor.pkl"),
        (BFD_TARGET, "backface_deformation_mm.pkl"),
        (PERFORATION_TARGET, "perforated.pkl"),
        (PASS_FAIL_TARGET, "pass_fail.pkl"),
    ):
        if out[key] is None:
            path = os.path.join(vdir, filename)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    out[key] = f.read()
    return out


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, default=str).encode("utf-8")


def get_model_bundle(version: str, db_session=None, force_reload: bool = False) -> ModelBundle:
    """Resolve an immutable bundle for a model version. Cached per version;
    a version is treated as immutable — retraining must mint a new version."""
    with _CACHE_LOCK:
        if not force_reload and version in _BUNDLE_CACHE:
            return _BUNDLE_CACHE[version]

        model_run = None
        if db_session is not None:
            from app.db.models.model_run import ModelRun
            model_run = db_session.query(ModelRun).filter(
                ModelRun.version == version,
                ModelRun.model_type == "ballistic",
            ).first()
            if model_run is None:
                raise ValueError(f"Model version {version} not found in database")

        metadata = _load_version_metadata(version, model_run)
        artifacts = _artifact_bytes(version, model_run)

        if artifacts["preprocessor"] is None:
            raise ValueError(f"Model version {version} has no preprocessor artifact")
        if artifacts[BFD_TARGET] is None:
            raise ValueError(f"Model version {version} has no BFD regressor artifact")

        bundle_hash = hashlib.sha256(
            b"|".join(
                [artifacts["preprocessor"], artifacts[BFD_TARGET]]
                + [artifacts[k] for k in (PERFORATION_TARGET, PASS_FAIL_TARGET) if artifacts[k]]
                + [_canonical_json(metadata.get("feature_columns", [])),
                   _canonical_json(metadata.get("feature_toggles", {}))]
            )
        ).hexdigest()

        bundle = ModelBundle(
            version=version,
            model_name=metadata.get("model_name", version),
            bundle_hash=bundle_hash,
            feature_contract_version=metadata.get("feature_contract_version", CONTRACT_V0),
            metadata=metadata,
            feature_columns=list(metadata.get("feature_columns", [])),
            categorical_columns=list(metadata.get("categorical_columns", [])),
            numeric_columns=list(metadata.get("numeric_columns", [])),
            feature_toggles=metadata.get("feature_toggles"),
            training_ranges=metadata.get("training_ranges", {}),
            material_snapshot=metadata.get("material_properties", {}),
            preprocessor=joblib.load(io.BytesIO(artifacts["preprocessor"])),
            bfd_artifact=joblib.load(io.BytesIO(artifacts[BFD_TARGET])),
            perforation_model=(
                joblib.load(io.BytesIO(artifacts[PERFORATION_TARGET]))
                if artifacts[PERFORATION_TARGET] else None
            ),
            pass_fail_model=(
                joblib.load(io.BytesIO(artifacts[PASS_FAIL_TARGET]))
                if artifacts[PASS_FAIL_TARGET] else None
            ),
            categorical_names=frozenset(categorical_feature_names(
                metadata.get("material_properties", {})
            )),
        )

        if not bundle.feature_columns:
            raise ValueError(f"Model version {version} metadata has no feature_columns")

        _BUNDLE_CACHE[version] = bundle
        return bundle


def get_default_version(db_session=None) -> Optional[str]:
    """Resolve the active model version: the version activated via
    load_model_version (metadata.json) if present, else the most recent
    model_runs row that has artifacts."""
    meta_path = os.path.join(MODEL_DIR, "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                version = json.load(f).get("version")
            if version:
                return version
        except Exception:
            pass
    if db_session is not None:
        from app.db.models.model_run import ModelRun
        run = db_session.query(ModelRun).filter(
            ModelRun.model_type == "ballistic",
            ModelRun.model_file.isnot(None),
        ).order_by(ModelRun.created_at.desc()).first()
        if run is not None:
            return run.version
    return None


def get_active_bundle(db_session=None) -> ModelBundle:
    version = get_default_version(db_session)
    if version is None:
        raise ValueError("No trained model found. Run training first.")
    return get_model_bundle(version, db_session=db_session)


def list_available_bundle_versions(db_session=None) -> List[Dict[str, Any]]:
    """Versions resolvable as bundles (DB row or filesystem dir present)."""
    versions = set(os.listdir(VERSIONS_DIR)) if os.path.isdir(VERSIONS_DIR) else set()
    names: Dict[str, str] = {}
    if db_session is not None:
        from app.db.models.model_run import ModelRun
        for v, name in db_session.query(ModelRun.version, ModelRun.model_name).filter(
            ModelRun.model_type == "ballistic", ModelRun.model_file.isnot(None)
        ).all():
            versions.add(v)
            names[v] = name
    return [
        {"version": v, "model_name": names.get(v)}
        for v in sorted(versions)
    ]
