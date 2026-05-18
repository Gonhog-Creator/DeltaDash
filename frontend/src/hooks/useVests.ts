import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { vestsApi, VestCreate, VestUpdate, VestLayerCreate } from '../api/vests';

export function useVests(params?: { skip?: number; limit?: number; vest_type?: string; threat_level?: string }) {
  return useQuery({
    queryKey: ['vests', params],
    queryFn: () => vestsApi.list(params),
  });
}

export function useVest(id: string) {
  return useQuery({
    queryKey: ['vest', id],
    queryFn: () => vestsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateVest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (vest: VestCreate) => vestsApi.create(vest),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vests'] });
    },
  });
}

export function useUpdateVest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, vest }: { id: string; vest: VestUpdate }) =>
      vestsApi.update(id, vest),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['vests'] });
      queryClient.invalidateQueries({ queryKey: ['vest', id] });
    },
  });
}

export function useDeleteVest() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => vestsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vests'] });
    },
  });
}

export function useUpdateVestLayers() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, layers }: { id: string; layers: VestLayerCreate[] }) =>
      vestsApi.updateLayers(id, layers),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['vests'] });
      queryClient.invalidateQueries({ queryKey: ['vest', id] });
    },
  });
}
