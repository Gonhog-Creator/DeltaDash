import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, API_BASE_URL } from '../api/client';

export interface GeometrySizeMeasurements {
  front: Record<string, number>;
  back: Record<string, number>;
}

export interface GeometryPdf {
  path: string;
  original_name: string;
}

export interface Geometry {
  id: string;
  name: string;
  description: string | null;
  vest_type: string | null;
  surface_areas: Record<string, Record<string, number>>;
  available_sizes: string[];
  includes_hard_plates: boolean;
  is_approved: boolean;
  size_measurements: Record<string, GeometrySizeMeasurements> | null;
  pdf_document: GeometryPdf | null;
  image_url: string | null;
  compatibility: string | null;
  notes: string | null;
}

export interface GeometryCreate {
  name: string;
  description?: string | null;
  vest_type?: string | null;
  surface_areas: Record<string, Record<string, number>>;
  available_sizes: string[];
  includes_hard_plates?: boolean;
  is_approved?: boolean;
  size_measurements?: Record<string, GeometrySizeMeasurements> | null;
  pdf_document?: GeometryPdf | null;
  image_url?: string | null;
  compatibility?: string | null;
  notes?: string | null;
}

export interface GeometryUpdate {
  name?: string;
  description?: string | null;
  vest_type?: string | null;
  surface_areas?: Record<string, Record<string, number>>;
  available_sizes?: string[];
  includes_hard_plates?: boolean;
  is_approved?: boolean;
  size_measurements?: Record<string, GeometrySizeMeasurements> | null;
  pdf_document?: GeometryPdf | null;
  image_url?: string | null;
  compatibility?: string | null;
  notes?: string | null;
}

export const geometriesApi = {
  list: async (params?: { vest_type?: string }) => {
    const queryParams = new URLSearchParams();
    if (params?.vest_type) queryParams.append('vest_type', params.vest_type);
    const url = `/api/v1/geometries${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return apiClient.get<Geometry[]>(url);
  },
  
  get: async (id: string) => {
    return apiClient.get<Geometry>(`/api/v1/geometries/${id}`);
  },
  
  create: async (geometry: GeometryCreate) => {
    return apiClient.post<Geometry>('/api/v1/geometries', geometry);
  },
  
  update: async (id: string, geometry: GeometryUpdate) => {
    return apiClient.put<Geometry>(`/api/v1/geometries/${id}`, geometry);
  },
  
  delete: async (id: string) => {
    return apiClient.delete<{ message: string }>(`/api/v1/geometries/${id}`);
  },

  uploadPdf: async (id: string, file: File) => {
    const formData = new FormData();
    formData.append('pdf_file', file);
    return apiClient.post<Geometry>(`/api/v1/geometries/${id}/upload-pdf`, formData);
  },

  downloadPdf: (id: string) => {
    return `${API_BASE_URL}/api/v1/geometries/${id}/download-pdf`;
  },

  deletePdf: async (id: string) => {
    return apiClient.delete<Geometry>(`/api/v1/geometries/${id}/delete-pdf`);
  },

  uploadImage: async (id: string, file: File) => {
    const formData = new FormData();
    formData.append('image_file', file);
    return apiClient.post<Geometry>(`/api/v1/geometries/${id}/upload-image`, formData);
  },

  downloadImage: (id: string) => {
    return `${API_BASE_URL}/api/v1/geometries/${id}/image`;
  },

  deleteImage: async (id: string) => {
    return apiClient.delete<Geometry>(`/api/v1/geometries/${id}/delete-image`);
  },

  downloadExcel: () => {
    return `${API_BASE_URL}/api/v1/geometries/download-excel`;
  },

  uploadExcel: async (file: File) => {
    const formData = new FormData();
    formData.append('excel_file', file);
    return apiClient.post<{ message: string; count: number }>(
      '/api/v1/geometries/upload-excel',
      formData
    );
  },
};

export function useGeometries(params?: { vest_type?: string }) {
  return useQuery({
    queryKey: ['geometries', params],
    queryFn: () => geometriesApi.list(params),
    refetchOnWindowFocus: false,
  });
}

export function useGeometry(id: string) {
  return useQuery({
    queryKey: ['geometry', id],
    queryFn: () => geometriesApi.get(id),
    enabled: !!id,
  });
}

export function useCreateGeometry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (geometry: GeometryCreate) => geometriesApi.create(geometry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    },
  });
}

export function useUpdateGeometry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, geometry }: { id: string; geometry: GeometryUpdate }) =>
      geometriesApi.update(id, geometry),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
      queryClient.invalidateQueries({ queryKey: ['geometry', id] });
    },
  });
}

export function useDeleteGeometry() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => geometriesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['geometries'] });
    },
  });
}
