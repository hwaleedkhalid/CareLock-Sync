/**
 * useDashboardData — Custom hook that owns all Admin Dashboard data fetching.
 *
 * Responsibilities:
 *   - Fires 5 parallel API calls on mount via Promise.allSettled
 *   - Normalises raw tenant API response into typed TenantRow[]
 *   - Exposes loading, error, and lastRefresh state
 *   - Provides a stable `refresh()` callback for manual re-fetch
 *   - Derives `activeTenantCount` to avoid re-computation in render
 *
 * Keeps AdminDashboard.tsx focused purely on layout & composition.
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { dashboardApi, syncApi, tenantApi } from '../../../shared/services/api';
import type { DashboardStats, SystemMetrics, DataQualityMetrics, SyncStatus } from '../../../shared/types';
import type { TenantRow } from '../components/TenantTable';

export interface SyncHistoryEntry {
  sync_id: string;
  type: 'full' | 'incremental';
  started_at: string;
  completed_at: string;
  stats: Record<string, number> | null;
}

export interface DashboardData {
  // Raw API responses
  stats: DashboardStats | null;
  systemMetrics: SystemMetrics | null;
  dataQuality: DataQualityMetrics | null;
  syncStatus: SyncStatus | null;
  syncHistory: SyncHistoryEntry[];
  tenants: TenantRow[];

  // Derived
  activeTenantCount: number;

  // Meta
  loading: boolean;
  error: string | null;
  lastRefresh: Date;
  refresh: () => Promise<void>;
}

function normaliseTenants(raw: unknown[]): TenantRow[] {
  return raw.map((t: any) => ({
    id: t.id ?? t.tenant_id ?? 0,
    name: t.name ?? t.hospital_name ?? 'Unknown',
    code: t.code ?? t.hospital_code ?? '--',
    status: t.is_active ? 'active' as const : 'inactive' as const,
    patients: t.patients ?? t.patient_count ?? 0,
    lastSync: t.last_sync
      ? new Date(t.last_sync).toLocaleDateString(undefined, {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
        })
      : 'Never',
  }));
}

export function useDashboardData(): DashboardData {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics | null>(null);
  const [dataQuality, setDataQuality] = useState<DataQualityMetrics | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncHistory, setSyncHistory] = useState<SyncHistoryEntry[]>([]);
  const [tenants, setTenants] = useState<TenantRow[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchData = useCallback(async () => {
    setError(null);
    try {
      const [sRes, smRes, dqRes, ssRes, tRes, shRes] = await Promise.allSettled([
        dashboardApi.getStats(),
        dashboardApi.getSystemMetrics(),
        dashboardApi.getDataQuality(),
        syncApi.status(),
        tenantApi.list(),
        syncApi.history(30),
      ]);

      if (sRes.status === 'fulfilled') setStats(sRes.value);
      if (smRes.status === 'fulfilled') setSystemMetrics(smRes.value);
      if (dqRes.status === 'fulfilled') setDataQuality(dqRes.value);
      if (ssRes.status === 'fulfilled') setSyncStatus(ssRes.value);

      if (tRes.status === 'fulfilled' && Array.isArray(tRes.value)) {
        setTenants(normaliseTenants(tRes.value));
      }

      if (shRes.status === 'fulfilled' && Array.isArray(shRes.value?.history)) {
        setSyncHistory(shRes.value.history as SyncHistoryEntry[]);
      }

      // Global error only when ALL calls failed
      const allFailed = [sRes, smRes, dqRes, ssRes, tRes].every(r => r.status === 'rejected');
      if (allFailed) {
        setError('Unable to reach backend API. Ensure the server is running.');
      }

      setLastRefresh(new Date());
    } catch {
      setError('An unexpected error occurred while fetching dashboard data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Live-poll sync status every 2s while a run is active — cheap, just refreshes
  // the in-memory `syncStatus` so the progress bar advances without a full
  // dashboard refetch.
  useEffect(() => {
    if (!syncStatus?.is_syncing) return;
    const iv = window.setInterval(async () => {
      try {
        const fresh = await syncApi.status();
        setSyncStatus(fresh);
        if (!fresh?.is_syncing) {
          // Run ended — pull down the full dashboard to refresh counts
          void fetchData();
        }
      } catch { /* transient, keep polling */ }
    }, 2000);
    return () => window.clearInterval(iv);
  }, [syncStatus?.is_syncing, fetchData]);

  const activeTenantCount = useMemo(
    () => tenants.filter(t => t.status === 'active').length,
    [tenants],
  );

  return {
    stats,
    systemMetrics,
    dataQuality,
    syncStatus,
    syncHistory,
    tenants,
    activeTenantCount,
    loading,
    error,
    lastRefresh,
    refresh: fetchData,
  };
}
