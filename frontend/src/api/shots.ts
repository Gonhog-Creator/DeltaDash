import { apiClient } from './client';

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
  anomaly_flag: boolean | null;
  anomaly_notes: string | null;
  raw_source_file: string | null;
  raw_row_number: number | null;
  created_at: string;
  updated_at: string;
}

export const shotsApi = {
  list: (params?: { skip?: number; limit?: number; test_session_id?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.test_session_id) searchParams.append('test_session_id', params.test_session_id);
    const query = searchParams.toString();
    return apiClient.get<Shot[]>(`/api/v1/shots${query ? `?${query}` : ''}`);
  },
};
