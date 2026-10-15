"""
Risk simulation executor.

One run = `run.requested_draws` simulated units. A unit is one realization of
the design (all material property draws resolved together) put through the
protocol revision's shot plan. Every draw is predicted by the immutable
ModelBundle; nothing is written to shared model artifact files.

Outputs (result_json):
- bfd histogram + survival curve over ALL simulated shots
- per-shot and protocol-level exceedance frequencies (Wilson intervals)
- expected events per 1000 shots
- near-worst finite event frequency
- stress-envelope summary
- readiness per output: 'exploratory' | 'validated_within_support' |
  'blocked' (value null with reason) — never a fabricated number
- calculation_trace: every variable, distribution, provenance, and rule,
  so the methodology subtab can show the full computation.

Uncertainty here is INPUT VARIATION ONLY (accepted-material tolerances +
velocity windows). Model/residual uncertainty is layered separately in
Milestone D.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.db.models import (
    Ammunition,
    MaterialPropertySpec,
    ProtocolRevision,
    RiskScenario,
    RiskSimulationRun,
    Vest,
    VestLayer,
)
from app.services.ml.model_bundle import ModelBundle
from app.services.risk.distributions import (
    ResolutionResult,
    draws_to_property_overrides,
    resolve_design_distributions,
)
from app.services.risk.sampling import Sampler, SampleVariable

DEFAULT_BFD_LIMIT_MM = 44.0
CHUNK_UNITS = 50

# Shots scoring above this are treated as perforated: BFD is physically
# meaningless for them and they are excluded from BFD statistics
# (same convention as the single-shot predict path in ballistic_ml.py).
PERF_BFD_MASK_THRESHOLD = 0.9


@dataclass
class ShotPlan:
    shot_number: int
    ammunition: Optional[Ammunition]
    side: str
    angle_degrees: Optional[float]
    conditioning: Optional[str]
    velocity_spec: Optional[Dict[str, Any]] = None   # {family, parameters}


@dataclass
class ScenarioContext:
    scenario: RiskScenario
    vest: Vest
    vest_composition: str
    total_layers: int
    material_type: Optional[str]
    shot_plan: List[ShotPlan]
    bfd_limit_mm: float
    threat_level: Optional[str]
    geometry_name: Optional[str]
    panel_surface_area_m2: Optional[float]
    resolution: ResolutionResult
    sampler: Sampler
    velocity_vars: List[SampleVariable]


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def _composition_string(db: Session, vest: Vest) -> str:
    from app.db.models import Material
    layers = (
        db.query(VestLayer)
        .filter(VestLayer.vest_id == vest.id)
        .order_by(VestLayer.layer_index)
        .all()
    )
    parts = []
    for vl in layers:
        mat = db.query(Material).filter(Material.id == vl.material_id).first()
        if mat:
            parts.append(f"{vl.layer_count or 1} {mat.name}")
    return " + ".join(parts)


def _velocity_spec_for_shot(shot_cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Protocol shot config -> velocity sampling spec.

    window_interpretation: 'symmetric' -> uniform in [ref-window, ref+window];
    'lower_only' -> uniform in [ref-window, ref]; 'upper_only' -> [ref, ref+window].
    Default when bounds exist but interpretation is unset: symmetric.
    """
    ref = shot_cfg.get("reference_velocity_m_s")
    window = shot_cfg.get("velocity_window_m_s")
    if ref is None:
        lo, hi = shot_cfg.get("velocity_lower_m_s"), shot_cfg.get("velocity_upper_m_s")
        if lo is None or hi is None:
            return None
        return {"family": "uniform", "parameters": {"a": float(lo), "b": float(hi)}}
    if window is None:
        return {"family": "constant", "parameters": {"value": float(ref)}}
    interp = shot_cfg.get("window_interpretation", "symmetric")
    lo = float(ref) - window if interp in ("symmetric", "lower_only") else float(ref)
    hi = float(ref) + window if interp in ("symmetric", "upper_only") else float(ref)
    return {"family": "uniform", "parameters": {"a": lo, "b": hi}}


