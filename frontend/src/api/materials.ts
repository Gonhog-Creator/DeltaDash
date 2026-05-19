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
  thickness_tolerance_mm: string | null;
  density_g_cm3: number | null;
  tensile_strength_mpa: number | null;
  modulus_gpa: number | null;
  elongation_percent: number | null;
  material_function: string | null;
  created_by_username: string | null;
  mss_file_path: string | null;
  sds_file_path: string | null;
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
  thickness_tolerance_mm?: string | null;
  density_g_cm3?: number | null;
  tensile_strength_mpa?: number | null;
  modulus_gpa?: number | null;
  elongation_percent?: number | null;
  material_function?: string | null;
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
  thickness_tolerance_mm?: string | null;
  density_g_cm3?: number | null;
  tensile_strength_mpa?: number | null;
  modulus_gpa?: number | null;
  elongation_percent?: number | null;
  material_function?: string | null;
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
    return apiClient.get<Material[]>(`/api/v1/materials/${query ? `?${query}` : ''}`);
  },

  get: (id: string) => apiClient.get<Material>(`/api/v1/materials/${id}`),

  create: (material: MaterialCreate, files?: { mss?: File; sds?: File }) => {
    if (files) {
      const formData = new FormData();
      Object.entries(material).forEach(([key, value]) => {
        if (value !== null && value !== undefined) {
          formData.append(key, value.toString());
        }
      });
      if (files.mss) formData.append('mss_file', files.mss);
      if (files.sds) formData.append('sds_file', files.sds);
      return apiClient.post<Material>('/api/v1/materials/', formData);
    }
    return apiClient.post<Material>('/api/v1/materials/', material);
  },

  update: (id: string, material: MaterialUpdate) => apiClient.patch<Material>(`/api/v1/materials/${id}`, material),

  uploadFiles: (id: string, files?: { mss?: File; sds?: File }) => {
    if (!files || (!files.mss && !files.sds)) {
      return Promise.reject('No files to upload');
    }
    const formData = new FormData();
    if (files.mss) formData.append('mss_file', files.mss);
    if (files.sds) formData.append('sds_file', files.sds);
    return apiClient.post<Material>(`/api/v1/materials/${id}/upload`, formData);
  },

  delete: (id: string) => apiClient.delete<void>(`/api/v1/materials/${id}`),
};
