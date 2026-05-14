import { apiClient } from './client';

export interface Material {
  id: string;
  name: string;
  normalized_name: string | null;
  manufacturer: string | null;
  supplier: string | null;
  material_class: string | null;
  fiber_type: string | null;
  weave_type: string | null;
  coating: string | null;
  color: string | null;
  areal_density_g_m2: number | null;
  thickness_mm: number | null;
  density_g_cm3: number | null;
  tensile_strength_mpa: number | null;
  modulus_gpa: number | null;
  elongation_percent: number | null;
  notes: string | null;
  source_confidence: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaterialCreate {
  name: string;
  normalized_name?: string | null;
  manufacturer?: string | null;
  supplier?: string | null;
  material_class?: string | null;
  fiber_type?: string | null;
  weave_type?: string | null;
  coating?: string | null;
  color?: string | null;
  areal_density_g_m2?: number | null;
  thickness_mm?: number | null;
  density_g_cm3?: number | null;
  tensile_strength_mpa?: number | null;
  modulus_gpa?: number | null;
  elongation_percent?: number | null;
  notes?: string | null;
  source_confidence?: string | null;
}

export interface MaterialUpdate {
  name?: string | null;
  normalized_name?: string | null;
  manufacturer?: string | null;
  supplier?: string | null;
  material_class?: string | null;
  fiber_type?: string | null;
  weave_type?: string | null;
  coating?: string | null;
  color?: string | null;
  areal_density_g_m2?: number | null;
  thickness_mm?: number | null;
  density_g_cm3?: number | null;
  tensile_strength_mpa?: number | null;
  modulus_gpa?: number | null;
  elongation_percent?: number | null;
  notes?: string | null;
  source_confidence?: string | null;
}

export const materialsApi = {
  list: (params?: { skip?: number; limit?: number; material_class?: string; manufacturer?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.material_class) searchParams.append('material_class', params.material_class);
    if (params?.manufacturer) searchParams.append('manufacturer', params.manufacturer);
    const query = searchParams.toString();
    return apiClient.get<Material[]>(`/api/v1/materials${query ? `?${query}` : ''}`);
  },

  get: (id: string) => apiClient.get<Material>(`/api/v1/materials/${id}`),

  create: (material: MaterialCreate) => apiClient.post<Material>('/api/v1/materials', material),

  update: (id: string, material: MaterialUpdate) => apiClient.patch<Material>(`/api/v1/materials/${id}`, material),

  delete: (id: string) => apiClient.delete<void>(`/api/v1/materials/${id}`),
};