def build_scenario_context(db: Session, scenario: RiskScenario) -> ScenarioContext:
    vest = db.query(Vest).filter(Vest.id == scenario.design_id).first()
    if vest is None:
        raise ValueError(f"Design vest {scenario.design_id} not found")

    composition = _composition_string(db, vest)
    if not composition:
        raise ValueError(f"Vest {vest.vest_code} has no layers/materials")

    layers = db.query(VestLayer).filter(VestLayer.vest_id == vest.id).all()
    total_layers = sum(vl.layer_count or 1 for vl in layers)

    classes = set()
    from app.db.models import Material
    for vl in layers:
        mat = db.query(Material).filter(Material.id == vl.material_id).first()
        if mat and mat.material_class:
            classes.add(mat.material_class)
    material_type = ", ".join(sorted(classes)) if classes else None

    # shot plan from the protocol revision (fallback: one nominal shot)
    shot_plan: List[ShotPlan] = []
    threat_level: Optional[str] = None
    if scenario.protocol_revision_id:
        rev = db.query(ProtocolRevision).filter(
            ProtocolRevision.id == scenario.protocol_revision_id
        ).first()
        if rev:
            threat_level = rev.level
        if rev and rev.shots_json:
            for i, shot_cfg in enumerate(rev.shots_json, start=1):
                ammo = None
                if shot_cfg.get("ammunition_id"):
                    ammo = db.query(Ammunition).filter(
                        Ammunition.id == shot_cfg["ammunition_id"]
                    ).first()
                shot_plan.append(ShotPlan(
                    shot_number=int(shot_cfg.get("shot_number", i)),
                    ammunition=ammo,
                    side=shot_cfg.get("side", "front"),
                    angle_degrees=shot_cfg.get("angle_degrees"),
                    conditioning=shot_cfg.get("conditioning"),
                    velocity_spec=_velocity_spec_for_shot(shot_cfg),
                ))
    if not shot_plan:
        shot_plan = [ShotPlan(shot_number=1, ammunition=None, side="front",
                              angle_degrees=None, conditioning=None, velocity_spec=None)]

    rule = scenario.outcome_rule_json or {}
    bfd_limit = float(rule.get("bfd_threshold_mm", DEFAULT_BFD_LIMIT_MM))

    # Resolve panel surface area from the vest's first compatible geometry,
    # mirroring how training rows resolve it from the test session geometry.
    from app.db.models import Geometry
    geometry_name = None
    panel_surface_area_m2 = None
    for gid in (vest.compatible_geometry_ids or []):
        geo = db.query(Geometry).filter(Geometry.id == gid).first()
        if not geo:
            continue
        size_areas = (geo.surface_areas or {}).get('M') or {}
        front_area = float(size_areas.get('front') or 0)
        back_area = float(size_areas.get('back') or 0)
        if front_area + back_area > 0:
            geometry_name = geo.name
            panel_surface_area_m2 = front_area + back_area
            break

    resolution = resolve_design_distributions(db, vest)

    # velocity variables (one per distinct shot plan velocity spec), drawn
    # inside the sampler so every draw is reproducible from the run seed
    velocity_vars = []
    for sp in shot_plan:
        if sp.velocity_spec:
            velocity_vars.append(SampleVariable(
                key=f"velocity|shot_{sp.shot_number}",
                material="",
                property_key="impact_velocity_mps",
                direction="none",
                spec=sp.velocity_spec,
                scope="unit",
                scope_id="unit",
                provenance="protocol_spec",
            ))

    sampler = Sampler(
        resolution.variables + velocity_vars,
        correlation_groups=(scenario.dependency_snapshot_json or {}).get("correlation_groups"),
    )

    return ScenarioContext(
        scenario=scenario,
        vest=vest,
        vest_composition=composition,
        total_layers=total_layers,
        material_type=material_type,
        shot_plan=shot_plan,
        bfd_limit_mm=bfd_limit,
        threat_level=threat_level,
        geometry_name=geometry_name,
        panel_surface_area_m2=panel_surface_area_m2,
        resolution=resolution,
        sampler=sampler,
        velocity_vars=velocity_vars,
    )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _base_row(ctx: ScenarioContext, sp: ShotPlan) -> Dict[str, Any]:
    ammo = sp.ammunition
    return {
        "vest_composition": ctx.vest_composition,
        "number_of_layers": ctx.total_layers,
        "material_type": ctx.material_type,
        "vest_type": ctx.vest.vest_type,
        "is_female": bool(ctx.vest.is_female) if ctx.vest.is_female is not None else False,
        "threat_level": (
            (ctx.scenario.outcome_rule_json or {}).get("threat_level")
            or ctx.threat_level
        ),
        "shot_number": sp.shot_number,
        "panel_side": sp.side,
        "impact_angle_deg": sp.angle_degrees,
        "condition": sp.conditioning,
        "ammunition_used": ammo.name if ammo else None,
        "bullet_mass_g": (
            float(ammo.projectile_mass_grams)
            if ammo and ammo.projectile_mass_grams
            else float(ammo.projectile_mass_grains) * 0.0647989
            if ammo and ammo.projectile_mass_grains else None
        ),
        "caliber_diameter_mm": float(ammo.caliber_diameter_mm)
            if ammo and ammo.caliber_diameter_mm else None,
        "caliber_length_mm": float(ammo.caliber_length_mm)
            if ammo and ammo.caliber_length_mm else None,
        "flexibility_rating": int(ctx.vest.flexibility_rating)
            if ctx.vest.flexibility_rating is not None else 0,
        "is_panel_sewn": int(ctx.vest.is_panel_sewn)
            if ctx.vest.is_panel_sewn is not None else 0,
        "weight_g": float(ctx.vest.weight_g) if ctx.vest.weight_g else None,
        "ply_orientations": None,
        "geometry_name": ctx.geometry_name,
        "panel_surface_area_m2": ctx.panel_surface_area_m2,
        "temperature_c": 21.0,
        "humidity_pct": 50.0,
    }


