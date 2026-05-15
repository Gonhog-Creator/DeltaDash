import { apiClient } from './client';

export interface ShotData {
  id: string;
  test_session_id: string;
  vest_number: string | null;
  side: string | null;
  shot_number: string | number;
  protection_level: string | null;
  caliber: string | null;
  trauma_mm: number | null;
  velocity_m_s: number | null;
  bfd_mm: number | null;
  measured_velocity_m_s: number | null;
  temperature_c: number | null;
  humidity_percent: number | null;
  created_at: string;
}

export const shotDataApi = {
  list: (params?: { skip?: number; limit?: number; test_session_id?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.test_session_id) searchParams.append('test_session_id', params.test_session_id);
    const query = searchParams.toString();
    return apiClient.get<ShotData[]>(`/api/v1/shot-data${query ? `?${query}` : ''}`);
  },
};
