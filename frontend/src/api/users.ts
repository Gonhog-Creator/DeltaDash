import { apiClient } from './client';

export interface AdminUser {
  id: string;
  username: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface AdminUserCreate {
  username: string;
  password: string;
  full_name?: string | null;
  role?: string;
  is_active?: boolean;
  is_admin?: boolean;
}

export interface AdminUserUpdate {
  full_name?: string | null;
  role?: string;
  is_active?: boolean;
  is_admin?: boolean;
  password?: string;
}

export const usersApi = {
  list: () => apiClient.get<AdminUser[]>('/api/v1/admin/users'),

  create: (user: AdminUserCreate) => apiClient.post<AdminUser>('/api/v1/admin/users', user),

  update: (id: string, user: AdminUserUpdate) => apiClient.patch<AdminUser>(`/api/v1/admin/users/${id}`, user),

  delete: (id: string) => apiClient.delete<void>(`/api/v1/admin/users/${id}`),
};
