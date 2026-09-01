import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { testSessionsApi, TestSessionCreate, TestSessionUpdate } from '../api/test_session';

export function useTestSessions(params?: { skip?: number; limit?: number; is_official?: boolean }) {
  return useQuery({
    queryKey: ['testSessions', params],
    queryFn: () => testSessionsApi.list(params),
  });
}

export function useTestSession(id: string) {
  return useQuery({
    queryKey: ['testSession', id],
    queryFn: () => testSessionsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateTestSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (testSession: TestSessionCreate) => testSessionsApi.create(testSession),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testSessions'] });
    },
  });
}

export function useCreateFromExcel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, testName, locationId, protocol, vestId, geometryId, testDate, dateFormat, isOfficial, certificationNumber }: { file: File; testName: string; locationId?: string; protocol?: string; vestId: string; geometryId: string; testDate?: string; dateFormat?: string; isOfficial?: boolean; certificationNumber?: string }) =>
      testSessionsApi.createFromExcel(file, testName, locationId, protocol, vestId, geometryId, testDate, dateFormat, isOfficial, certificationNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testSessions'] });
    },
  });
}

export function useUpdateTestSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, testSession, cascade }: { id: string; testSession: TestSessionUpdate; cascade?: boolean }) =>
      testSessionsApi.update(id, testSession, cascade),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['testSessions'] });
      queryClient.invalidateQueries({ queryKey: ['testSession', id] });
    },
  });
}

export function useDeleteTestSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => testSessionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testSessions'] });
    },
  });
}

export function useUploadExcel() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) => testSessionsApi.uploadExcel(id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testSessions'] });
    },
  });
}
