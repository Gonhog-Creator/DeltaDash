from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class ScenarioCreate(BaseModel):
    name: str
    design_id: UUID                      # vest id (the design under evaluation)
    model_version: Optional[str] = None   # None -> resolved to active bundle at creation
    protocol_revision_id: Optional[UUID] = None
    # Targeted threat selection: resolved server-side into a ProtocolRevision
    # (find-or-create from the protocol's levels_config). protocol_revision_id
    # wins if both are supplied.
    protocol_id: Optional[UUID] = None
    level: Optional[str] = None
    ammunition_id: Optional[UUID] = None
    population_mode: str = "accepted_units"   # accepted_units | pre_qc
    outcome_rule_json: Optional[Dict[str, Any]] = None   # e.g. {"bfd_threshold_mm": 44.0}
    near_worst_event_json: Optional[Dict[str, Any]] = None
    dependency_snapshot_json: Optional[Dict[str, Any]] = None
    layer_counts_locked: bool = True


class ScenarioOut(BaseModel):
    id: UUID
    name: str
    design_id: UUID
    model_version: str
    feature_contract_version: Optional[str]
    protocol_revision_id: Optional[UUID]
    population_mode: str
    outcome_rule_json: Optional[Dict[str, Any]]
    near_worst_event_json: Optional[Dict[str, Any]]
    layer_counts_locked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RunCreate(BaseModel):
    scenario_id: UUID
    model_version: Optional[str] = None     # None -> active bundle
    requested_draws: int = Field(default=1000, ge=1, le=200000)
    seed: Optional[int] = None              # None -> derive from hash


class RunOut(BaseModel):
    id: UUID
    scenario_id: UUID
    model_version: Optional[str]
    model_bundle_hash: Optional[str]
    feature_contract_version: Optional[str]
    seed: Optional[int]
    status: str
    requested_draws: int
    completed_independent_draws: int
    failure_reason: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class RunResult(BaseModel):
    run: RunOut
    readiness: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]


class DistributionPreview(BaseModel):
    """Resolved sampling variables for a vest design — previewed before a run."""
    vest_id: UUID
    variables: List[Dict[str, Any]]
    warnings: List[str]


class ModelVersionOut(BaseModel):
    version: str
    model_name: Optional[str] = None
    has_files: bool = False
