import { apiClient } from './client';

export interface TestSession {
  id: string;
  name: string;
  test_date: string | null;
  lab_name: string | null;
  protocol: string | null;
  clay_temperature_c: number | null;
  ambient_temperature_c: number | null;
  humidity_percent: number | null;
  conditioning: string | null;
  size: string | null;
  ballistic_limit: boolean | null;
  parent_test_group_id: string | null;
  vest_id: string | null;
  vest_name: string | null;
  vest_code: string | null;
  geometry_id: string | null;
  geometry_name: string | null;
  excel_file_path: string | null;
  notes: string | null;
  is_official: boolean;
  certification_number: string | null;
  created_at: string;
  updated_at: string;
  shot_count?: number | null;
  vest?: { id: string; vest_code: string | null; name: string | null } | null;
  geometry?: { id: string; name: string | null } | null;
}

export interface TestSessionCreate {
  name: string;
  test_date?: string | null;
  lab_name?: string | null;
  protocol?: string | null;
  clay_temperature_c?: number | null;
  ambient_temperature_c?: number | null;
  humidity_percent?: number | null;
  conditioning?: string | null;
  geometry_id: string;
  notes?: string | null;
}

export interface TestSessionUpdate {
  name?: string | null;
  test_date?: string | null;
  lab_name?: string | null;
  protocol?: string | null;
  clay_temperature_c?: number | null;
  ambient_temperature_c?: number | null;
  humidity_percent?: number | null;
  conditioning?: string | null;
  vest_id?: string | null;
  geometry_id?: string | null;
  notes?: string | null;
  certification_number?: string | null;
}

export const testSessionsApi = {
  list: (params?: { skip?: number; limit?: number; is_official?: boolean }) => {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.is_official !== undefined) searchParams.append('is_official', params.is_official.toString());
    const query = searchParams.toString();
    return apiClient.get<TestSession[]>(`/api/v1/test-sessions${query ? `?${query}` : ''}`);
  },

  get: (id: string) => apiClient.get<TestSession>(`/api/v1/test-sessions/${id}`),

  create: (testSession: TestSessionCreate) => apiClient.post<TestSession>('/api/v1/test-sessions', testSession),

  createFromExcel: (file: File, testName: string, locationId: string | undefined, protocol: string | undefined, vestId: string, geometryId: string, testDate: string | undefined, dateFormat: string | undefined, isOfficial: boolean | undefined, certificationNumber: string | undefined) => {
    const formData = new FormData();
    formData.append('excel_file', file);
    formData.append('test_name', testName);
    if (locationId) {
      formData.append('location_id', locationId);
    }
    if (protocol) {
      formData.append('protocol', protocol);
    }
    if (vestId) {
      formData.append('vest_id', vestId);
    }
    formData.append('geometry_id', geometryId);
    if (testDate) {
      formData.append('test_date', testDate);
    }
    if (dateFormat) {
      formData.append('date_format', dateFormat);
    }
    if (isOfficial !== undefined) {
      formData.append('is_official', isOfficial.toString());
    }
    if (certificationNumber !== undefined) {
      formData.append('certification_number', certificationNumber);
    }
    return apiClient.post<TestSession[]>('/api/v1/test-sessions/from-excel', formData);
  },

  update: (id: string, testSession: TestSessionUpdate, cascade?: boolean) => {
    const query = cascade !== undefined ? `?cascade=${cascade.toString()}` : '';
    return apiClient.patch<TestSession>(`/api/v1/test-sessions/${id}${query}`, testSession);
  },

  uploadExcel: (id: string, file: File) => {
    const formData = new FormData();
    formData.append('excel_file', file);
    return apiClient.post<TestSession>(`/api/v1/test-sessions/${id}/upload-excel`, formData);
  },

  delete: (id: string) => apiClient.delete<void>(`/api/v1/test-sessions/${id}`),
};
