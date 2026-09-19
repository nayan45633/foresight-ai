/**
 * Foresight AI - Production API Client & Request Dispatcher
 *
 * Centralizes authentication token management, automatic refresh token rotation on 401,
 * request tracing with X-Request-ID, and typed error normalization.
 */

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface ApiErrorDetail {
  code: string;
  message: string;
  request_id?: string;
  details?: any;
}

export class ApiError extends Error {
  public status: number;
  public code: string;
  public requestId?: string;
  public details?: any;

  constructor(status: number, message: string, code?: string, requestId?: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || `HTTP_${status}`;
    this.requestId = requestId;
    this.details = details;
  }
}

// Token Storage Keys
const ACCESS_TOKEN_KEY = 'foresight_access_token';
const REFRESH_TOKEN_KEY = 'foresight_refresh_token';

export function getStoredAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getStoredRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setStoredTokens(accessToken: string, refreshToken?: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  }
}

export function clearStoredTokens(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((callback) => callback(token));
  refreshSubscribers = [];
}

async function attemptTokenRefresh(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearStoredTokens();
      return null;
    }

    const data = await response.json();
    setStoredTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    clearStoredTokens();
    return null;
  }
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
  const token = getStoredAccessToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // If body is FormData (e.g. PCAP upload), delete Content-Type to allow browser boundary setting
  if (options.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (netErr: any) {
    throw new ApiError(0, 'Network connection unavailable. Please check SOC API status.', 'NETWORK_ERROR');
  }

  // Handle 401 Unauthorized with token refresh rotation
  if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await attemptTokenRefresh();
      isRefreshing = false;

      if (newToken) {
        onRefreshed(newToken);
        headers['Authorization'] = `Bearer ${newToken}`;
        return apiClient<T>(endpoint, { ...options, headers });
      }
    } else {
      // Queue requests while refresh is underway
      return new Promise<T>((resolve, reject) => {
        refreshSubscribers.push(async (newToken) => {
          try {
            headers['Authorization'] = `Bearer ${newToken}`;
            const retryRes = await apiClient<T>(endpoint, { ...options, headers });
            resolve(retryRes);
          } catch (err) {
            reject(err);
          }
        });
      });
    }
  }

  if (!response.ok) {
    let errorMsg = response.statusText || 'An unexpected error occurred';
    let errorCode = `HTTP_${response.status}`;
    let requestId: string | undefined;
    let details: any = null;

    try {
      const errorJson = await response.json();
      if (errorJson.error) {
        errorCode = errorJson.error.code || errorCode;
        errorMsg = errorJson.error.message || errorMsg;
        requestId = errorJson.error.request_id;
        details = errorJson.error.details;
      } else if (errorJson.detail) {
        errorMsg = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Fallback on non-JSON response body
    }

    throw new ApiError(response.status, errorMsg, errorCode, requestId, details);
  }

  return response.json() as Promise<T>;
}
