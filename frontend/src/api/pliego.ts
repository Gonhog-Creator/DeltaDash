import { apiClient, API_BASE_URL } from './client';

export interface PliegoRequirements {
  threat_level?: string | null;
  protection_class?: string | null;
  vest_type?: string | null;
  required_sizes?: string[] | null;
  max_weight_g?: number | null;
  trauma_homologation?: {
    backface_max_mm?: number | null;
    ammunition?: string | null;
  } | null;
  flexibility_required?: boolean | null;
  panel_sewn_required?: boolean | null;
  ammunition_calibers?: string[] | null;
  is_female_required?: boolean | null;
  min_total_layers?: number | null;
  max_total_layers?: number | null;
  max_thickness_mm?: number | null;
  stitch_pattern?: string | null;
  additional_notes?: string | null;
  raw_summary?: string | null;
}

export interface PliegoVestCertification {
  name: string;
  lab_name: string | null;
  protocol: string | null;
  certification_number: string | null;
  test_date: string | null;
}

export interface PliegoVestMatch {
  vest_id: string;
  vest_code: string;
  vest_type: string | null;
  threat_level: string | null;
  protection_class: string | null;
  total_layers: number | null;
  total_thickness_mm: number | null;
  weight_g: number | null;
  sizes: Record<string, number> | null;
  composition: string | null;
  flexibility_rating: boolean;
  is_panel_sewn: boolean | null;
  is_catalog_model: boolean;
  is_female: boolean | null;
  certifications: PliegoVestCertification[];
  match_score: number;
  match_details: Record<string, string | boolean>;
  match_gaps: string[];
}

export interface PliegoMatchResults {
  recommendations: PliegoVestMatch[];
  summary: {
    total_certified_vests: number;
    total_matched: number;
    top_score: number;
  };
  gaps: string[];
}

export interface PliegoDocument {
  id: string;
  filename: string;
  original_name: string | null;
  status: 'pending' | 'analyzed' | 'failed';
  extracted_requirements: PliegoRequirements | null;
  match_results: PliegoMatchResults | null;
  error_message: string | null;
  created_by_username: string | null;
  created_at: string;
  updated_at: string;
}

export const pliegoApi = {
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<PliegoDocument>('/api/v1/pliego/upload', formData);
  },

  list: () => apiClient.get<PliegoDocument[]>('/api/v1/pliego/documents'),

  get: (id: string) => apiClient.get<PliegoDocument>(`/api/v1/pliego/documents/${id}`),

  download: (id: string) => {
    const url = `${API_BASE_URL}/api/v1/pliego/documents/${id}/download`;
    const token = localStorage.getItem('token');
    return fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
    }).then((res) => {
      if (!res.ok) throw new Error('Download failed');
      return res.blob();
    });
  },

  delete: (id: string) => apiClient.delete<void>(`/api/v1/pliego/documents/${id}`),

  retry: (id: string) => apiClient.post<PliegoDocument>(`/api/v1/pliego/documents/${id}/retry`),
};
