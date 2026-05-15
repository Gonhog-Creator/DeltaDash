import { apiClient } from './client';

export interface Ammunition {
  id: string;
  name: string;
  caliber: string | null;
  caliber_unit: string | null;
  caliber_diameter_mm: number | null;
  caliber_length_mm: number | null;
  caliber_inch: number | null;
  projectile_type: string | null;
  projectile_mass_grains: number | null;
  projectile_mass_grams: number | null;
  nominal_velocity_fps: number | null;
  nominal_velocity_m_s: number | null;
  manufacturer: string | null;
  lot_number: string | null;
  standard_reference: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface AmmunitionCreate {
  name: string;
  caliber?: string | null;
  caliber_unit: string;
  caliber_diameter_mm?: number | null;
  caliber_length_mm?: number | null;
  caliber_inch?: number | null;
  projectile_type?: string | null;
  projectile_mass_grains: number;
  nominal_velocity_fps: number;
  manufacturer?: string | null;
  lot_number?: string | null;
  standard_reference?: string | null;
  notes?: string | null;
}

export interface AmmunitionUpdate {
  name?: string | null;
  caliber?: string | null;
  caliber_unit?: string | null;
  caliber_diameter_mm?: number | null;
  caliber_length_mm?: number | null;
  caliber_inch?: number | null;
  projectile_type?: string | null;
  projectile_mass_grains?: number | null;
  nominal_velocity_fps?: number | null;
  manufacturer?: string | null;
  lot_number?: string | null;
  standard_reference?: string | null;
  notes?: string | null;
}

export const ammunitionApi = {
  list: (params?: { skip?: number; limit?: number; caliber?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.caliber) searchParams.append('caliber', params.caliber);
    const query = searchParams.toString();
    return apiClient.get<Ammunition[]>(`/api/v1/ammunition/${query ? `?${query}` : ''}`);
  },

  get: (id: string) => apiClient.get<Ammunition>(`/api/v1/ammunition/${id}`),

  create: (ammunition: AmmunitionCreate) => apiClient.post<Ammunition>('/api/v1/ammunition/', ammunition),

  update: (id: string, ammunition: AmmunitionUpdate) => apiClient.patch<Ammunition>(`/api/v1/ammunition/${id}`, ammunition),

  delete: (id: string) => apiClient.delete<void>(`/api/v1/ammunition/${id}`),
};
