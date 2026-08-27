import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser, UserRole } from '../types';
import { apiClient } from '../services/apiClient';

interface AuthContextType {
  user: AuthUser | null;
  login: (user: AuthUser) => void;
  logout: () => void;
  isAuthenticated: boolean;
  hasRole: (role: UserRole) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const STORAGE_KEY = 'carelock_auth';

export const useAuth = (): AuthContextType => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
};

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);

  // Restore session on mount
  // CRITICAL: must also re-inject the token into apiClient —
  // the singleton keeps no token between page refreshes.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const stored: AuthUser = JSON.parse(raw);
        setUser(stored);
        // Re-arm the singleton with the stored JWT so that all POST/PUT/DELETE
        // requests made after a hard refresh carry the Authorization header.
        if (stored.access_token) {
          apiClient.setToken(stored.access_token);
        }
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  // Listen for auth expiration from backend
  useEffect(() => {
    const handleAuthExpired = () => {
      console.warn('[AuthContext] Session expired by backend (401 received)');
      logout();
    };

    apiClient.on('auth-expired', handleAuthExpired);
    return () => {
      apiClient.off('auth-expired', handleAuthExpired);
    };
  }, []);

  const login = (u: AuthUser) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
    setUser(u);
    // Set token in apiClient when user logs in
    apiClient.setToken(u.access_token);
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
    // Clear token from apiClient when user logs out
    apiClient.setToken(null);
  };

  const hasRole = (role: UserRole) => user?.role === role;

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
};
