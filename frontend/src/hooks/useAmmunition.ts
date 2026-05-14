import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ammunitionApi, Ammunition, AmmunitionCreate, AmmunitionUpdate } from '../api/ammunition';

export function useAmmunition(params?: { skip?: number; limit?: number; caliber?: string }) {
  return useQuery({
    queryKey: ['ammunition', params],
    queryFn: () => ammunitionApi.list(params),
  });
}

export function useAmmunitionItem(id: string) {
  return useQuery({
    queryKey: ['ammunition', id],
    queryFn: () => ammunitionApi.get(id),
    enabled: !!id,
  });
}

export function useCreateAmmunition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (ammunition: AmmunitionCreate) => ammunitionApi.create(ammunition),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ammunition'] });
    },
  });
}

export function useUpdateAmmunition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, ammunition }: { id: string; ammunition: AmmunitionUpdate }) =>
      ammunitionApi.update(id, ammunition),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['ammunition'] });
      queryClient.invalidateQueries({ queryKey: ['ammunition', id] });
    },
  });
}

export function useDeleteAmmunition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => ammunitionApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ammunition'] });
    },
  });
}
