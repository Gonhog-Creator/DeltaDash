import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { locationsApi, LocationCreate } from '../api/locations';

export function useLocations() {
  return useQuery({
    queryKey: ['locations'],
    queryFn: () => locationsApi.list(),
  });
}

export function useCreateLocation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (location: LocationCreate) => locationsApi.create(location),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations'] });
    },
  });
}

export function useDeleteLocation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => locationsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations'] });
    },
  });
}

export function useUpdateLocation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, location }: { id: string; location: Partial<LocationCreate> }) => 
      locationsApi.update(id, location),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['locations'] });
    },
  });
}
