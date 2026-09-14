import { apiClient } from './client';

export interface AmmunitionConfig {
  ammunition_id: string;
  reference_velocity_m_s: number;
  velocity_window_m_s?: number | null;
  shots_per_panel: number;
}

export interface ProtocolLevel {
  level_name: string;
  ammunition_config: AmmunitionConfig[];
}

export interface Protocol {
  id: string;
  name: string;
  description?: string;
  levels_config?: ProtocolLevel[] | null;
}

export interface ProtocolCreate {
  name: string;
  description?: string;
  levels_config?: ProtocolLevel[] | null;
}

export const protocolsApi = {
  list: () => apiClient.get<Protocol[]>('/api/v1/protocols'),

  create: (protocol: ProtocolCreate) => apiClient.post<Protocol>('/api/v1/protocols', protocol),

  get: (id: string) => apiClient.get<Protocol>(`/api/v1/protocols/${id}`),

  update: (id: string, protocol: Partial<ProtocolCreate>) => apiClient.patch<Protocol>(`/api/v1/protocols/${id}`, protocol),

  delete: (id: string) => apiClient.delete<void>(`/api/v1/protocols/${id}`),
};
