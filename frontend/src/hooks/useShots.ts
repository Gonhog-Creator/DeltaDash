import { useQuery } from '@tanstack/react-query';
import { shotsApi } from '../api/shots';

export function useShots(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ['shots', params],
    queryFn: () => shotsApi.list(params),
  });
}

export function useShotsByTestSession(testSessionId: string | null) {
  return useQuery({
    queryKey: ['shots', 'test_session', testSessionId],
    queryFn: () => shotsApi.list({ test_session_id: testSessionId || undefined }),
    enabled: !!testSessionId,
  });
}
