/**
 * shared/context/BackendStatusContext.tsx
 * Manages backend connectivity status and displays persistent warning when offline
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { apiClient } from '../services/apiClient';

interface BackendStatusContextType {
  isHealthy: boolean | null; // null = unknown, true = healthy, false = offline
  lastChecked: number;
  retryHealth: () => Promise<void>;
}

const BackendStatusContext = createContext<BackendStatusContextType | undefined>(undefined);

export const useBackendStatus = (): BackendStatusContextType => {
  const context = useContext(BackendStatusContext);
  if (!context) {
    throw new Error('useBackendStatus must be used inside BackendStatusProvider');
  }
  return context;
};

interface BackendStatusProviderProps {
  children: ReactNode;
}

export const BackendStatusProvider: React.FC<BackendStatusProviderProps> = ({ children }) => {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const [lastChecked, setLastChecked] = useState(0);

  useEffect(() => {
    // Check on startup
    apiClient.isBackendHealthy().then(healthy => {
      setIsHealthy(healthy);
      setLastChecked(Date.now());
    });

    // Subscribe to status changes
    const handleOffline = () => {
      console.warn('[BackendStatusContext] Backend offline detected');
      setIsHealthy(false);
      setLastChecked(Date.now());
    };

    const handleOnline = () => {
      console.log('[BackendStatusContext] Backend online restored');
      setIsHealthy(true);
      setLastChecked(Date.now());
    };

    apiClient.on('backend-offline', handleOffline);
    apiClient.on('backend-online', handleOnline);

    return () => {
      apiClient.off('backend-offline', handleOffline);
      apiClient.off('backend-online', handleOnline);
    };
  }, []);

  const retryHealth = useCallback(async () => {
    console.log('[BackendStatusContext] Manual health check retry');
    const healthy = await apiClient.refreshHealthCheck();
    setIsHealthy(healthy);
    setLastChecked(Date.now());
  }, []);

  const value: BackendStatusContextType = {
    isHealthy,
    lastChecked,
    retryHealth,
  };

  return (
    <BackendStatusContext.Provider value={value}>
      {children}
    </BackendStatusContext.Provider>
  );
};

/**
 * BackendStatusBanner — Shows persistent warning when backend is offline
 * Does NOT block user interaction — just provides warning
 */
export const BackendStatusBanner: React.FC = () => {
  const { isHealthy, retryHealth } = useBackendStatus();

  if (isHealthy !== false) {
    return null; // Show nothing when healthy or unknown
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        backgroundColor: '#7f1d1d', // Dark red
        borderBottom: '2px solid #dc2626',
        padding: '0.75rem 1rem',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '1rem',
        fontSize: '0.875rem',
        fontWeight: 500,
        boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      }}
      role="alert"
    >
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <span style={{ fontSize: '1.25rem' }}>⚠️</span>
        <span>
          Backend is unreachable. Please check that the server is running on port 8003.
        </span>
      </div>

      <button
        onClick={retryHealth}
        style={{
          padding: '0.5rem 1rem',
          backgroundColor: '#dc2626',
          color: '#fff',
          border: '1px solid #991b1b',
          borderRadius: '0.375rem',
          cursor: 'pointer',
          fontSize: '0.875rem',
          fontWeight: 600,
          whiteSpace: 'nowrap',
          transition: 'background-color 0.2s',
        }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.backgroundColor = '#991b1b';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.backgroundColor = '#dc2626';
        }}
      >
        Retry
      </button>
    </div>
  );
};

/**
 * Hook to wrap main content with top padding when banner is visible
 * This prevents banner from covering page content
 */
export const useBackendBannerPadding = (): string => {
  const { isHealthy } = useBackendStatus();
  return isHealthy === false ? '3.5rem' : '0';
};
