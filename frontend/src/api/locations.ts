import { apiClient } from './client';

export interface Location {
  id: string;
  name: string;
  address?: string;
}

export interface LocationCreate {
  name: string;
  address?: string;
}

export const locationsApi = {
  list: () => apiClient.get<Location[]>('/api/v1/locations'),

  create: (location: LocationCreate) => apiClient.post<Location>('/api/v1/locations', location),

  get: (id: string) => apiClient.get<Location>(`/api/v1/locations/${id}`),

  update: (id: string, location: Partial<LocationCreate>) => apiClient.patch<Location>(`/api/v1/locations/${id}`, location),

  delete: (id: string) => apiClient.delete<void>(`/api/v1/locations/${id}`),
};
