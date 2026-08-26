import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, API_BASE_URL } from '../api/client';

export interface ModelDocument {
  id: string;
  model_id: string;
  name: string;
  original_name: string | null;
}

export interface VestModel {
  id: string;
  name: string;
  composition: string | null;
  documents: ModelDocument[];
}

export interface VestModelCreate {
  name: string;
  composition?: string | null;
}

export interface VestModelUpdate {
  name?: string;
  composition?: string | null;
}

export const vestModelsApi = {
  list: async () => {
    return apiClient.get<VestModel[]>('/api/v1/vest-models');
  },

  create: async (model: VestModelCreate) => {
    return apiClient.post<VestModel>('/api/v1/vest-models', model);
  },

  update: async (id: string, model: VestModelUpdate) => {
    return apiClient.put<VestModel>(`/api/v1/vest-models/${id}`, model);
  },

  delete: async (id: string) => {
    return apiClient.delete<{ message: string }>(`/api/v1/vest-models/${id}`);
  },

  uploadDocument: async (modelId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<ModelDocument>(`/api/v1/vest-models/${modelId}/documents`, formData);
  },

  downloadDocumentUrl: (modelId: string, docId: string) => {
    return `${API_BASE_URL}/api/v1/vest-models/${modelId}/documents/${docId}/download`;
  },

  deleteDocument: async (modelId: string, docId: string) => {
    return apiClient.delete<{ message: string }>(`/api/v1/vest-models/${modelId}/documents/${docId}`);
  },
};

export function useVestModels() {
  return useQuery({
    queryKey: ['vest-models'],
    queryFn: () => vestModelsApi.list(),
  });
}

export function useCreateVestModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (model: VestModelCreate) => vestModelsApi.create(model),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vest-models'] });
    },
  });
}

export function useUpdateVestModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, model }: { id: string; model: VestModelUpdate }) =>
      vestModelsApi.update(id, model),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vest-models'] });
    },
  });
}

export function useDeleteVestModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => vestModelsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vest-models'] });
    },
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ modelId, file }: { modelId: string; file: File }) =>
      vestModelsApi.uploadDocument(modelId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vest-models'] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ modelId, docId }: { modelId: string; docId: string }) =>
      vestModelsApi.deleteDocument(modelId, docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vest-models'] });
    },
  });
}