def _preload_spec_windows(db: Session, ctx: ScenarioContext) -> Dict[str, tuple]:
    """spec windows keyed by variable key, loaded once per run."""
    windows: Dict[str, tuple] = {}
    for rm in ctx.resolution.materials:
        for var in rm.variables:
            spec = db.query(MaterialPropertySpec).filter(
                MaterialPropertySpec.material_id == rm.material.id,
                MaterialPropertySpec.property_key == var.property_key,
                MaterialPropertySpec.direction == var.direction,
            ).first()
            if spec is not None:
                windows[var.key] = (
                    float(spec.lower_limit) if spec.lower_limit is not None else None,
                    float(spec.upper_limit) if spec.upper_limit is not None else None,
                )
    return windows


def _pre_qc_reject(draw: Dict[str, float], windows: Dict[str, tuple]) -> bool:
    """pre_qc mode: reject a unit when a drawn property falls outside its
    spec window. Rejected draws are counted and reported, not resampled."""
    for key, (lo, hi) in windows.items():
        val = draw.get(key)
        if val is None:
            continue
        if lo is not None and val < lo:
            return True
        if hi is not None and val > hi:
            return True
    return False


def _wilson(k: int, n: int, z: float = 1.959963984540054) -> Dict[str, Any]:
    if n == 0:
        # all shots masked/perforated — no evaluable shots, fields null
        return {"estimate": None, "ci95_low": None, "ci95_high": None,
                "n": 0, "events": int(k)}
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"estimate": float(p), "ci95_low": float(center - half), "ci95_high": float(center + half),
            "n": int(n), "events": int(k)}


