import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export interface Geometry {
  id: string;
  name: string;
  description: string | null;
  vest_type: string | null;
  surface_areas: Record<string, Record<string, number>>;
  available_sizes: string[];
  includes_hard_plates: boolean;
  notes: string | null;
}

export interface GeometryCreate {
  name: string;
  description?: string;
  vest_type?: string;
  surface_areas: Record<string, Record<string, number>>;
  available_sizes: string[];
  includes_hard_plates?: boolean;
  notes?: string;
}

export interface GeometryUpdate {
  name?: string;
  description?: string;
  vest_type?: string;
  surface_areas?: Record<string, Record<string, number>>;
  available_sizes?: string[];
  includes_hard_plates?: boolean;
  notes?: string;
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
};

export function useGeometries(params?: { vest_type?: string }) {
  return useQuery({
    queryKey: ['geometries', params],
    queryFn: () => geometriesApi.list(params),
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
