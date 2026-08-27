import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, API_BASE_URL } from '../api/client';
import { vestsApi } from '../api/vests';

export interface ModelDocument {
  id: string;
  vest_id: string;
  name: string;
  original_name: string | null;
}

export interface VestModel {
  id: string;
  name: string;
  composition: string | null;
  documents: ModelDocument[];
}

export const vestModelsApi = {
  list: async () => {
    const vests = await vestsApi.list({ is_catalog_model: true });
    return vests.map(v => ({
      id: v.id,
      name: v.vest_code,
      composition: v.composition ?? null,
      documents: [],
    })) as VestModel[];
  },

  uploadDocument: async (vestId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<ModelDocument>(`/api/v1/vests/${vestId}/documents`, formData);
  },

  downloadDocumentUrl: (vestId: string, docId: string) => {
    return `${API_BASE_URL}/api/v1/vests/${vestId}/documents/${docId}/download`;
  },

  deleteDocument: async (vestId: string, docId: string) => {
    return apiClient.delete<{ message: string }>(`/api/v1/vests/${vestId}/documents/${docId}`);
  },
};

export function useVestModels() {
  return useQuery({
    queryKey: ['vests'],
    queryFn: () => vestModelsApi.list(),
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ modelId, file }: { modelId: string; file: File }) =>
      vestModelsApi.uploadDocument(modelId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vests'] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ modelId, docId }: { modelId: string; docId: string }) =>
      vestModelsApi.deleteDocument(modelId, docId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vests'] });
    },
  });
}
