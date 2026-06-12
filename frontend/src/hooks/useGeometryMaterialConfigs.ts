import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';

export interface GeometryMaterialConfig {
  id: string;
  geometry_id: string;
  geometry_name: string;
  size: string;
  material_requirements: Array<{
    material_id: string;
    layer_count: number;
    notes?: string;
  }>;
  accessories: Array<{
    material_id: string;
    quantity_per_vest: number;
    unit: string;
    notes?: string;
  }>;
  efficiency_factor: number | null;
  notes: string | null;
}

export interface GeometryMaterialConfigCreate {
  geometry_id: string;
  size: string;
  material_requirements: Array<{
    material_id: string;
    layer_count: number;
    notes?: string;
  }>;
  accessories: Array<{
    material_id: string;
    quantity_per_vest: number;
    unit: string;
    notes?: string;
  }>;
  efficiency_factor?: number;
  notes?: string;
}

export interface GeometryMaterialConfigUpdate {
  material_requirements?: Array<{
    material_id: string;
    layer_count: number;
    notes?: string;
  }>;
  accessories?: Array<{
    material_id: string;
    quantity_per_vest: number;
    unit: string;
    notes?: string;
  }>;
  efficiency_factor?: number;
  notes?: string;
}

export const useGeometryMaterialConfigs = (params?: { geometry_id?: string; size?: string }) => {
  return useQuery({
    queryKey: ['geometryMaterialConfigs', params],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (params?.geometry_id) searchParams.append('geometry_id', params.geometry_id);
      if (params?.size) searchParams.append('size', params.size);
      const query = searchParams.toString();
      return apiClient.get<GeometryMaterialConfig[]>(
        `/api/v1/geometry-material-configs/${query ? `?${query}` : ''}`
      );
    },
  });
};

export const useGeometryMaterialConfig = (id: string) => {
  return useQuery({
    queryKey: ['geometryMaterialConfig', id],
    queryFn: async () => {
      return apiClient.get<GeometryMaterialConfig>(`/api/v1/geometry-material-configs/${id}`);
    },
    enabled: !!id,
  });
};

export const useCreateGeometryMaterialConfig = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (config: GeometryMaterialConfigCreate) => {
      return apiClient.post<GeometryMaterialConfig>('/api/v1/geometry-material-configs/', config);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['geometryMaterialConfigs'] });
    },
  });
};

export const useUpdateGeometryMaterialConfig = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, config }: { id: string; config: GeometryMaterialConfigUpdate }) => {
      return apiClient.patch<GeometryMaterialConfig>(`/api/v1/geometry-material-configs/${id}`, config);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['geometryMaterialConfigs'] });
      queryClient.invalidateQueries({ queryKey: ['geometryMaterialConfig'] });
    },
  });
};

export const useDeleteGeometryMaterialConfig = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient.delete<void>(`/api/v1/geometry-material-configs/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['geometryMaterialConfigs'] });
    },
  });
};
