/**
 * Foresight AI - Authentication API Service
 */

import { apiClient, clearStoredTokens, setStoredTokens } from './client';

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  role: 'admin' | 'analyst' | 'user';
  is_active: boolean;
  is_superuser?: boolean;
  created_at?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
}

export interface LoginPayload {
  username_or_email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  username: string;
  password: string;
  full_name?: string;
  role?: string;
}

export const authApi = {
  async login(credentials: LoginPayload): Promise<AuthTokens> {
    const tokens = await apiClient<AuthTokens>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });
    setStoredTokens(tokens.access_token, tokens.refresh_token);
    return tokens;
  },

  async register(data: RegisterPayload): Promise<UserProfile> {
    return apiClient<UserProfile>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async getMe(): Promise<UserProfile> {
    return apiClient<UserProfile>('/auth/me');
  },

  async logout(): Promise<void> {
    try {
      await apiClient('/auth/logout', { method: 'POST' });
    } catch {
      // Graceful logout even if API call fails
    } finally {
      clearStoredTokens();
    }
  },

  async listUsers(skip = 0, limit = 50): Promise<UserProfile[]> {
    return apiClient<UserProfile[]>(`/auth/users?skip=${skip}&limit=${limit}`);
  },
};
