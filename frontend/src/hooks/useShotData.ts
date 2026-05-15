import { useQuery } from '@tanstack/react-query';
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