def run_simulation(run_id, db: Session, bundle: ModelBundle) -> None:
    """Execute a queued run. Callable from a worker thread; the run row is
    the progress/checkpoint record (cancel by setting status='canceled')."""
    run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    scenario = db.query(RiskScenario).filter(RiskScenario.id == run.scenario_id).first()
    if scenario is None:
        raise ValueError(f"Scenario {run.scenario_id} not found")

    run.status = "running"
    run.started_at = datetime.utcnow()
    run.model_bundle_hash = bundle.bundle_hash
    run.feature_contract_version = bundle.feature_contract_version
    db.commit()

    ctx = build_scenario_context(db, scenario)
    ctx.sampler.reset_population()
    rng = np.random.default_rng(int(run.seed))

    # Milestone D calibration artifacts (present on bundles trained via
    # train_v1_manifest.py; absent -> raw model behavior, exploratory)
    cal = (bundle.metadata or {}).get("calibration") or {}
    validation_meta = (bundle.metadata or {}).get("validation") or {}
    bfd_bias = float(cal.get("bfd_residual_bias_mm") or 0.0)
    bfd_sigma = cal.get("bfd_residual_sigma_mm")
    perf_iso = cal.get("perforation_isotonic")  # {"x": [...], "y": [...]}

    n_units = int(run.requested_draws)
    n_shots = len(ctx.shot_plan)
    limit = ctx.bfd_limit_mm
    pre_qc = scenario.population_mode == "pre_qc"
    spec_windows = _preload_spec_windows(db, ctx) if pre_qc else {}

    # outcome event spec (conjunctive, may be None)
    nw = scenario.near_worst_event_json or {}

    unit_bfd: List[np.ndarray] = []          # per unit: array of shot BFDs
    unit_perf: List[Optional[np.ndarray]] = []  # per unit: perforation scores per shot
    velocities: List[List[float]] = []
    unit_draws: List[Dict[str, float]] = []
    n_rejected = 0
    done = 0

    # incremental aggregates -> interim result_json each chunk (live UI)
    interim_edges = np.linspace(0, limit * 3, 41)
    interim_hist = np.zeros(len(interim_edges) - 1, dtype=int)
    exceed_k = 0
    per_shot_k = np.zeros(n_shots, dtype=int)
    per_shot_valid = np.zeros(n_shots, dtype=int)
    proto_k = 0
    perf_sum = 0.0
    per_shot_perf_sum = np.zeros(n_shots, dtype=float)
    perf_n = 0
    perf_k = 0          # shots masked as perforated (score > threshold)
    valid_n = 0         # shots that contribute to BFD statistics

    def _interim_result() -> Dict[str, Any]:
        n_eval_i = done * n_shots
        res: Dict[str, Any] = {
            "partial": True,
            "n_units": done,
            "n_shots_per_unit": n_shots,
            "n_predicted_shots": n_eval_i,
            "n_rejected_pre_qc": n_rejected if pre_qc else 0,
            "bfd_limit_mm": limit,
            "histogram": {"bin_edges": interim_edges.tolist(),
                          "counts": interim_hist.tolist()},
            "n_perforated_shots": perf_k,
            "perforations_per_1000_shots": (
                float(perf_k / n_eval_i * 1000) if n_eval_i else None
            ),
            "per_shot_exceedance": [
                {"shot_number": ctx.shot_plan[si].shot_number,
                 **_wilson(int(per_shot_k[si]), int(per_shot_valid[si]))}
                for si in range(n_shots)
            ] if done else [],
            "protocol_exceedance": _wilson(proto_k, done),
            "expected_events_per_1000_shots": (
                float(exceed_k / valid_n * 1000) if valid_n else None
            ),
            "combined_failure_rate": _wilson(exceed_k + perf_k, n_eval_i),
            "combined_events_per_1000_shots": (
                float((exceed_k + perf_k) / n_eval_i * 1000) if n_eval_i else None
            ),
        }
        if perf_n:
            res["perforation"] = {
                "mean_score": perf_sum / perf_n,
                "per_shot_mean": (per_shot_perf_sum / done).tolist() if done else [],
                "uncalibrated": True,
            }
        return res

    try:
        for chunk_start in range(0, n_units, CHUNK_UNITS):
            # cancellation checkpoint
            db.refresh(run)
            if run.status == "canceled":
                db.commit()
                return

            chunk_frames = []
            chunk_meta = []  # (unit_idx_local, n_shot_rows, draw)
            for _ in range(min(CHUNK_UNITS, n_units - chunk_start)):
                draw = ctx.sampler.draw_unit(rng).values

                if pre_qc and _pre_qc_reject(draw, spec_windows):
                    n_rejected += 1
                    continue

                overrides = draws_to_property_overrides(ctx.resolution, draw)
                unit_rows = []
                unit_vel = []
                for sp in ctx.shot_plan:
                    row = _base_row(ctx, sp)
                    row["impact_velocity_mps"] = draw.get(f"velocity|shot_{sp.shot_number}")
                    unit_vel.append(row.get("impact_velocity_mps"))
                    unit_rows.append(row)

                frame = bundle.build_input_frame(unit_rows, property_overrides=overrides)
                chunk_frames.append(frame)
                chunk_meta.append((draw, unit_vel))

            if not chunk_frames:
                continue

            import pandas as pd
            chunk_frame = pd.concat(chunk_frames, ignore_index=True)
            preds = bundle.predict_frame(chunk_frame)
            # residual calibration: de-bias + holdout-estimated noise
            if bfd_sigma:
                preds = preds - bfd_bias + rng.normal(0.0, float(bfd_sigma), len(preds))
                preds = np.clip(preds, 0.0, None)
            elif bfd_bias:
                preds = np.clip(preds - bfd_bias, 0.0, None)

            perf_preds = bundle.predict_perforation_frame(chunk_frame)
            if perf_preds is not None and perf_iso:
                # isotonic-calibrated penetration probability
                perf_preds = np.interp(perf_preds, perf_iso["x"], perf_iso["y"])

            cursor = 0
            for (draw, unit_vel) in chunk_meta:
                bfd_arr = preds[cursor:cursor + n_shots]
                perf_arr = (
                    perf_preds[cursor:cursor + n_shots]
                    if perf_preds is not None else None
                )
                cursor += n_shots
                unit_bfd.append(bfd_arr)
                unit_perf.append(perf_arr)
                velocities.append(unit_vel)
                unit_draws.append(draw)

                valid = np.ones(n_shots, dtype=bool)
                if perf_arr is not None:
                    valid = perf_arr <= PERF_BFD_MASK_THRESHOLD
                    perf_k += int((~valid).sum())
                    perf_sum += float(perf_arr.sum())
                    per_shot_perf_sum += perf_arr
                    perf_n += n_shots
                valid_n += int(valid.sum())
                per_shot_valid += valid

                ex = (bfd_arr > limit) & valid
                exceed_k += int(ex.sum())
                per_shot_k += ex
                proto_k += int(bool((bfd_arr[valid] > limit).any()))
                interim_hist += np.histogram(bfd_arr[valid], bins=interim_edges)[0]
                done += 1

            run.completed_independent_draws = done
            run.result_json = _interim_result()
            db.commit()

        # ---------------------------------------------------------------
        # aggregation
        # ---------------------------------------------------------------
        bfd_mat = np.vstack(unit_bfd) if unit_bfd else np.zeros((0, n_shots))
        n_units_eval = bfd_mat.shape[0]

        # perforation classifier scores (uncalibrated, exploratory)
        perforation = None
        pm = None
        if any(a is not None for a in unit_perf):
            pm = np.full((n_units_eval, n_shots), np.nan)
            for i, a in enumerate(unit_perf):
                if a is not None:
                    pm[i] = a
            perforation = {
                "mean_score": float(np.nanmean(pm)),
                "per_shot_mean": [
                    float(np.nanmean(pm[:, j])) for j in range(n_shots)
                ],
                "frac_score_gt_50": float(np.nanmean(pm > 0.5)),
                "uncalibrated": True,
            }

        # mask perforated shots: BFD is meaningless for them
        if pm is not None:
            valid_mat = ~(pm > PERF_BFD_MASK_THRESHOLD)   # NaN -> not perforated
        else:
            valid_mat = np.ones((n_units_eval, n_shots), dtype=bool)
        bfd_eval = np.where(valid_mat, bfd_mat, np.nan)
        flat = bfd_eval[~np.isnan(bfd_eval)]
        n_eval = len(flat)
        n_perforated = int((~valid_mat).sum())
        total_shots = int(n_units_eval * n_shots)

        exceed = flat > limit
        per_shot_rates = []
        for si in range(n_shots):
            if bfd_mat.size:
                col_valid = valid_mat[:, si]
                k = int(((bfd_mat[:, si] > limit) & col_valid).sum())
                per_shot_rates.append({
                    "shot_number": ctx.shot_plan[si].shot_number,
                    **_wilson(k, int(col_valid.sum())),
                })
        protocol_rate = _wilson(proto_k, n_units_eval)

        # histogram + survival
        hist_bins = np.linspace(0, max(float(flat.max()) if n_eval else limit * 2, limit * 1.5), 41)
        hist, edges = np.histogram(flat, bins=hist_bins)
        survival_x = np.linspace(0, float(hist_bins[-1]), 101)
        survival_y = (flat[None, :] >= survival_x[:, None]).mean(axis=1) if n_eval else np.zeros(101)

        # per-shot survival curves — answers "what's P(shot k records BFD > T)?"
        per_shot_survival = []
        for si in range(n_shots):
            col = bfd_eval[:, si]
            col = col[~np.isnan(col)]
            if len(col):
                per_shot_survival.append({
                    "shot_number": ctx.shot_plan[si].shot_number,
                    "n": int(len(col)),
                    "bfd_mm": survival_x.tolist(),
                    "p_exceed": (col[None, :] >= survival_x[:, None]).mean(axis=1).tolist(),
                })

        # per-vest survival of worst shot — answers "P(a vest records BFD > T
        # on at least one shot)?", i.e. the vest-level failure event
        unit_max_survival = None
        has_valid_shot = valid_mat.any(axis=1)
        if has_valid_shot.any():
            unit_max = np.max(
                np.where(valid_mat[has_valid_shot], bfd_mat[has_valid_shot], -np.inf),
                axis=1,
            )
            unit_max_survival = {
                "n": int(has_valid_shot.sum()),
                "bfd_mm": survival_x.tolist(),
                "p_exceed": (unit_max[None, :] >= survival_x[:, None]).mean(axis=1).tolist(),
            }

        # near-worst finite event: joint condition over shots of a unit
        # (perforated shots are NaN -> never satisfy a condition)
        near_worst = None
        if nw and nw.get("shots") and bfd_mat.size:
            cond = np.ones(bfd_mat.shape[0], dtype=bool)
            for cond_spec in nw["shots"]:
                si = int(cond_spec["shot_index"])
                op = cond_spec.get("op", ">")
                thr = float(cond_spec["threshold_mm"])
                col = bfd_eval[:, si]
                cond &= (col > thr) if op == ">" else (col < thr) if op == "<" else (col >= thr)
            near_worst = _wilson(int(cond.sum()), bfd_mat.shape[0])

        # stress envelope: highest sampled velocity at which predicted BFD p95
        # stays under the limit (per-shot velocity vs bfd pairs pooled,
        # perforated shots excluded)
        stress = None
        if velocities and n_eval:
            v_all = np.array([
                v for i, u in enumerate(velocities)
                for j, v in enumerate(u)
                if v is not None and valid_mat[i, j]
            ], dtype=float)
            b_all = np.array([
                bfd_mat[i, j]
                for i, u in enumerate(velocities)
                for j, v in enumerate(u)
                if v is not None and valid_mat[i, j]
            ], dtype=float)
            if len(v_all) and len(v_all) == len(b_all):
                order = np.argsort(v_all)
                v_s, b_s = v_all[order], b_all[order]
                v_edges = np.unique(np.quantile(v_s, np.linspace(0, 1, 21)))
                envelope = []
                for lo, hi in zip(v_edges[:-1], v_edges[1:]):
                    m = (v_s >= lo) & (v_s < hi)
                    if m.sum() >= 10:
                        envelope.append({
                            "velocity_bin": [float(lo), float(hi)],
                            "bfd_p50": float(np.median(b_s[m])),
                            "bfd_p95": float(np.quantile(b_s[m], 0.95)),
                            "n": int(m.sum()),
                        })
                ok = [e for e in envelope if e["bfd_p95"] <= limit]
                stress = {
                    "bfd_limit_mm": limit,
                    "max_velocity_p95_within_limit": float(max(e["velocity_bin"][1] for e in ok)) if ok else None,
                    "envelope": envelope,
                }

        # readiness promotion from the grouped-validation manifest stored
        # in bundle metadata. Gates are conservative; anything not meeting
        # them stays exploratory — nothing is claimed beyond the evidence.
        bh = (validation_meta.get("bfd_holdout") or {})
        ph = (validation_meta.get("perforation_holdout") or {})
        bfd_validated = bool(
            bh.get("n", 0) >= 100
            and (bh.get("r") or 0) >= 0.5
            and (bh.get("residual_sigma_mm") or 1e9) <= 10.0
        )
        perf_validated = bool(
            perf_iso
            and (ph.get("n_pos") or 0) >= 30
            and (ph.get("auc") or 0) >= 0.8
        )
        bfd_state = "validated_within_support" if bfd_validated else "exploratory"
        perf_state = (
            "validated_within_support" if perf_validated
            else "exploratory" if perforation else "blocked"
        )
        combined_state = (
            "validated_within_support" if (bfd_validated and perf_validated)
            else "exploratory" if (bfd_validated and perforation)
            else "blocked"
        )
        readiness = {
            "bfd_distribution": bfd_state,
            "bfd_exceedance_frequency": bfd_state,
            "perforation_probability": perf_state,
            "combined_risk": combined_state,
            "explanations": {
                "bfd_distribution": (
                    f"holdout r={bh.get('r'):.2f}, MAE={bh.get('mae_mm'):.1f}mm, "
                    f"residual sigma={bh.get('residual_sigma_mm'):.1f}mm "
                    f"(n={bh.get('n')}, {validation_meta.get('manifest', {}).get('n_val_groups', '?')} unseen vests)"
                    if bh else "no validation manifest on this bundle"
                ),
                "perforation_probability": (
                    "isotonic-calibrated probability"
                    if perf_validated else
                    "raw classifier score, uncalibrated (insufficient real "
                    "positive labels; synthetic anchors dominate) — treat as "
                    "exploratory" if perforation else
                    "no penetration classifier available in this model bundle"
                ),
                "combined_risk": (
                    "joint P(perforate or exceed) combines calibrated terms"
                    if combined_state == "validated_within_support" else
                    "requires calibrated penetration probability plus "
                    "validated conditional BFD"
                ),
            },
        }

        result = {
            "n_units": int(bfd_mat.shape[0]),
            "n_shots_per_unit": n_shots,
            "n_predicted_shots": int(n_eval),
            "n_rejected_pre_qc": n_rejected if pre_qc else 0,
            "bfd_limit_mm": limit,
            "histogram": {"bin_edges": edges.tolist(), "counts": hist.tolist()},
            "survival": {"bfd_mm": survival_x.tolist(), "p_exceed": survival_y.tolist()},
            "per_shot_survival": per_shot_survival,
            "unit_max_survival": unit_max_survival,
            "per_shot_exceedance": per_shot_rates,
            "perforation": perforation,
            "protocol_exceedance": protocol_rate,
            "n_perforated_shots": n_perforated,
            "perforation_rate": _wilson(n_perforated, total_shots),
            "perforations_per_1000_shots": (
                float(n_perforated / total_shots * 1000) if total_shots else None
            ),
            # joint failure: shot perforates OR (stops and exceeds BFD limit)
            "combined_failure_rate": _wilson(
                int(exceed.sum()) + n_perforated, total_shots
            ),
            "combined_events_per_1000_shots": (
                float((int(exceed.sum()) + n_perforated) / total_shots * 1000)
                if total_shots else None
            ),
            "expected_events_per_1000_shots": (float(exceed.mean() * 1000) if n_eval else None),
            "near_worst_event": near_worst,
            "stress_envelope": stress,
            "warnings": ctx.resolution.warnings + ctx.sampler.warnings + (
                ["No velocity spec for one or more shots; model imputation (training median) used."]
                if any(not sp.velocity_spec for sp in ctx.shot_plan) else []
            ) + (
                [f"{n_perforated} shot(s) excluded from BFD statistics "
                 f"(perforation score > {PERF_BFD_MASK_THRESHOLD}, uncalibrated threshold)."]
                if n_perforated else []
            ),
            "calculation_trace": {
                "variables": ctx.resolution.trace,
                "model_version": bundle.version,
                "bundle_hash": bundle.bundle_hash,
                "feature_contract_version": bundle.feature_contract_version,
                "population_mode": scenario.population_mode,
                "layer_counts_locked": bool(scenario.layer_counts_locked),
                "composition": ctx.vest_composition,
                "shot_plan": [
                    {"shot_number": sp.shot_number, "side": sp.side,
                     "ammunition": sp.ammunition.name if sp.ammunition else None,
                     "angle_degrees": sp.angle_degrees,
                     "conditioning": sp.conditioning,
                     "velocity_spec": sp.velocity_spec}
                    for sp in ctx.shot_plan
                ],
                "seed": int(run.seed),
                "calibration_applied": {
                    "bfd_bias_mm": bfd_bias if (bfd_sigma or bfd_bias) else None,
                    "bfd_residual_sigma_mm": bfd_sigma,
                    "perforation_isotonic": bool(perf_iso),
                },
                "notes": [
                    "BFD uncertainty combines input variation + holdout residual noise when the bundle carries a calibration artifact.",
                    "Velocity sampled per shot within the protocol window interpretation (symmetric/lower_only/upper_only).",
                    "Stack thickness/mass are recomputed from sampled layer properties — never sampled independently.",
                ],
            },
        }

        run.readiness_json = readiness
        run.result_json = result
        run.completed_independent_draws = bfd_mat.shape[0]
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        db.rollback()
        run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
        run.status = "failed"
        run.failure_reason = f"{type(e).__name__}: {e}"
        run.completed_at = datetime.utcnow()
        db.commit()
        raise
