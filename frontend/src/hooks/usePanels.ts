import { useQuery } from '@tanstack/react-query';
import { panelsApi } from '../api/panels';

export function usePanels(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ['panels', params],
    queryFn: () => panelsApi.list(params),
  });
}
