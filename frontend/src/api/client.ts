const API_BASE_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://deltadash-backend-production.up.railway.app';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async getMockData<T>(endpoint: string, options: RequestInit): Promise<T> {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 100));

    // Return mock data based on endpoint
    if (endpoint.includes('/auth/me')) {
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
      } as T;
    }

    if (endpoint.includes('/test-sessions')) {
      if (endpoint.includes('/stats')) {
        return { test_session_count: 0, total_shots: 0 } as T;
      }
      return [] as T;
    }

    if (endpoint.includes('/materials')) {
      return [] as T;
    }

    if (endpoint.includes('/vests')) {
      return [] as T;
    }

    if (endpoint.includes('/ammunition')) {
      return [] as T;
    }

    if (endpoint.includes('/panels')) {
      return [] as T;
    }

    if (endpoint.includes('/shots')) {
      return [] as T;
    }

    if (endpoint.includes('/shot-patterns')) {
      return [] as T;
    }

    if (endpoint.includes('/analytics')) {
      return {
        points: [],
      } as T;
    }

    if (endpoint.includes('/logout')) {
      localStorage.removeItem('token');
      return { message: 'Logged out successfully' } as T;
    }

    if (endpoint.includes('/locations')) {
      return [] as T;
    }

    if (endpoint.includes('/protocols')) {
      return [] as T;
    }

    if (endpoint.includes('/shot-data')) {
      return [] as T;
    }

    // Default empty response
    return {} as T;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const token = localStorage.getItem('token');
    const isFormData = options.body instanceof FormData;
    const config: RequestInit = {
      ...options,
      credentials: 'include',
      headers: isFormData
        ? {
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options.headers,
          }
        : {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options.headers,
          },
    };

    const response = await fetch(url, config);

    if (!response.ok) {
      if (response.status === 401) {
        // Only redirect to login if not already on login page or checking auth
        if (!window.location.pathname.includes('/login') && !endpoint.includes('/auth/me')) {
          window.location.href = '/login';
        }
        // Suppress console error for auth/me endpoint to clean up console
        if (!endpoint.includes('/auth/me')) {
          console.error('Unauthorized request to', endpoint);
        }
        throw new Error('Unauthorized');
      }
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
      // Create an error object that preserves the detail
      const errorObj = new Error(typeof error.detail === 'string' ? error.detail : 'An error occurred') as any;
      errorObj.detail = error.detail;
      throw errorObj;
    }

    if (response.status === 204 || response.headers.get('content-length') === '0') {
      return undefined as T;
    }
    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data instanceof FormData ? data : (data ? JSON.stringify(data) : undefined),
    });
  }

  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }
}

export const apiClient = new ApiClient(API_BASE_URL);
