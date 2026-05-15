import { apiClient } from './client';

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export const authApi = {
  login: async (credentials: LoginCredentials): Promise<Token> => {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/auth/login`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    return response.json();
  },

  logout: async (): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>('/api/v1/auth/logout');
  },

  getCurrentUser: async (): Promise<User> => {
    return apiClient.get<User>('/api/v1/auth/me');
  },

  changePassword: async (oldPassword: string, newPassword: string): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>('/api/v1/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  },
};
