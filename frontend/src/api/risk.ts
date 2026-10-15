import { apiClient } from './client';

export interface RiskModel {
  version: string;
  model_name?: string;
  has_files?: boolean;
}

export interface RiskModelsResponse {
  active_version: string | null;
  versions: RiskModel[];
}

export interface DistributionVariable {
  variable: string;
  material: string;
  property_key: string;
  direction: string;
  unit: string;
  catalog_nominal?: number | null;
  family?: string;
  parameters?: Record<string, unknown>;
  provenance?: string;
  basis?: string;
  skipped?: boolean;
  reason?: string;
}

export interface DistributionPreview {
  vest_id: string;
  variables: DistributionVariable[];
  warnings: string[];
}

export interface AmmoOption {
  ammunition_id: string;
  ammunition_name?: string;
  caliber?: string;
  reference_velocity_m_s?: number;
  velocity_window_m_s?: number;
  shots_per_panel?: number;
}

export interface ProtocolLevel {
  level_name: string;
  ammunition_config: AmmoOption[];
}

export interface RiskProtocol {
  id: string;
  name: string;
  levels: ProtocolLevel[];
}

export interface ScenarioCreate {
  name: string;
  design_id: string;
  model_version?: string;
  protocol_revision_id?: string;
  protocol_id?: string;
  level?: string;
  ammunition_id?: string;
  population_mode?: 'accepted_units' | 'pre_qc';
  outcome_rule_json?: { bfd_threshold_mm?: number; threat_level?: string };
  near_worst_event_json?: Record<string, unknown>;
  dependency_snapshot_json?: Record<string, unknown>;
  layer_counts_locked?: boolean;
}

export interface Scenario {
  id: string;
  name: string;
  design_id: string;
  model_version: string;
  feature_contract_version?: string;
  protocol_revision_id?: string;
  population_mode: string;
  outcome_rule_json?: Record<string, unknown>;
  near_worst_event_json?: Record<string, unknown>;
  layer_counts_locked: boolean;
  created_at: string;
}

export interface RunCreate {
  scenario_id: string;
  model_version?: string;
  requested_draws?: number;
  seed?: number;
}

export interface RiskRun {
  id: string;
  scenario_id: string;
  model_version?: string;
  model_bundle_hash?: string;
  feature_contract_version?: string;
  seed?: number;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'canceled';
  requested_draws: number;
  completed_independent_draws: number;
  failure_reason?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface RateEstimate {
  estimate: number;
  ci95_low: number;
  ci95_high: number;
  n: number;
  events: number;
  shot_number?: number;
}

export interface RunResult {
  partial?: boolean;   // true while run is in progress — interim aggregates
  n_units: number;
  n_shots_per_unit: number;
  n_predicted_shots: number;
  n_rejected_pre_qc?: number;
  bfd_limit_mm: number;
  histogram: { bin_edges: number[]; counts: number[] };
  survival?: { bfd_mm: number[]; p_exceed: number[] };
  per_shot_survival?: { shot_number: number; n: number; bfd_mm: number[]; p_exceed: number[] }[];
  unit_max_survival?: { n: number; bfd_mm: number[]; p_exceed: number[] };
  per_shot_exceedance: RateEstimate[];
  perforation?: {
    mean_score: number;
    per_shot_mean: number[];
    frac_score_gt_50?: number;
    uncalibrated?: boolean;
    vest_rate?: RateEstimate;
    vests_with_perforation_per_1000?: number;
  };
  protocol_exceedance?: RateEstimate;
  n_perforated_shots?: number;
  perforation_rate?: RateEstimate;
  perforations_per_1000_shots?: number;
  combined_failure_rate?: RateEstimate;
  combined_events_per_1000_shots?: number;
  expected_events_per_1000_shots?: number;
  near_worst_event?: RateEstimate;
  stress_envelope?: {
    bfd_limit_mm: number;
    max_velocity_p95_within_limit?: number;
    envelope: { velocity_bin: number[]; bfd_p50: number; bfd_p95: number; n: number }[];
  };
  warnings?: string[];
  calculation_trace?: {
    variables: DistributionVariable[];
    model_version: string;
    bundle_hash?: string;
    feature_contract_version?: string;
    population_mode?: string;
    layer_counts_locked?: boolean;
    composition?: string;
    shot_plan?: Record<string, unknown>[];
    seed?: number;
    notes?: string[];
  };
}

export interface RunResultResponse {
  run: RiskRun;
  readiness?: {
    bfd_distribution?: string;
    bfd_exceedance_frequency?: string;
    perforation_probability?: string;
    combined_risk?: string;
    explanations?: Record<string, string>;
  };
  result?: RunResult;
}

const BASE = '/api/v1/ballistic/risk';

export const riskApi = {
  models: () => apiClient.get<RiskModelsResponse>(`${BASE}/models`),
  protocols: () => apiClient.get<RiskProtocol[]>(`${BASE}/protocols`),
  distributionPreview: (vestId: string) =>
    apiClient.get<DistributionPreview>(`${BASE}/distributions/${vestId}`),
  createScenario: (payload: ScenarioCreate) =>
    apiClient.post<Scenario>(`${BASE}/scenarios`, payload),
  listScenarios: () => apiClient.get<Scenario[]>(`${BASE}/scenarios`),
  createRun: (payload: RunCreate) =>
    apiClient.post<RiskRun>(`${BASE}/runs`, payload),
  listRuns: (scenarioId?: string, modelVersion?: string) => {
    const params = new URLSearchParams();
    if (scenarioId) params.set('scenario_id', scenarioId);
    if (modelVersion) params.set('model_version', modelVersion);
    const q = params.toString();
    return apiClient.get<RiskRun[]>(`${BASE}/runs${q ? `?${q}` : ''}`);
  },
  getRun: (runId: string) => apiClient.get<RiskRun>(`${BASE}/runs/${runId}`),
  getRunResult: (runId: string) =>
    apiClient.get<RunResultResponse>(`${BASE}/runs/${runId}/result`),
  cancelRun: (runId: string) =>
    apiClient.post<RiskRun>(`${BASE}/runs/${runId}/cancel`),
};
