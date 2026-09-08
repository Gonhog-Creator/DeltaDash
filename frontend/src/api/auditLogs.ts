import { apiClient } from './client';

export interface AuditLogEntry {
  id: string;
  user_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  before_json: Record<string, any> | null;
  after_json: Record<string, any> | null;
  created_at: string;
}

export const auditLogsApi = {
  list: (params?: { user_id?: string; entity_type?: string; action?: string; days?: number; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.user_id) searchParams.append('user_id', params.user_id);
    if (params?.entity_type) searchParams.append('entity_type', params.entity_type);
    if (params?.action) searchParams.append('action', params.action);
    if (params?.days) searchParams.append('days', String(params.days));
    if (params?.limit) searchParams.append('limit', String(params.limit));
    const query = searchParams.toString();
    return apiClient.get<AuditLogEntry[]>(`/api/v1/audit-logs/${query ? `?${query}` : ''}`);
  },

  entityTypes: () => apiClient.get<string[]>('/api/v1/audit-logs/entity-types'),
};
