import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { coversApi, CoverCreate, CoverUpdate } from '../api/covers';

export function useCovers() {
  return useQuery({
    queryKey: ['covers'],
    queryFn: () => coversApi.list(),
  });
}

export function useCreateCover() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CoverCreate) => coversApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['covers'] });
    },
  });
}

export function useUpdateCover() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: CoverUpdate }) => coversApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['covers'] });
    },
  });
}

export function useDeleteCover() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => coversApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['covers'] });
    },
  });
}
