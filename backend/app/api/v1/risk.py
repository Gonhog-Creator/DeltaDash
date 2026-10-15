import hashlib
import uuid as uuid_mod
import random
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.db.models import RiskScenario, RiskSimulationRun, Vest
from app.db.models.protocol import Protocol
from app.db.models.protocol_revision import ProtocolRevision
from app.db.models.ammunition import Ammunition
from app.schemas.risk import (
    DistributionPreview,
    RunCreate,
    RunOut,
    RunResult,
    ScenarioCreate,
    ScenarioOut,
)
from app.api.v1.auth import get_current_active_user
from app.db.models.user import User

router = APIRouter()


def _derive_seed(scenario_id) -> int:
    """Deterministic default seed from the scenario id."""
    return int.from_bytes(hashlib.sha256(str(scenario_id).encode()).digest()[:4], "big")


def _execute_run(run_id):
    """Background entry point: fresh session + bundle, then execute."""
    from app.services.ml.model_bundle import get_model_bundle
    db = SessionLocal()
    try:
        run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
        if run is None or run.status != "queued":
            return
        version = (run.runtime_versions_json or {}).get("model_version")
        bundle = get_model_bundle(version, db_session=db)
        from app.services.risk.simulation import run_simulation
        run_simulation(run_id, db, bundle)
    except Exception:
        try:
            run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
            if run and run.status == "running":
                run.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.get("/risk/models")
def risk_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Model versions resolvable as immutable bundles."""
    from app.services.ml.model_bundle import list_available_bundle_versions, get_default_version
    return {
        "active_version": get_default_version(db),
        "versions": list_available_bundle_versions(db),
    }


@router.get("/risk/protocols")
def risk_protocols(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Protocols -> levels -> ammunition options for targeted sim runs."""
    out = []
    for p in db.query(Protocol).order_by(Protocol.name).all():
        levels = []
        for lvl in (p.levels_config or []):
            ammo_opts = []
            for cfg in (lvl.get("ammunition_config") or []):
                ammo = db.query(Ammunition).filter(
                    Ammunition.id == cfg.get("ammunition_id")
                ).first()
                ammo_opts.append({
                    "ammunition_id": cfg.get("ammunition_id"),
                    "ammunition_name": ammo.name if ammo else None,
                    "caliber": ammo.caliber if ammo else None,
                    "reference_velocity_m_s": cfg.get("reference_velocity_m_s"),
                    "velocity_window_m_s": cfg.get("velocity_window_m_s"),
                    "shots_per_panel": cfg.get("shots_per_panel"),
                })
            levels.append({
                "level_name": lvl.get("level_name"),
                "ammunition_config": ammo_opts,
            })
        out.append({"id": str(p.id), "name": p.name, "levels": levels})
    return out


