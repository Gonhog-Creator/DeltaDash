import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { materialsApi, MaterialCreate, MaterialUpdate } from '../api/materials';

export function useMaterials(params?: { skip?: number; limit?: number; material_class?: string; manufacturer?: string }) {
  return useQuery({
    queryKey: ['materials', params],
    queryFn: () => materialsApi.list(params),
  });
}

export function useMaterial(id: string) {
  return useQuery({
    queryKey: ['material', id],
    queryFn: () => materialsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateMaterial() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ material, files }: { material: MaterialCreate; files?: { mss?: File; sds?: File } }) =>
      materialsApi.create(material, files),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
  });
}

export function useUpdateMaterial() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, material }: { id: string; material: MaterialUpdate }) =>
      materialsApi.update(id, material),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      queryClient.invalidateQueries({ queryKey: ['material', id] });
    },
  });
}

export function useUploadMaterialFiles() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, files }: { id: string; files: { mss?: File; sds?: File } }) =>
      materialsApi.uploadFiles(id, files),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      queryClient.invalidateQueries({ queryKey: ['material', id] });
    },
  });
}

export function useDeleteMaterial() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => materialsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    },
  });
}

export function useRemoveMaterialFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, fileType }: { id: string; fileType: 'mss' | 'sds' }) =>
      materialsApi.removeFile(id, fileType),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      queryClient.invalidateQueries({ queryKey: ['material', id] });
    },
  });
}
