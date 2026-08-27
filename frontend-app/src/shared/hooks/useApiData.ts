/**
 * shared/hooks/useApiData.ts
 * Reusable hook for fetching data from backend APIs using apiClient
 *
 * Usage:
 *   const { data, loading, error, refetch } = useApiData<SyncStatus>('/api/v1/sync/status');
 *
 * Returns:
 *   - data: T | null — the fetched data, null while loading or if error
 *   - loading: boolean — true while fetching initial data
 *   - error: ApiError | null — error if fetch failed
 *   - refetch: () => Promise<T> — manually refetch data
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../services/apiClient';
import type { ApiError } from '../services/apiClient';

export interface UseApiDataResult<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  refetch: () => Promise<T>;
}

export function useApiData<T = any>(
  endpoint: string,
  options?: {
    skip?: boolean;  // If true, don't fetch on mount
    pollInterval?: number;  // Auto-refetch every N ms (disabled by default)
  }
): UseApiDataResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(!options?.skip);
  const [error, setError] = useState<ApiError | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Manual refetch function
  const refetch = useCallback(async (): Promise<T> => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiClient.get<T>(endpoint);
      setData(result);
      return result;
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError);
      throw apiError;
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  // Initial fetch on mount or endpoint change
  useEffect(() => {
    if (options?.skip) return;

    refetch().catch(() => {
      // Error already set in refetch()
    });
  }, [endpoint, options?.skip, refetch]);

  // Auto-polling setup
  useEffect(() => {
    if (!options?.pollInterval || options.skip) return;

    pollIntervalRef.current = setInterval(() => {
      refetch().catch(() => {
        // Silently handle refetch errors during polling
        // (error state already updated in refetch)
      });
    }, options.pollInterval);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [options?.pollInterval, options?.skip, refetch]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  return { data, loading, error, refetch };
}

export default useApiData;
