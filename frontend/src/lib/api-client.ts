/**
 * Foresight AI - Standard API Client with automatic JSON parsing and typed responses.
 */

import { API_BASE_URL } from './api/client';

export class ApiError extends Error {
  constructor(public status: number, public message: string, public details?: any) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // Ignore JSON parse failure on non-JSON error bodies
    }
    throw new ApiError(response.status, errorDetail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(endpoint: string, headers?: HeadersInit) =>
    request<T>(endpoint, { method: 'GET', headers }),
  post: <T>(endpoint: string, body: any, headers?: HeadersInit) =>
    request<T>(endpoint, { method: 'POST', body: JSON.stringify(body), headers }),
  patch: <T>(endpoint: string, body: any, headers?: HeadersInit) =>
    request<T>(endpoint, { method: 'PATCH', body: JSON.stringify(body), headers }),
  delete: <T>(endpoint: string, headers?: HeadersInit) =>
    request<T>(endpoint, { method: 'DELETE', headers }),
};
