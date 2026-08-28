import { apiClient } from './client';

export interface Cover {
  id: string;
  cover_code: string;
  name: string;
  geometry_id: string | null;
  geometry_name: string | null;
  fabric_type: string | null;
  fabric_weight_g_m2: number | null;
  layer_count: number | null;
  weight_g: number | null;
  has_molle: boolean;
  molle_config: MolleConfig[] | null;
  has_quick_release: boolean;
  quick_release_type: string | null;
  fin_height_mm: number | null;
  fin_width_mm: number | null;
  available_sizes: string[] | null;
  compatible_vest_types: string[] | null;
  notes: string | null;
}

export interface MolleConfig {
  location: string;
  rows: number;
  columns: number;
}

export interface CoverCreate {
  cover_code: string;
  name: string;
  geometry_id?: string | null;
  fabric_type?: string | null;
  fabric_weight_g_m2?: number | null;
  layer_count?: number | null;
  weight_g?: number | null;
  has_molle?: boolean;
  molle_config?: MolleConfig[] | null;
  has_quick_release?: boolean;
  quick_release_type?: string | null;
  fin_height_mm?: number | null;
  fin_width_mm?: number | null;
  available_sizes?: string[] | null;
  compatible_vest_types?: string[] | null;
  notes?: string | null;
}

export interface CoverUpdate extends Partial<CoverCreate> {}

export const coversApi = {
  list: (params?: { geometry_id?: string; vest_type?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.geometry_id) searchParams.append('geometry_id', params.geometry_id);
    if (params?.vest_type) searchParams.append('vest_type', params.vest_type);
    const query = searchParams.toString();
    return apiClient.get<Cover[]>(`/api/v1/covers/${query ? `?${query}` : ''}`);
  },

  get: (id: string) => apiClient.get<Cover>(`/api/v1/covers/${id}`),

  create: (data: CoverCreate) => apiClient.post<Cover>('/api/v1/covers/', data),

  update: (id: string, data: CoverUpdate) => apiClient.put<Cover>(`/api/v1/covers/${id}`, data),

  delete: (id: string) => apiClient.delete<{ message: string }>(`/api/v1/covers/${id}`),
};
