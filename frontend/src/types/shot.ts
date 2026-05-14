export interface Shot {
  id: string;
  test_session_id: string | null;
  panel_id: string | null;
  ammunition_id: string | null;
  shot_pattern_position_id: string | null;
  shot_number: number | null;
  measured_velocity_fps: number | null;
  measured_velocity_m_s: number | null;
  impact_angle_degrees: number | null;
  bfd_mm: number | null;
  penetration: boolean | null;
  partial_penetration: boolean | null;
  trauma_score: number | null;
  pass_fail: string | null;
  distance_m: number | null;
  yaw_observed: boolean | null;
  edge_hit: boolean | null;
  anomaly_flag: boolean;
  anomaly_notes: string | null;
  raw_source_file: string | null;
  raw_row_number: number | null;
  created_at: string;
  updated_at: string;
}
