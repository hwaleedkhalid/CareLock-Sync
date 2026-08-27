/**
 * AdminDashboard.tsx — Healthcare Data Pipeline Observability Dashboard
 *
 * Monitors:
 * • CDC (Change Data Capture) pipeline health
 * • ETL (Extract-Transform-Load) processing
 * • Multi-database adapter connections (PostgreSQL, MySQL, MongoDB, Oracle, SQL Server)
 * • Data quality and ingestion lag
 * • Real-time performance trends
 *
 * CRITICAL: All metrics come from real backend APIs
 * - NO mock data
 * - NO fake datasets
 * - All charts built from actual API polling
 */
import React, { useState, useMemo, useCallback } from 'react';
import { RefreshCw, Database, TrendingUp } from 'lucide-react';
import { useApiData, useTimeSeries } from '../../../shared/hooks';
import ErrorBanner from '../../../shared/ui/ErrorBanner';
import AuthGuard from '../../../shared/components/AuthGuard';
import ErrorFallback from '../../../shared/components/ErrorFallback';
import SystemInsights from '../components/SystemInsights';
import CDCSourcesGrid from '../components/CDCSourcesGrid';
import {
  normalizeConnectorHealth,
  normalizeDatabaseStatus,
  normalizeSystemStatus,
} from '../../../shared/utils/apiNormalizers';
import {
  LineChart, Line, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

// ── Component ─────────────────────────────────────────────────────────────────
const AdminDashboard: React.FC = () => {
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  // ── API calls ──────────────────────────────────────────────────────────────
  const connectorRaw  = useApiData<any>('/api/v1/connector/health',         { pollInterval: 10000 });
  const hospitalDbRaw = useApiData<any>('/api/v1/status/database/hospital', { pollInterval: 15000 });
  const sharedDbRaw   = useApiData<any>('/api/v1/status/database/shared',   { pollInterval: 15000 });
  const systemRaw     = useApiData<any>('/api/v1/status/system',            { pollInterval: 15000 });
  const cdcMetricsRaw = useApiData<any>('/api/v1/system/metrics',           { pollInterval: 10000 });
  const tenantsRaw    = useApiData<any[]>('/api/v1/connector/tenants',      { pollInterval: 30000 });

  // ── Normalize raw responses ────────────────────────────────────────────────
  const connectorData = useMemo(
    () => connectorRaw.data ? normalizeConnectorHealth(connectorRaw.data) : null,
    [connectorRaw.data]
  );

  const hospitalDbData = useMemo(
    () => hospitalDbRaw.data ? normalizeDatabaseStatus(hospitalDbRaw.data, 'postgresql') : null,
    [hospitalDbRaw.data]
  );

  const sharedDbData = useMemo(
    () => sharedDbRaw.data ? normalizeDatabaseStatus(sharedDbRaw.data, 'postgresql') : null,
    [sharedDbRaw.data]
  );

  const systemData = useMemo(
    () => systemRaw.data ? normalizeSystemStatus(systemRaw.data) : null,
    [systemRaw.data]
  );

  // ── Real CDC metrics from /api/v1/system/metrics (cdc_inbox tables) ────────
  // available=false means CDC schema not yet deployed — show N/A in that case.
  const cdcMetrics = cdcMetricsRaw.data ?? null;
  const cdcAvailable = cdcMetrics?.available === true;

  // ── Avg latency from real per-DB pings in connector health ─────────────────
  // The connector health endpoint measures actual SELECT-1 round-trips for each
  // database. Average those real values instead of the system status endpoint.
  const avgLatency = useMemo((): number | null => {
    const lats = (connectorData?.adapters ?? [])
      .map((a: any) => a.latency_ms)
      .filter((v: any): v is number => typeof v === 'number' && v > 0);
    if (lats.length === 0) return null;
    return Math.round((lats.reduce((a: number, b: number) => a + b, 0) / lats.length) * 10) / 10;
  }, [connectorData]);

  // ── Time-series accumulators (real API polling — NO mock data) ─────────────
  // CRITICAL: extractors must be stable references (useCallback) so useTimeSeries
  // doesn't re-run on every render.
  const latencyExtractor     = useCallback((data: any) => data.avg_latency_ms,       []);
  const throughputExtractor  = useCallback((data: any) => data.throughput_records_sec,[]);
  const cdcCaptureExtractor  = useCallback((data: any) => data.cdc_capture_rate,      []);
  const cdcLagExtractor      = useCallback((data: any) => data.cdc_lag_max_seconds,   []);
  const etlExtractor         = useCallback((data: any) => data.etl_processing_time_ms,[]);

  // Latency series driven by system status (which now returns real avg latency)
  const latencySeries     = useTimeSeries(systemData,    latencyExtractor,    30);
  const throughputSeries  = useTimeSeries(connectorData, throughputExtractor,  30);
  const cdcCaptureSeries  = useTimeSeries(connectorData, cdcCaptureExtractor,  30);
  const cdcLagSeries      = useTimeSeries(connectorData, cdcLagExtractor,      30);
  const etlTimeSeries     = useTimeSeries(connectorData, etlExtractor,         30);

  // ── Combined loading / error ───────────────────────────────────────────────
  const isLoading = connectorRaw.loading || hospitalDbRaw.loading || sharedDbRaw.loading || systemRaw.loading;
  const tenants   = tenantsRaw.data || [];
  const error     = connectorRaw.error ?? hospitalDbRaw.error ?? sharedDbRaw.error ?? systemRaw.error;

  // ── Extract display values (BEFORE any early return — Rules of Hooks) ──────
  const adapters        = connectorData?.adapters        || [];
  const cdcLagMax       = connectorData?.cdc_lag_max_seconds    ?? null;
  const workersReady    = connectorData?.workers_ready          ?? 0;
  const workersTotal    = connectorData?.workers_total          ?? 0;
  const failedAdapters  = connectorData?.failed_adapters        ?? 0;
  const uptime          = systemData?.uptime_seconds            ?? null;
  const activeServices  = systemData?.active_services           ?? 0;
  const failedServices  = systemData?.failed_services           ?? 0;

  // CDC pipeline KPIs — real values from cdc_inbox, or null when CDC not deployed.
  const cdcRate          = cdcAvailable ? null : null;                    // capture rate not yet derivable from cdc_inbox alone
  const cdcExpected      = 99;
  const throughput       = cdcAvailable
    ? (cdcMetrics.throughput_per_min != null
        ? Math.round(cdcMetrics.throughput_per_min / 60 * 10) / 10      // real: rows/min → rows/sec
        : null)
    : null;
  const etlProcessingTime = null;                                         // no ETL timing instrument yet
  const failed24h         = null;                                         // no per-run failure counter yet

  // Stroke colour for CDC capture rate chart (green when healthy, amber otherwise)
  const cdcCaptureStroke = useMemo(
    () => (cdcCaptureSeries?.length > 0 && cdcCaptureSeries[cdcCaptureSeries.length - 1]?.value >= (cdcExpected - 5))
      ? '#34d399'
      : '#f59e0b',
    [cdcCaptureSeries, cdcExpected]
  );

  // Handle auth errors (403/401) with graceful fallback (conditional logic AFTER all hooks)
  if (error && 'status' in error && (error.status === 403 || error.status === 401)) {
    return (
      <ErrorFallback
        error={error}
        logout={() => {
          // Trigger auth-expired event which AuthContext listens for
          const event = new CustomEvent('auth-expired');
          window.dispatchEvent(event);
        }}
      />
    );
  }

  // Combined refetch for all endpoints
  const refetchAll = async () => {
    await Promise.allSettled([
      connectorRaw.refetch(),
      hospitalDbRaw.refetch(),
      sharedDbRaw.refetch(),
      systemRaw.refetch(),
      cdcMetricsRaw.refetch(),
      tenantsRaw.refetch(),
    ]);
    setLastRefresh(new Date());
  };

  // Early return for initial loading (conditional logic AFTER all hooks)
  if (isLoading && !connectorData && !systemData) {
    return (
      <div style={{ maxWidth: 1400, margin: '0 auto', padding: '1.5rem', fontFamily: "'Inter', sans-serif" }}>
        <div style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '1.5rem' }}>System Health Monitor</div>
        <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)' }}>
          Loading health data…
        </div>
      </div>
    );
  }

  // Extract Database Connection Status (Healthcare Data Sources)
  const dbs = [
    { name: 'Hospital DB', data: hospitalDbData },
    { name: 'Shared DB', data: sharedDbData },
  ];

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter', sans-serif" }}>

      {/* Error banner */}
      {error && (
        <ErrorBanner
          message="Failed to load system health data"
          detail={error.userMessage || error.message || 'Failed to load system health'}
          onRetry={refetchAll}
        />
      )}

      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>Data Pipeline Observability</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)', margin: '0.25rem 0 0' }}>
            Healthcare ETL Pipeline • CDC Capture • Multi-Database Adapters • Real-time Performance
            {systemData?.cdc_pipeline_healthy === false && ' • ⚠️ Pipeline Health Issues'}
          </p>
        </div>
        <button onClick={refetchAll} disabled={isLoading} className="ds-btn" style={{ opacity: isLoading ? 0.6 : 1, cursor: isLoading ? 'not-allowed' : 'pointer' }}>
          <RefreshCw style={{ width: 13, height: 13, ...(isLoading ? { animation: 'spin 0.7s linear infinite' } : {}) }} />
          Refresh
        </button>
      </div>

      {/* ============ CDC SOURCES GRID (ALL 5 DATABASES) ============ */}
      <div className="ds-animate ds-animate-d1" style={{ marginBottom: '2rem' }}>
        <CDCSourcesGrid adapters={adapters} isLoading={isLoading} />
      </div>

      {/* ============ CENTRAL DB — REGISTERED TENANTS ============ */}
      <div className="ds-animate ds-animate-d1" style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
          <Database style={{ width: 16, height: 16 }} />
          Central DB — Registered Tenants ({tenants.length})
        </div>
        <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', overflow: 'hidden' }}>
          {tenantsRaw.loading && tenants.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)', fontSize: '0.8125rem' }}>Loading tenants…</div>
          ) : tenants.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)', fontSize: '0.8125rem' }}>No tenants registered</div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ds-border)' }}>
                    {['ID', 'Hospital', 'Code', 'Platform', 'Partition', 'Status', 'Onboarded', 'Last Sync'].map(h => (
                      <th key={h} style={{ padding: '0.625rem 1rem', textAlign: 'left', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tenants.map((t: any, i: number) => (
                    <tr key={t.tenant_id} style={{ borderBottom: i < tenants.length - 1 ? '1px solid var(--ds-border)' : 'none', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                      <td style={{ padding: '0.625rem 1rem', color: 'var(--ds-text-muted)' }}>{t.tenant_id}</td>
                      <td style={{ padding: '0.625rem 1rem', fontWeight: 600, color: 'var(--ds-text-primary)', whiteSpace: 'nowrap' }}>{t.hospital_name}</td>
                      <td style={{ padding: '0.625rem 1rem', fontFamily: 'monospace', color: 'var(--ds-text-muted)' }}>{t.hospital_code}</td>
                      <td style={{ padding: '0.625rem 1rem' }}>
                        <span style={{ display: 'inline-block', padding: '0.125rem 0.5rem', borderRadius: '0.25rem', fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}>{t.db_platform}</span>
                      </td>
                      <td style={{ padding: '0.625rem 1rem', fontFamily: 'monospace', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{t.partition_name}</td>
                      <td style={{ padding: '0.625rem 1rem' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem', color: t.is_active ? '#34d399' : '#f87171', fontWeight: 600 }}>
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.is_active ? '#34d399' : '#f87171', display: 'inline-block' }} />
                          {t.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td style={{ padding: '0.625rem 1rem', color: 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>
                        {t.onboarded_date ? new Date(t.onboarded_date).toLocaleDateString() : '—'}
                      </td>
                      <td style={{ padding: '0.625rem 1rem', color: t.last_sync_date ? 'var(--ds-text-primary)' : 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>
                        {t.last_sync_date ? new Date(t.last_sync_date).toLocaleString() : 'Never'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* ============ LEGACY ADAPTER CARDS (REMOVING - KEPT FOR REFERENCE) ============ */}
      {false && (
      <div className="ds-animate ds-animate-d1">
        <h3 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
          CDC Adapters • Hospital Data Sources
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
          {adapters.map((adapter, i) => (
            <div key={adapter.id} style={{
              background: 'var(--ds-card-bg)',
              border: `1px solid ${adapter.status === 'connected' ? 'rgba(16,185,129,0.3)' : adapter.status === 'error' ? 'rgba(239,68,68,0.3)' : 'rgba(156,163,175,0.3)'}`,
              borderRadius: '1rem',
              padding: '1rem',
              animationDelay: `${i * 0.05}s`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--ds-text-muted)' }}>{adapter.name}</div>
                  <div style={{ fontSize: '0.625rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{adapter.database_type}</div>
                </div>
                <div style={{
                  width: 10, height: 10, borderRadius: '50%',
                  background: adapter.status === 'connected' ? '#34d399' : adapter.status === 'error' ? '#f87171' : '#9ca3af',
                  boxShadow: `0 0 8px ${adapter.status === 'connected' ? 'rgba(52,211,153,0.5)' : 'rgba(248,113,113,0.5)'}`
                }} />
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>
                Status: <span style={{ color: 'var(--ds-text-primary)', fontWeight: 600, textTransform: 'capitalize' }}>{adapter.status}</span>
              </div>
              <div style={{ fontSize: '0.625rem', color: 'var(--ds-text-muted)', lineHeight: 1.6 }}>
                <div>Latency: {adapter.latency_ms !== null ? `${adapter.latency_ms}ms` : 'N/A'}</div>
                <div>CDC: {adapter.cdc_enabled ? '✓ Enabled' : '✗ Disabled'} {adapter.cdc_trigger_status === 'failed' && '(⚠️ Trigger failed)'}</div>
                <div>Lag: {adapter.cdc_lag_seconds !== null ? `${adapter.cdc_lag_seconds}s` : 'N/A'}</div>
                {adapter.last_captured_change_id && <div>Watermark: {adapter.last_captured_change_id}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
      )}

      {/* Database Connections Health Panel */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '1rem' }}>
        {dbs.map(db => (
          <div key={db.name} style={{
            background: 'var(--ds-card-bg)',
            border: `1px solid ${db.data?.status === 'connected' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            borderRadius: '1rem',
            padding: '1rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--ds-text-muted)' }}>
                <Database style={{ width: 12, height: 12, display: 'inline', marginRight: '0.25rem' }} />
                {db.name}
              </span>
              <div style={{
                width: 10, height: 10, borderRadius: '50%',
                background: db.data?.status === 'connected' ? '#34d399' : '#f87171',
                boxShadow: `0 0 8px ${db.data?.status === 'connected' ? 'rgba(52,211,153,0.5)' : 'rgba(248,113,113,0.5)'}`
              }} />
            </div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ds-text-primary)', marginBottom: '0.5rem', textTransform: 'capitalize' }}>
              {db.data?.engine || 'Unknown'}
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginBottom: '0.25rem' }}>
              Status: {db.data?.status || 'Unknown'}
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
              Latency: {db.data?.latency_ms ?? '—'}ms
              {db.data?.active_connections ? ` · ${db.data.active_connections}/${db.data.pool_size || '?'} active` : ''}
            </div>
          </div>
        ))}
      </div>

      {/* Metric Cards */}
      <div className="ds-animate ds-animate-d3" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>

        {/* CDC Pipeline — Queue Depth (real from cdc_inbox) */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: `1px solid ${cdcAvailable ? 'rgba(99,102,241,0.3)' : 'var(--ds-card-border)'}`,
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>CDC Queue Depth</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>
            {cdcAvailable ? (cdcMetrics.queue_depth ?? 'N/A') : 'N/A'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            {cdcAvailable
              ? `${cdcMetrics.dead_letter_count ?? 0} dead-letter · ${cdcMetrics.active_sources ?? 0} active sources`
              : 'CDC tables not yet deployed'}
          </div>
        </div>

        {/* Live Throughput (real from cdc_inbox — rows processed per sec) */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>CDC Throughput</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>
            {throughput !== null ? throughput.toFixed(1) : 'N/A'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            {cdcAvailable
              ? `Records / sec (${cdcMetrics.throughput_per_min ?? 0}/min)`
              : 'CDC tables not yet deployed'}
          </div>
        </div>

        {/* DB Adapters Connected */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>DB Adapters Online</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: workersReady === workersTotal ? '#34d399' : '#f59e0b', marginBottom: '0.25rem' }}>
            {workersReady} / {workersTotal}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            {workersTotal > 0 ? `${Math.round((workersReady / workersTotal) * 100)}% reachable` : 'No adapters configured'}
          </div>
        </div>

        {/* Active DB Services */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>Core DBs Online</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>
            {activeServices}
          </div>
          <div style={{ fontSize: '0.6875rem', color: failedServices > 0 ? '#f87171' : '#34d399' }}>
            {failedServices > 0 ? `${failedServices} unreachable` : 'All core DBs reachable'}
          </div>
        </div>

        {/* Average Latency */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>Avg Latency</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>
            {avgLatency !== null ? `${avgLatency.toFixed(0)}ms` : 'N/A'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            API response time
          </div>
        </div>

        {/* System Uptime */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>System Uptime</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>
            {uptime !== null ? `${Math.floor(uptime / 86400)}d` : 'N/A'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            {uptime !== null ? `${Math.floor((uptime % 86400) / 3600)}h ${Math.floor((uptime % 3600) / 60)}m` : 'Collecting data'}
          </div>
        </div>

        {/* CDC Ingestion Lag — real from cdc_inbox source_ts */}
        {(() => {
          const lagVal = cdcAvailable
            ? (cdcMetrics.ingestion_lag_seconds ?? null)
            : null;
          const lagColor = lagVal === null ? 'var(--ds-card-border)'
            : lagVal < 5   ? 'rgba(16,185,129,0.3)'
            : lagVal < 30  ? 'rgba(245,158,11,0.3)'
            :                'rgba(239,68,68,0.3)';
          const lagText = lagVal === null ? 'CDC tables not yet deployed'
            : lagVal < 5   ? '✓ Healthy'
            : lagVal < 30  ? '⚠ Warning'
            :                '🔴 Critical lag';
          const lagTextColor = lagVal === null ? 'var(--ds-text-muted)'
            : lagVal < 5  ? '#34d399' : lagVal < 30 ? '#f59e0b' : '#f87171';
          return (
            <div style={{ background: 'var(--ds-card-bg)', border: `1px solid ${lagColor}`, borderRadius: '1rem', padding: '1.25rem', boxShadow: 'var(--ds-card-shadow)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>CDC Ingestion Lag</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>
                {lagVal !== null ? `${lagVal.toFixed(1)}s` : 'N/A'}
              </div>
              <div style={{ fontSize: '0.6875rem', color: lagTextColor }}>{lagText}</div>
            </div>
          );
        })()}

        {/* CDC Error Rate — real from dead-letter vs done ratio */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>CDC Error Rate</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: cdcAvailable && (cdcMetrics.error_rate ?? 0) > 0.05 ? '#f87171' : '#34d399', marginBottom: '0.25rem' }}>
            {cdcAvailable && cdcMetrics.error_rate != null
              ? `${(cdcMetrics.error_rate * 100).toFixed(2)}%`
              : 'N/A'}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            {cdcAvailable ? 'DLQ ratio over last hour' : 'CDC tables not yet deployed'}
          </div>
        </div>

        {/* Failed Adapters / Sync Errors */}
        <div style={{
          background: 'var(--ds-card-bg)',
          border: `1px solid ${failedAdapters > 0 ? 'rgba(239,68,68,0.3)' : 'rgba(16,185,129,0.3)'}`,
          borderRadius: '1rem',
          padding: '1.25rem',
          boxShadow: 'var(--ds-card-shadow)',
        }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>Failed Adapters</div>
          <div style={{ fontSize: '2rem', fontWeight: 800, color: failedAdapters > 0 ? '#f87171' : '#34d399', marginBottom: '0.25rem' }}>
            {failedAdapters}
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
            {failed24h !== null ? `${failed24h} errors (24h)` : 'No error data'}
          </div>
        </div>

      </div>

      {/* Performance Trends Section */}
      {(latencySeries.length > 0 || throughputSeries.length > 0 || cdcCaptureSeries.length > 0) && (
        <div className="ds-animate ds-animate-d4" style={{ marginTop: '2rem' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            marginBottom: '1.5rem',
            fontSize: '1rem',
            fontWeight: 700,
            color: 'var(--ds-text-primary)',
          }}>
            <TrendingUp style={{ width: 18, height: 18 }} />
            Performance Trends (Real-time Data)
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(500px, 1fr))', gap: '1.5rem' }}>

            {/* Latency Trend Chart */}
            {latencySeries.length > 0 && (
              <div style={{
                background: 'var(--ds-card-bg)',
                border: '1px solid var(--ds-card-border)',
                borderRadius: '1rem',
                padding: '1.25rem',
                boxShadow: 'var(--ds-card-shadow)',
              }}>
                <h3 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                  API Latency Trend (Last {latencySeries.length} readings)
                </h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={latencySeries} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                    <XAxis
                      dataKey="timestamp"
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                      label={{ value: 'Latency (ms)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--ds-surface-2)',
                        border: '1px solid var(--ds-border)',
                        borderRadius: '0.75rem',
                        fontSize: '0.75rem',
                      }}
                      cursor={{ stroke: 'var(--ds-border)' }}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#60a5fa"
                      strokeWidth={2}
                      dot={false}
                      name="Latency (ms)"
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Throughput Trend Chart */}
            {throughputSeries.length > 0 && (
              <div style={{
                background: 'var(--ds-card-bg)',
                border: '1px solid var(--ds-card-border)',
                borderRadius: '1rem',
                padding: '1.25rem',
                boxShadow: 'var(--ds-card-shadow)',
              }}>
                <h3 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                  Throughput Trend (Last {throughputSeries.length} readings)
                </h3>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={throughputSeries} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                    <defs>
                      <linearGradient id="colorThroughput" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#34d399" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                    <XAxis
                      dataKey="timestamp"
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                      label={{ value: 'Records/sec', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--ds-surface-2)',
                        border: '1px solid var(--ds-border)',
                        borderRadius: '0.75rem',
                        fontSize: '0.75rem',
                      }}
                      cursor={{ stroke: 'var(--ds-border)' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="#34d399"
                      strokeWidth={2}
                      fill="url(#colorThroughput)"
                      name="Records/sec"
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* CDC Capture Rate Trend */}
            {cdcCaptureSeries.length > 0 && (
              <div style={{
                background: 'var(--ds-card-bg)',
                border: '1px solid var(--ds-card-border)',
                borderRadius: '1rem',
                padding: '1.25rem',
                boxShadow: 'var(--ds-card-shadow)',
              }}>
                <h3 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                  CDC Capture Rate Trend (Last {cdcCaptureSeries.length} readings)
                </h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={cdcCaptureSeries} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                    <XAxis
                      dataKey="timestamp"
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      domain={[0, 100]}
                      axisLine={false}
                      tickLine={false}
                      label={{ value: 'Capture Rate (%)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--ds-surface-2)',
                        border: '1px solid var(--ds-border)',
                        borderRadius: '0.75rem',
                        fontSize: '0.75rem',
                      }}
                      cursor={{ stroke: 'var(--ds-border)' }}
                      formatter={(value) => `${value}%`}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke={cdcCaptureStroke}
                      strokeWidth={2}
                      dot={false}
                      name="Capture Rate (%)"
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* CDC Lag Trend Chart */}
            {cdcLagSeries.length > 0 && (
              <div style={{
                background: 'var(--ds-card-bg)',
                border: '1px solid var(--ds-card-border)',
                borderRadius: '1rem',
                padding: '1.25rem',
                boxShadow: 'var(--ds-card-shadow)',
              }}>
                <h3 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                  CDC Ingestion Lag (Last {cdcLagSeries.length} readings)
                </h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={cdcLagSeries} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                    <XAxis
                      dataKey="timestamp"
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                      label={{ value: 'Lag (seconds)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--ds-surface-2)',
                        border: '1px solid var(--ds-border)',
                        borderRadius: '0.75rem',
                        fontSize: '0.75rem',
                      }}
                      cursor={{ stroke: 'var(--ds-border)' }}
                      formatter={(value) => `${value}s`}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke={cdcLagSeries[cdcLagSeries.length - 1]?.value > 30 ? '#f87171' : '#f59e0b'}
                      strokeWidth={2}
                      dot={false}
                      name="Lag (seconds)"
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* ETL Processing Time Trend */}
            {etlTimeSeries.length > 0 && (
              <div style={{
                background: 'var(--ds-card-bg)',
                border: '1px solid var(--ds-card-border)',
                borderRadius: '1rem',
                padding: '1.25rem',
                boxShadow: 'var(--ds-card-shadow)',
              }}>
                <h3 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                  ETL Transform Time (Last {etlTimeSeries.length} readings)
                </h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={etlTimeSeries} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                    <XAxis
                      dataKey="timestamp"
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }}
                      axisLine={false}
                      tickLine={false}
                      label={{ value: 'Time (ms)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--ds-surface-2)',
                        border: '1px solid var(--ds-border)',
                        borderRadius: '0.75rem',
                        fontSize: '0.75rem',
                      }}
                      cursor={{ stroke: 'var(--ds-border)' }}
                      formatter={(value) => `${value}ms`}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#8b5cf6"
                      strokeWidth={2}
                      dot={false}
                      name="Transform Time (ms)"
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

          </div>
        </div>
      )}

      {/* System Insights & Alerts — Intelligent Analysis Layer */}
      <SystemInsights
        latencySeries={latencySeries}
        throughputSeries={throughputSeries}
        cdcLagSeries={cdcLagSeries}
        cdcCaptureSeries={cdcCaptureSeries}
        etlTimeSeries={etlTimeSeries}
        adapters={adapters}
        onRefetch={refetchAll}
        isLoading={isLoading}
      />

      {/* Last refresh timestamp */}
      <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', textAlign: 'right', marginTop: '1.5rem' }}>
        Last refreshed: {lastRefresh.toLocaleTimeString()} • Charts update with API polling • Insights updated in real-time
      </div>

    </div>
  );
};

/**
 * Wrap dashboard with AuthGuard to prevent rendering before authentication ready
 * This prevents 403/401 errors that cause blank screen
 */
const AuthenticatedAdminDashboard: React.FC = () => (
  <AuthGuard>
    <AdminDashboard />
  </AuthGuard>
);

export default AuthenticatedAdminDashboard;

