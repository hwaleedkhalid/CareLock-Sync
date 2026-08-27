/**
 * pages/MonitoringPage.tsx — Dark glassmorphism, full ds-* design system.
 * Shared between /admin/monitoring, /hospital/monitoring, /hospital/sync-report.
 * PHASE 2.2: Integrated with apiClient and useApiData hook.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { apiClient } from '../shared/services/apiClient';
import { useApiData } from '../shared/hooks';
import { useAuth } from '../shared/context/AuthContext';
import ErrorBanner from '../shared/ui/ErrorBanner';
import {
  Activity, RefreshCw, Play, CheckCircle2,
  AlertCircle, Clock, Database, Zap, Loader2,
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, AreaChart, Area,
} from 'recharts';

import type { SyncStatus, SystemMetrics } from '../shared/types';

interface MetricsHistory { time: string; records: number; errors: number; latency: number }

/* ── helper: glass card ───────────────────────────────────────────────────── */
const card = (extra?: React.CSSProperties): React.CSSProperties => ({
  background: 'var(--ds-card-bg)',
  backdropFilter: 'var(--ds-card-blur)',
  WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
  border: '1px solid var(--ds-card-border)',
  borderRadius: '1rem',
  boxShadow: 'var(--ds-card-shadow)',
  ...extra,
});

/* ── status chip ──────────────────────────────────────────────────────────── */
const StatusChip: React.FC<{ status: string }> = ({ status }) => {
  const map: Record<string, { bg: string; color: string; border: string }> = {
    operational: { bg: 'var(--ds-status-active-bg)',   color: 'var(--ds-status-active-text)',   border: 'rgba(16,185,129,0.25)' },
    syncing:     { bg: 'var(--ds-status-syncing-bg)',  color: 'var(--ds-status-syncing-text)',  border: 'rgba(59,130,246,0.25)' },
    error:       { bg: 'var(--ds-status-error-bg)',    color: 'var(--ds-status-error-text)',    border: 'rgba(239,68,68,0.25)' },
    unknown:     { bg: 'var(--ds-table-head-bg)',      color: 'var(--ds-text-muted)',           border: 'var(--ds-table-border)' },
    idle:        { bg: 'var(--ds-table-head-bg)',      color: 'var(--ds-text-muted)',           border: 'var(--ds-table-border)' },
  };
  const s = map[status] ?? map.idle;
  return (
    <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.25rem 0.625rem', borderRadius: '2rem', background: s.bg, color: s.color, border: `1px solid ${s.border}`, textTransform: 'capitalize' }}>
      {status}
    </span>
  );
};

/* ── custom tooltip ───────────────────────────────────────────────────────── */
const ChartTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;
  return (
    <div style={{ background: 'var(--ds-surface-2)', border: '1px solid var(--ds-border)', borderRadius: '0.75rem', padding: '0.625rem 0.875rem', fontSize: '0.75rem', boxShadow: '0 8px 24px rgba(0,0,0,0.35)' }}>
      <p style={{ fontWeight: 700, color: 'var(--ds-text-primary)', margin: '0 0 0.375rem' }}>{label}</p>
      {payload.map((e: any, i: number) => (
        <div key={i} style={{ display: 'flex', gap: '0.375rem', alignItems: 'center' }}>
          <div style={{ width: 8, height: 8, borderRadius: '2px', background: e.color, flexShrink: 0 }} />
          <span style={{ color: 'var(--ds-text-muted)' }}>{e.name}:</span>
          <span style={{ color: 'var(--ds-text-primary)', fontWeight: 700 }}>{e.value}</span>
        </div>
      ))}
    </div>
  );
};

