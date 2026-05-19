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

    const token = await apiClient.post<Token>('/api/v1/auth/login', formData);
    // Store token in localStorage for fallback
    localStorage.setItem('token', token.access_token);
    return token;
  },

  logout: async (): Promise<{ message: string }> => {
    const result = await apiClient.post<{ message: string }>('/api/v1/auth/logout');
    // Remove token from localStorage
    localStorage.removeItem('token');
    return result;
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
