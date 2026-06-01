import { apiClient } from './client';

export interface VestLayer {
  id: string;
  vest_id: string;
  layer_index: number;
  material_id: string | null;
  layer_count: number;
  notes: string | null;
}

export interface VestLayerCreate {
  layer_index: number;
  material_id?: string | null;
  layer_count?: number;
  notes?: string | null;
}

export interface Vest {
  id: string;
  vest_code: string;
  vest_type: string | null;
  threat_level: string | null;
  total_layers: number | null;
  total_thickness_mm: number | null;
  sizes: Record<string, number> | null;
  construction_notes: string | null;
  stitch_pattern: string | null;
  backing_material: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  layers: VestLayer[];
}

export interface VestCreate {
  vest_code: string;
  vest_type?: string | null;
  threat_level?: string | null;
  total_layers?: number | null;
  total_thickness_mm?: number | null;
  sizes?: Record<string, number> | null;
  construction_notes?: string | null;
  stitch_pattern?: string | null;
  backing_material?: string | null;
  notes?: string | null;
  layers?: VestLayerCreate[];
}

export interface VestUpdate {
  vest_code?: string | null;
  vest_type?: string | null;
  threat_level?: string | null;
  total_layers?: number | null;
  total_thickness_mm?: number | null;
  sizes?: Record<string, number> | null;
  construction_notes?: string | null;
  stitch_pattern?: string | null;
  backing_material?: string | null;
  notes?: string | null;
}

export interface VestListItem {
  id: string;
  vest_code: string;
  vest_type: string | null;
  threat_level: string | null;
  total_layers: number | null;
  total_thickness_mm: number | null;
  sizes: Record<string, number> | null;
  created_by_username: string | null;
  composition: string | null;
}

export const vestsApi = {
  list: (params?: { skip?: number; limit?: number; vest_type?: string; threat_level?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.vest_type) searchParams.append('vest_type', params.vest_type);
    if (params?.threat_level) searchParams.append('threat_level', params.threat_level);
    const query = searchParams.toString();
    return apiClient.get<VestListItem[]>(`/api/v1/vests/${query ? `?${query}` : ''}`);
  },

  get: (id: string) => apiClient.get<Vest>(`/api/v1/vests/${id}`),

  create: (vest: VestCreate) => apiClient.post<Vest>('/api/v1/vests/', vest),

  update: (id: string, vest: VestUpdate) => apiClient.patch<Vest>(`/api/v1/vests/${id}`, vest),

  delete: (id: string) => apiClient.delete<void>(`/api/v1/vests/${id}`),

  getLayers: (id: string) => apiClient.get<VestLayer[]>(`/api/v1/vests/${id}/layers`),

  updateLayers: (id: string, layers: VestLayerCreate[]) => apiClient.put<VestLayer[]>(`/api/v1/vests/${id}/layers`, layers),
};
