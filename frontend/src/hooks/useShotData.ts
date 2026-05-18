import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { shotDataApi } from '../api/shot_data';

export function useShotData(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ['shot_data', params],
    queryFn: () => shotDataApi.list(params),
  });
}

export function useShotDataByTestSession(testSessionId: string | null) {
  return useQuery({
    queryKey: ['shot_data', 'test_session', testSessionId],
    queryFn: () => shotDataApi.list({ test_session_id: testSessionId || undefined }),
    enabled: !!testSessionId,
  });
}

export function useUpdateShotData() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, shotData }: { id: string; shotData: import('../api/shot_data').ShotDataUpdate }) =>
      shotDataApi.update(id, shotData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['shot_data'] });
    },
  });
}