/* ── component ────────────────────────────────────────────────────────────── */
const MonitoringPage: React.FC = () => {
  const { user } = useAuth();

  // Fetch sync status and system metrics using new hook
  const syncData = useApiData<SyncStatus>('/api/v1/sync/status');
  const metricsData = useApiData<SystemMetrics>('/api/v1/system/metrics');

  // State for manual refresh and trigger
  const [history] = useState<MetricsHistory[]>([]);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Combined loading and error states
  const isLoading = syncData.loading || metricsData.loading;
  const error = syncData.error ?? metricsData.error;

  // Combined refetch for both endpoints — use allSettled to handle partial failures
  const refetchAll = useCallback(async () => {
    const results = await Promise.allSettled([
      syncData.refetch(),
      metricsData.refetch(),
    ]);

    // Log any failures (errors are already set in hook state)
    results.forEach((result, idx) => {
      if (result.status === 'rejected') {
        const endpoint = idx === 0 ? '/api/v1/sync/status' : '/api/v1/system/metrics';
        console.warn(`[MonitoringPage] Failed to refetch ${endpoint}:`, result.reason);
      }
    });
  }, [syncData, metricsData]);

  // Auto-refresh logic
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(refetchAll, 10000);
    return () => clearInterval(id);
  }, [autoRefresh, refetchAll]);

  const triggerSync = async () => {
    // Safety: prevent rapid clicks
    if (triggering) return;

    setTriggering(true);
    setTriggerResult(null);

    try {
      // Use tenant_id from auth context (fallback to 1 if missing)
      const tenantId = user?.tenant_id ?? 1;

      const res = await apiClient.post<{ message?: string }>('/api/v1/sync/full', {
        tenant_id: tenantId,
      });

      setTriggerResult({ ok: true, msg: res.message ?? 'Sync triggered successfully.' });
      console.log('[MonitoringPage] Sync triggered successfully for tenant', tenantId);

      // Refetch after 2s delay to show updated status
      setTimeout(refetchAll, 2000);
    } catch (err) {
      const apiError = err as any;
      const msg = apiError?.userMessage || apiError?.message || 'Failed to trigger sync.';
      setTriggerResult({ ok: false, msg });
      console.error('[MonitoringPage] Failed to trigger sync:', err);
    } finally {
      setTriggering(false);
    }
  };

  const kpiCards = [
    {
      label: 'Sync Status',
      value: syncData.data ? (syncData.data.is_syncing ? 'syncing' : 'operational') : 'unknown',
      icon: <Activity style={{ width: 16, height: 16, color: '#60a5fa' }} />,
      sub: syncData.data?.last_sync_time ? `Last: ${new Date(syncData.data.last_sync_time).toLocaleTimeString()}` : 'No sync yet',
      isBadge: true,
      grad: 'linear-gradient(135deg,rgba(59,130,246,0.15),rgba(59,130,246,0.03))',
    },
    {
      label: 'Total Syncs',
      value: syncData.data?.total_syncs?.toLocaleString() ?? '—',
      icon: <Database style={{ width: 16, height: 16, color: '#34d399' }} />,
      sub: 'Completed sync jobs',
      grad: 'linear-gradient(135deg,rgba(16,185,129,0.15),rgba(16,185,129,0.03))',
    },
    {
      label: 'Last Sync Records',
      value: syncData.data?.last_sync_stats ? String(Object.values(syncData.data.last_sync_stats).reduce((a, b) => a + b, 0)) : '—',
      icon: <AlertCircle style={{ width: 16, height: 16, color: '#818cf8' }} />,
      sub: 'Records in last sync',
      grad: 'linear-gradient(135deg,rgba(99,102,241,0.15),rgba(99,102,241,0.03))',
    },
    {
      label: 'Avg Latency',
      value: metricsData.data?.avg_latency != null ? `${Math.round(metricsData.data.avg_latency)}ms` : '—',
      icon: <Zap style={{ width: 16, height: 16, color: '#fbbf24' }} />,
      sub: 'API response time',
      grad: 'linear-gradient(135deg,rgba(245,158,11,0.15),rgba(245,158,11,0.03))',
    },
  ];

  const axisProps = { fontSize: 11, fill: 'var(--ds-text-muted)' } as any;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Activity style={{ width: 22, height: 22, color: '#60a5fa' }} />System Monitoring
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>Real-time sync status and performance metrics</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)', cursor: 'pointer', userSelect: 'none' }}>
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} style={{ accentColor: '#7c3aed' }} />
            Auto-refresh (10 s)
          </label>
          <button onClick={refetchAll} disabled={isLoading} className="ds-btn" style={{ fontSize: '0.8125rem', opacity: isLoading ? 0.6 : 1 }}>
            <RefreshCw style={{ width: 13, height: 13 }} />Refresh
          </button>
          <button onClick={triggerSync} disabled={triggering} className="ds-btn ds-btn-primary" style={{ fontSize: '0.8125rem', opacity: triggering ? 0.6 : 1 }}>
            {triggering ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 0.8s linear infinite' }} /> : <Play style={{ width: 13, height: 13 }} />}
            Trigger Sync
          </button>
        </div>
      </div>

      {error && (
        <ErrorBanner
          message="Failed to load monitoring data"
          detail={error.userMessage || error.message || 'An error occurred while fetching data'}
          onRetry={refetchAll}
        />
      )}

      {/* Trigger result banner */}
      {triggerResult && (
        <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.75rem 1rem', borderRadius: '0.75rem', background: triggerResult.ok ? 'var(--ds-status-active-bg)' : 'var(--ds-status-error-bg)', border: `1px solid ${triggerResult.ok ? 'rgba(16,185,129,0.25)' : 'rgba(239,68,68,0.25)'}`, fontSize: '0.8125rem', color: triggerResult.ok ? 'var(--ds-status-active-text)' : 'var(--ds-status-error-text)' }}>
          <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0 }} />
          {triggerResult.msg}
        </div>
      )}

      {/* KPI cards */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '1rem' }}>
        {kpiCards.map(c => (
          <div key={c.label} style={{ background: c.grad, border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.125rem', transition: 'border-color 0.25s,transform 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-hover-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{c.label}</span>
              {c.icon}
            </div>
            {c.isBadge
              ? <StatusChip status={String(c.value)} />
              : <p style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>{String(c.value)}</p>}
            <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', margin: '0.375rem 0 0' }}>{c.sub}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(400px,1fr))', gap: '1rem' }}>
        {/* Records chart */}
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Records synced over time</h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={history} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gRec" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
              <XAxis dataKey="time" tick={axisProps} axisLine={false} tickLine={false} />
              <YAxis tick={axisProps} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
              <Area type="monotone" dataKey="records" stroke="#3b82f6" strokeWidth={2} fill="url(#gRec)" name="Records" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Latency chart */}
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>API latency (ms)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={history} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
              <XAxis dataKey="time" tick={axisProps} axisLine={false} tickLine={false} />
              <YAxis tick={axisProps} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--ds-border)' }} />
              <Line type="monotone" dataKey="latency" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Latency (ms)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* System metrics */}
      {metricsData.data && (
        <div className="ds-animate ds-animate-d3" style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>System metrics</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', gap: '0.75rem' }}>
            {[
              { label: 'API Requests',    value: metricsData.data.api_requests?.toLocaleString() ?? '—' },
              { label: 'Error Rate',      value: metricsData.data.error_rate != null ? `${(metricsData.data.error_rate * 100).toFixed(2)}%` : '—' },
              { label: 'CDC Operations',  value: metricsData.data.cdc_operations?.toLocaleString() ?? '—' },
              { label: 'ETL Syncs',       value: metricsData.data.etl_syncs?.toLocaleString() ?? '—' },
              { label: 'Avg Latency',     value: metricsData.data.avg_latency != null ? `${Math.round(metricsData.data.avg_latency)}ms` : '—' },
            ].map(m => (
              <div key={m.label} style={{ background: 'var(--ds-table-head-bg)', borderRadius: '0.75rem', padding: '0.875rem', textAlign: 'center', border: '1px solid var(--ds-table-border)' }}>
                <p style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: '0 0 0.25rem', letterSpacing: '-0.02em' }}>{m.value}</p>
                <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', margin: 0 }}>{m.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Observability note */}
      <div className="ds-animate ds-animate-d4" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', background: 'rgba(59,130,246,0.10)', border: '1px solid rgba(59,130,246,0.20)', borderRadius: '0.875rem', padding: '1rem 1.125rem', fontSize: '0.8125rem', color: '#93c5fd' }}>
        <Clock style={{ width: 15, height: 15, flexShrink: 0, marginTop: 2 }} />
        <div>
          <p style={{ fontWeight: 700, margin: '0 0 0.25rem' }}>Full observability available via Grafana</p>
          <p style={{ margin: 0, opacity: 0.75, fontSize: '0.75rem' }}>
            Run <code style={{ background: 'rgba(59,130,246,0.20)', padding: '0.1rem 0.4rem', borderRadius: '0.3rem', fontFamily: 'monospace' }}>docker compose -f docker/observability/docker-compose.yml up -d</code>{' '}
            then open <strong>http://localhost:3001</strong> (admin / carelock_admin_2026)
          </p>
        </div>
      </div>
    </div>
  );
};

export default MonitoringPage;