def _resolve_protocol_revision(
    db: Session,
    payload: ScenarioCreate,
    created_by: Optional[str] = None,
) -> Optional[uuid_mod.UUID]:
    """Find-or-create an immutable ProtocolRevision for the selected
    protocol + level + ammunition. Returns None when no protocol selected."""
    if payload.protocol_revision_id:
        return payload.protocol_revision_id
    if payload.protocol_id is None or payload.level is None:
        return None

    protocol = db.query(Protocol).filter(Protocol.id == payload.protocol_id).first()
    if protocol is None:
        raise HTTPException(status_code=404, detail="Protocol not found")

    level_cfg = next(
        (l for l in (protocol.levels_config or [])
         if l.get("level_name") == payload.level),
        None,
    )
    if level_cfg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Level {payload.level} not found in protocol {protocol.name}",
        )

    ammo_cfgs = level_cfg.get("ammunition_config") or []
    if payload.ammunition_id:
        ammo_cfgs = [c for c in ammo_cfgs
                     if str(c.get("ammunition_id")) == str(payload.ammunition_id)]
        if not ammo_cfgs:
            raise HTTPException(
                status_code=404,
                detail="Selected ammunition is not configured for that level",
            )

    # Build shots_json: shots_per_panel shots per ammo config, numbered
    # sequentially, symmetric velocity windows.
    shots_json = []
    shot_no = 1
    for cfg in ammo_cfgs:
        for _ in range(int(cfg.get("shots_per_panel") or 1)):
            shots_json.append({
                "shot_number": shot_no,
                "side": "front",
                "ammunition_id": cfg.get("ammunition_id"),
                "reference_velocity_m_s": cfg.get("reference_velocity_m_s"),
                "velocity_window_m_s": cfg.get("velocity_window_m_s"),
                "window_interpretation": "symmetric",
            })
            shot_no += 1

    outcome_rule = payload.outcome_rule_json or {}
    import json as _json
    rev_content = {
        "protocol_id": str(protocol.id),
        "level": payload.level,
        "shots": shots_json,
        "outcome_rule": outcome_rule,
    }
    rev_hash = hashlib.sha256(
        _json.dumps(rev_content, sort_keys=True, default=str).encode()
    ).hexdigest()

    existing = db.query(ProtocolRevision).filter(
        ProtocolRevision.content_hash == rev_hash
    ).first()
    if existing:
        return existing.id

    max_rev = db.query(ProtocolRevision).filter(
        ProtocolRevision.protocol_id == protocol.id,
        ProtocolRevision.level == payload.level,
    ).count()
    rev = ProtocolRevision(
        protocol_id=protocol.id,
        level=payload.level,
        revision=max_rev + 1,
        rule_source="risk_ui",
        review_status="draft",
        shots_json=shots_json,
        outcome_rule_json=outcome_rule,
        content_hash=rev_hash,
        created_by=created_by,
    )
    db.add(rev)
    db.flush()
    return rev.id


