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
    // Development bypass: if username is "admin" and password is "admin" and we're in dev mode, skip actual login
    if (credentials.username === 'admin' && credentials.password === 'admin' && import.meta.env.DEV) {
      localStorage.setItem('token', 'dev_bypass_token');
      return { access_token: 'dev_bypass_token', token_type: 'bearer' };
    }

    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await fetch('https://deltadash-backend-production.up.railway.app/api/v1/auth/login', {
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
    // Development bypass: clear token and return success
    if (import.meta.env.DEV) {
            localStorage.removeItem('token');
      return { message: 'Logged out successfully' };
    }
    return apiClient.post<{ message: string }>('/api/v1/auth/logout');
  },

  getCurrentUser: async (): Promise<User> => {
    // Development bypass: return fake user data in dev mode only if token exists
    if (import.meta.env.DEV) {
      const token = localStorage.getItem('token');
      if (!token) {
        throw new Error('Not authenticated');
      }
      return {
        id: '1',
        username: 'admin',
        email: 'admin@example.com',
        full_name: 'Admin User',
        role: 'admin',
        is_active: true,
        is_admin: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    }
    return apiClient.get<User>('/api/v1/auth/me');
  },

  changePassword: async (oldPassword: string, newPassword: string): Promise<{ message: string }> => {
    return apiClient.post<{ message: string }>('/api/v1/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  },
};
