import { apiClient } from './client';

export interface ManualEntryShot {
  shot_number: string;
  side?: string | null;
  conditioning?: string | null;
  vest_number?: string | null;
  angle_degrees?: number | null;
  caliber?: string | null;
  velocity_m_s?: number | null;
  trauma_mm?: number | null;
  trauma_qualitative?: string | null;
  protection_level?: string | null;
  temperature_c?: number | null;
  humidity_percent?: number | null;
}

export interface ManualEntryVestTab {
  vest_number?: string | null;
  serial_number?: string | null;
  size?: string | null;
  conditioning?: string | null;
  ballistic_limit?: boolean | false;
  shots: ManualEntryShot[];
}

export interface ManualEntryRequest {
  name: string;
  test_date?: string | null;
  lab_name?: string | null;
  protocol?: string | null;
  clay_temperature_c?: number | null;
  ambient_temperature_c?: number | null;
  humidity_percent?: number | null;
  vest_id?: string | null;
  geometry_id: string;
  is_official?: boolean | false;
  certification_number?: string | null;
  notes?: string | null;
  protection_level?: string | null;
  vest_tabs: ManualEntryVestTab[];
}

export interface ManualEntryResponse {
  parent_session_id: string;
  child_session_ids: string[];
  total_shots: number;
}

export const manualEntryApi = {
  submit: (entry: ManualEntryRequest) =>
    apiClient.post<ManualEntryResponse>('/api/v1/test-sessions/manual-entry', entry),
};