@router.get("/risk/distributions/{vest_id}", response_model=DistributionPreview)
def distribution_preview(
    vest_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Preview the resolved sampling distributions + assumptions for a design."""
    vest = db.query(Vest).filter(Vest.id == vest_id).first()
    if vest is None:
        raise HTTPException(status_code=404, detail="Vest not found")
    from app.services.risk.distributions import resolve_design_distributions
    res = resolve_design_distributions(db, vest)
    return DistributionPreview(vest_id=vest_id, variables=res.trace, warnings=res.warnings)


@router.post("/risk/scenarios", response_model=ScenarioOut)
def create_scenario(
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    vest = db.query(Vest).filter(Vest.id == payload.design_id).first()
    if vest is None:
        raise HTTPException(status_code=404, detail="Design vest not found")

    # Scenarios pin the model version they were defined under so runs are
    # comparable over time; default to the active bundle's version+contract.
    from app.services.ml.model_bundle import get_model_bundle, get_default_version
    model_version = payload.model_version or get_default_version(db)
    if model_version is None:
        raise HTTPException(status_code=404, detail="No trained model found")
    bundle = get_model_bundle(model_version, db_session=db)

    # Snapshot the layer structure + resolved distributions so the scenario
    # is reproducible even if the vest/materials change later.
    from app.db.models import VestLayer, Material
    layers = (
        db.query(VestLayer).filter(VestLayer.vest_id == vest.id)
        .order_by(VestLayer.layer_index).all()
    )
    layer_snapshot = [
        {
            "layer_index": vl.layer_index,
            "material_id": str(vl.material_id) if vl.material_id else None,
            "material_name": (db.query(Material).filter(Material.id == vl.material_id).first().name
                              if vl.material_id else None),
            "layer_count": vl.layer_count,
        }
        for vl in layers
    ]

    # Targeted threat selection -> immutable protocol revision
    protocol_revision_id = _resolve_protocol_revision(
        db, payload, created_by=str(current_user.id)
    )

    from app.services.risk.distributions import resolve_design_distributions
    resolution = resolve_design_distributions(db, vest)
    distribution_snapshot = {"variables": resolution.trace, "warnings": resolution.warnings}

    import json as _json
    content = {
        "design_id": str(payload.design_id),
        "model_version": bundle.version,
        "feature_contract_version": bundle.feature_contract_version,
        "protocol_revision_id": str(protocol_revision_id) if protocol_revision_id else None,
        "layers": layer_snapshot,
        "distributions": distribution_snapshot,
        "population_mode": payload.population_mode,
        "outcome_rule": payload.outcome_rule_json or {},
    }
    content_hash = hashlib.sha256(
        _json.dumps(content, sort_keys=True, default=str).encode()
    ).hexdigest()

    scenario = RiskScenario(
        name=payload.name,
        design_id=payload.design_id,
        model_version=bundle.version,
        feature_contract_version=bundle.feature_contract_version,
        protocol_revision_id=protocol_revision_id,
        population_mode=payload.population_mode,
        outcome_rule_json=payload.outcome_rule_json or {},
        near_worst_event_json=payload.near_worst_event_json,
        dependency_snapshot_json=payload.dependency_snapshot_json or {},
        distribution_snapshot_json=distribution_snapshot,
        layer_snapshot_json=layer_snapshot,
        layer_counts_locked=payload.layer_counts_locked,
        content_hash=content_hash,
        created_by=current_user.id,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/risk/scenarios", response_model=List[ScenarioOut])
def list_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return db.query(RiskScenario).order_by(RiskScenario.created_at.desc()).all()


@router.get("/risk/scenarios/{scenario_id}", response_model=ScenarioOut)
def get_scenario(
    scenario_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    s = db.query(RiskScenario).filter(RiskScenario.id == scenario_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return s


@router.post("/risk/runs", response_model=RunOut)
def create_run(
    payload: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    scenario = db.query(RiskScenario).filter(RiskScenario.id == payload.scenario_id).first()
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # A run normally uses the scenario's pinned model version; an explicit
    # override enables A/B comparison across versions on the same scenario.
    model_version = payload.model_version or scenario.model_version
    if not model_version:
        from app.services.ml.model_bundle import get_default_version
        model_version = get_default_version(db)
        if model_version is None:
            raise HTTPException(status_code=404, detail="No trained model found")

    run = RiskSimulationRun(
        scenario_id=payload.scenario_id,
        scenario_hash=scenario.content_hash,
        seed=payload.seed if payload.seed is not None else _derive_seed(payload.scenario_id),
        status="queued",
        requested_draws=payload.requested_draws,
        runtime_versions_json={"model_version": model_version},
        created_by=current_user.id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_execute_run, run.id)
    run.model_version = model_version
    return run


@router.get("/risk/runs", response_model=List[RunOut])
def list_runs(
    scenario_id: Optional[uuid_mod.UUID] = None,
    model_version: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Run history for comparison across scenarios and model versions."""
    q = db.query(RiskSimulationRun)
    if scenario_id:
        q = q.filter(RiskSimulationRun.scenario_id == scenario_id)
    runs = q.order_by(RiskSimulationRun.created_at.desc()).limit(100).all()
    for run in runs:
        run.model_version = (run.runtime_versions_json or {}).get("model_version")
    if model_version:
        runs = [r for r in runs if r.model_version == model_version]
    return runs


@router.get("/risk/runs/{run_id}", response_model=RunOut)
def get_run(
    run_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run.model_version = (run.runtime_versions_json or {}).get("model_version")
    return run


@router.get("/risk/runs/{run_id}/result", response_model=RunResult)
def get_run_result(
    run_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run.model_version = (run.runtime_versions_json or {}).get("model_version")
    return RunResult(run=run, readiness=run.readiness_json, result=run.result_json)


@router.post("/risk/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(
    run_id: uuid_mod.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Flag a queued/running run for cancellation. The worker checks this at
    each chunk boundary."""
    run = db.query(RiskSimulationRun).filter(RiskSimulationRun.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status in ("completed", "failed", "canceled"):
        run.model_version = (run.runtime_versions_json or {}).get("model_version")
        return run
    run.status = "canceled"
    db.commit()
    db.refresh(run)
    run.model_version = (run.runtime_versions_json or {}).get("model_version")
    return run
