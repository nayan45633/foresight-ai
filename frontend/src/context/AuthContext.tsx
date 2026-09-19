'use client';

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { authApi, LoginPayload, RegisterPayload, UserProfile } from '@/lib/api/auth';
import { clearStoredTokens, getStoredAccessToken } from '@/lib/api/client';

interface AuthContextType {
  user: UserProfile | null;
  role: 'admin' | 'analyst' | 'user' | 'guest';
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshProfile = useCallback(async () => {
    const token = getStoredAccessToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const profile = await authApi.getMe();
      setUser(profile);
    } catch {
      setUser(null);
      clearStoredTokens();
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshProfile();
  }, [refreshProfile]);

  const login = async (credentials: LoginPayload) => {
    setIsLoading(true);
    try {
      await authApi.login(credentials);
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: RegisterPayload) => {
    setIsLoading(true);
    try {
      await authApi.register(payload);
      // Auto login after registration
      await authApi.login({ username_or_email: payload.username, password: payload.password });
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await authApi.logout();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const role: 'admin' | 'analyst' | 'user' | 'guest' = user ? user.role : 'guest';

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated: Boolean(user),
        isLoading,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
