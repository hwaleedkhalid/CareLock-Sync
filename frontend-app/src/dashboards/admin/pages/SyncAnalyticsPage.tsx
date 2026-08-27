/**
 * SyncAnalyticsPage.tsx — System Analytics (Sync Operations)
 *
 * All data is fetched from real backend APIs:
 *   GET  /api/v1/sync/status          — live sync state + total_syncs
 *   GET  /api/v1/sync/history?limit=50 — history table + chart source
 *   GET  /api/v1/system/metrics        — throughput, error_rate, queue depth
 *   GET  /api/v1/connector/health      — per-DB connection status (auto-sync trigger)
 *   POST /api/v1/sync/full             — trigger single-tenant full sync
 *   POST /api/v1/sync/multi/full       — trigger full sync across ALL databases
 *   POST /api/v1/sync/multi/incremental — auto-triggered when a DB reconnects
 *
 * RULES:
 *  - No mock/fake data. Missing values display "N/A" or "—".
 *  - All hooks before any conditional return (React rules of hooks).
 *  - Auto-trigger incremental sync when a disconnected DB reconnects.
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  RefreshCw, Play, CheckCircle2, AlertCircle,
  Clock, Database, Zap, Loader2, BarChart3, Wifi, WifiOff,
} from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

import { useApiData } from '../../../shared/hooks';
import { apiClient } from '../../../shared/services/apiClient';
import { useAuth } from '../../../shared/context/AuthContext';
import ErrorBanner from '../../../shared/ui/ErrorBanner';
import type { SystemMetrics } from '../../../shared/types';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Extract total records count from a sync run's stats object */
function extractRecords(stats: Record<string, any> | null | undefined): number {
  if (!stats) return 0;
  // Full sync: { patients, encounters, observations, medications, ... }
  // Incremental: { changes_applied, errors, by_table }
  if (typeof stats.changes_applied === 'number') return stats.changes_applied;
  return ['patients', 'encounters', 'observations', 'observations',
          'medications', 'loaded'].reduce((sum, key) => {
    const v = stats[key];
    return sum + (typeof v === 'number' ? v : 0);
  }, 0);
}

function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return 'N/A';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return iso;
  }
}

function fmtShortTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ── Sub-components ─────────────────────────────────────────────────────────────

const card = (extra?: React.CSSProperties): React.CSSProperties => ({
  background: 'var(--ds-card-bg)',
  border: '1px solid var(--ds-card-border)',
  borderRadius: '1rem',
  boxShadow: 'var(--ds-card-shadow)',
  ...extra,
});

const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const colors: Record<string, { bg: string; text: string; border: string }> = {
    completed:  { bg: 'rgba(16,185,129,0.12)',  text: '#34d399', border: 'rgba(16,185,129,0.3)' },
    running:    { bg: 'rgba(59,130,246,0.12)',   text: '#60a5fa', border: 'rgba(59,130,246,0.3)' },
    queued:     { bg: 'rgba(245,158,11,0.12)',   text: '#fbbf24', border: 'rgba(245,158,11,0.3)' },
    failed:     { bg: 'rgba(239,68,68,0.12)',    text: '#f87171', border: 'rgba(239,68,68,0.3)'  },
    idle:       { bg: 'rgba(156,163,175,0.12)',  text: '#9ca3af', border: 'rgba(156,163,175,0.3)' },
  };
  const c = colors[status] ?? colors.idle;
  return (
    <span style={{
      fontSize: '0.6875rem', fontWeight: 700, textTransform: 'capitalize',
      padding: '0.2rem 0.6rem', borderRadius: '2rem',
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
    }}>
      {status}
    </span>
  );
};

const ChartTip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--ds-surface-2)', border: '1px solid var(--ds-border)', borderRadius: '0.75rem', padding: '0.625rem 0.875rem', fontSize: '0.75rem', boxShadow: '0 8px 24px rgba(0,0,0,0.35)' }}>
      <p style={{ fontWeight: 700, color: 'var(--ds-text-primary)', margin: '0 0 0.375rem' }}>{label}</p>
      {payload.map((e: any, i: number) => (
        <div key={i} style={{ display: 'flex', gap: '0.375rem', alignItems: 'center' }}>
          <div style={{ width: 8, height: 8, borderRadius: '2px', background: e.color }} />
          <span style={{ color: 'var(--ds-text-muted)' }}>{e.name}:</span>
          <span style={{ color: 'var(--ds-text-primary)', fontWeight: 700 }}>{e.value}</span>
        </div>
      ))}
    </div>
  );
};

const axisProps = { fontSize: 10, fill: 'var(--ds-text-muted)' } as any;

// ── Main Component ─────────────────────────────────────────────────────────────

const SyncAnalyticsPage: React.FC = () => {
  const { user } = useAuth();

  // ── API data ────────────────────────────────────────────────────────────────
  // All hooks declared unconditionally at the top (rules of hooks)
  const [autoRefresh, setAutoRefresh] = useState(true);

  const syncStatusRaw   = useApiData<any>('/api/v1/sync/status',         { pollInterval: 15000 });
  const historyRaw      = useApiData<any>('/api/v1/sync/history?limit=50');
  const metricsRaw      = useApiData<SystemMetrics>('/api/v1/system/metrics', { pollInterval: 30000 });
  const connectorRaw    = useApiData<any>('/api/v1/connector/health',     { pollInterval: 30000 });

  // ── UI state ────────────────────────────────────────────────────────────────
  const [triggering, setTriggering] = useState<'full' | 'multi' | null>(null);
  const [triggerMsg, setTriggerMsg] = useState<{ ok: boolean; msg: string; warn?: boolean } | null>(null);
  const [autoSyncNote, setAutoSyncNote] = useState<string | null>(null);

  // ── Refs for auto-sync detection ────────────────────────────────────────────
  const prevDbStatusRef = useRef<Record<string, boolean>>({});
  const autoSyncLockRef = useRef(false); // prevents rapid re-triggers (60s cooldown)

  // ── Derived values (memoised — must be declared before any early return) ────
  const historyItems: any[] = useMemo(
    () => historyRaw.data?.history ?? [],
    [historyRaw.data],
  );

  const isSyncing = syncStatusRaw.data?.is_syncing ?? false;
  const syncProgress = syncStatusRaw.data?.progress ?? 0;
  const syncStep = syncStatusRaw.data?.current_step ?? null;

  // KPI: Total Syncs
  const kpiTotalSyncs: number | null = syncStatusRaw.data?.total_syncs ?? null;

  // KPI: Average Duration (from history)
  const kpiAvgDuration: number | null = useMemo(() => {
    const valid = historyItems.filter(h => typeof h.duration_s === 'number');
    if (valid.length === 0) return null;
    const sum = valid.reduce((acc: number, h: any) => acc + h.duration_s, 0);
    return Math.round((sum / valid.length) * 100) / 100;
  }, [historyItems]);

  // KPI: Throughput from CDC metrics
  const kpiThroughput: number | null = metricsRaw.data?.throughput_per_min ?? null;

  // KPI: Error Rate from CDC metrics
  const kpiErrorRate: number | null = metricsRaw.data?.error_rate ?? null;

  // Chart: Sync Trends (records processed per completed run, chronological)
  const syncTrendsData = useMemo(() => {
    return historyItems
      .filter((h: any) => h.status === 'completed' && h.completed_at)
      .slice()
      .reverse()
      .slice(-20) // last 20 completed runs
      .map((h: any) => ({
        time:    fmtShortTime(h.completed_at),
        records: extractRecords(h.stats),
        type:    h.type === 'full' ? 'Full' : 'Incr',
      }));
  }, [historyItems]);

  // Chart: Performance Over Time (duration per run, chronological)
  const perfData = useMemo(() => {
    return historyItems
      .filter((h: any) => typeof h.duration_s === 'number' && h.started_at)
      .slice()
      .reverse()
      .slice(-20) // last 20 runs
      .map((h: any) => ({
        time:     fmtShortTime(h.started_at),
        duration: Math.round(h.duration_s * 10) / 10,
        status:   h.status,
      }));
  }, [historyItems]);

  // Combined error / loading
  const isLoading = syncStatusRaw.loading || historyRaw.loading;
  const pageError = syncStatusRaw.error ?? historyRaw.error ?? null;

  // ── Auto-refresh: faster polling when a sync is active ──────────────────────
  useEffect(() => {
    if (!autoRefresh || !isSyncing) return;
    // When a sync is active, re-poll status + history every 4 s
    const id = setInterval(() => {
      syncStatusRaw.refetch().catch(() => {});
      historyRaw.refetch().catch(() => {});
    }, 4000);
    return () => clearInterval(id);
  }, [autoRefresh, isSyncing]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Auto-sync: trigger incremental when a DB reconnects ────────────────────
  useEffect(() => {
    const databases: any[] = connectorRaw.data?.databases ?? [];
    if (databases.length === 0) return;

    // Build current snapshot: { dbName → connected }
    const current: Record<string, boolean> = {};
    databases.forEach((db: any) => { current[db.name] = !!db.connected; });

    const prev = prevDbStatusRef.current;
    if (Object.keys(prev).length === 0) {
      // First reading — just record state, don't trigger
      prevDbStatusRef.current = current;
      return;
    }

    // Find DBs that transitioned disconnected → connected
    const newlyOnline = Object.entries(current)
      .filter(([name, connected]) => connected && prev[name] === false)
      .map(([name]) => name);

    if (newlyOnline.length > 0 && !autoSyncLockRef.current) {
      autoSyncLockRef.current = true; // lock for 60 s to prevent storm
      const note = `Auto-sync triggered — ${newlyOnline.join(', ')} came online`;
      setAutoSyncNote(note);

      apiClient
        .post<any>('/api/v1/sync/multi/incremental', {})
        .then(() => {
          syncStatusRaw.refetch().catch(() => {});
          historyRaw.refetch().catch(() => {});
        })
        .catch(() => {})
        .finally(() => {
          setTimeout(() => {
            autoSyncLockRef.current = false;
          }, 60_000);
        });
    }

    prevDbStatusRef.current = current;
  }, [connectorRaw.data]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-dismiss trigger message after 8 s
  useEffect(() => {
    if (!triggerMsg) return;
    const id = setTimeout(() => setTriggerMsg(null), 8000);
    return () => clearTimeout(id);
  }, [triggerMsg]);

  // Auto-dismiss auto-sync note after 8 s
  useEffect(() => {
    if (!autoSyncNote) return;
    const id = setTimeout(() => setAutoSyncNote(null), 8000);
    return () => clearTimeout(id);
  }, [autoSyncNote]);

  // ── Actions ─────────────────────────────────────────────────────────────────
  const refetchAll = useCallback(async () => {
    await Promise.allSettled([
      syncStatusRaw.refetch(),
      historyRaw.refetch(),
      metricsRaw.refetch(),
      connectorRaw.refetch(),
    ]);
  }, [syncStatusRaw, historyRaw, metricsRaw, connectorRaw]);

  /**
   * Extract the most informative error string from an ApiError.
   * apiClient normalises Axios errors → ApiError objects whose .userMessage
   * already contains the FastAPI detail string for 4xx/5xx responses.
   * We do NOT read err.response (that field lives on the raw Axios error,
   * not on ApiError).
   */
  const extractErrMsg = useCallback((err: any, fallback: string): string => {
    // ApiError.userMessage already has the FastAPI detail for known HTTP codes
    if (err?.userMessage && err.userMessage !== 'An error occurred. Please try again.') {
      return String(err.userMessage).slice(0, 300);
    }
    // Additional fallback via originalError in case the handler returned the generic message
    const rawDetail = err?.originalError?.response?.data?.detail;
    if (rawDetail) return String(rawDetail).slice(0, 300);
    return err?.message ?? fallback;
  }, []);

  const handleTriggerFull = useCallback(async () => {
    if (triggering) return;
    setTriggering('full');
    setTriggerMsg(null);
    try {
      // tenant_id: admin token has null tenant_id → default to 1 (postgres_hospital)
      // mode: 'full' forces a full reload regardless of prior run history
      const tenantId = user?.tenant_id ?? 1;
      const res = await apiClient.post<any>(
        '/api/v1/sync/full',
        { tenant_id: tenantId, mode: 'full' },
        { timeout: 30_000 },   // advisory lock + DB insert can be slow
      );
      setTriggerMsg({
        ok:  true,
        msg: res.message ?? `Full sync queued (sync_id: ${res.sync_id ?? '—'})`,
      });
      // Give the background task 1.5 s to update sync_runs before polling
      setTimeout(() => {
        syncStatusRaw.refetch().catch(() => {});
        historyRaw.refetch().catch(() => {});
      }, 1500);
    } catch (err: any) {
      // 409 = already running  →  show as a warning, not an error
      const is409 = err?.status === 409;
      setTriggerMsg({
        ok:  false,
        msg: extractErrMsg(err, 'Sync trigger failed — check backend logs'),
        ...(is409 ? { warn: true } : {}),
      });
    } finally {
      setTriggering(null);
    }
  }, [triggering, user, syncStatusRaw, historyRaw, extractErrMsg]);

  const handleTriggerMulti = useCallback(async () => {
    if (triggering) return;
    setTriggering('multi');
    setTriggerMsg(null);
    try {
      // MultiSyncRequest only accepts { limit? } — no tenant_id, it comes from sync_config.json
      const res = await apiClient.post<any>(
        '/api/v1/sync/multi/full',
        {},
        { timeout: 30_000 },
      );
      const srcCount = res.sources?.length ?? '?';
      setTriggerMsg({
        ok:  true,
        msg: res.message ?? `Multi-DB full sync queued across ${srcCount} source(s)`,
      });
      setTimeout(() => {
        syncStatusRaw.refetch().catch(() => {});
        historyRaw.refetch().catch(() => {});
      }, 1500);
    } catch (err: any) {
      const is409 = err?.status === 409;
      setTriggerMsg({
        ok:  false,
        msg: extractErrMsg(err, 'Multi-sync trigger failed — check backend logs'),
        ...(is409 ? { warn: true } : {}),
      });
    } finally {
      setTriggering(null);
    }
  }, [triggering, syncStatusRaw, historyRaw, extractErrMsg]);

  // ── Render ──────────────────────────────────────────────────────────────────

  const kpis = [
    {
      label: 'Total Syncs',
      value: kpiTotalSyncs !== null ? kpiTotalSyncs.toLocaleString() : 'N/A',
      icon: <Database style={{ width: 16, height: 16, color: '#34d399' }} />,
      sub: 'All completed sync runs',
      grad: 'linear-gradient(135deg,rgba(16,185,129,0.15),rgba(16,185,129,0.03))',
      accent: '#34d399',
    },
    {
      label: 'Avg Duration',
      value: fmtDuration(kpiAvgDuration),
      icon: <Clock style={{ width: 16, height: 16, color: '#60a5fa' }} />,
      sub: kpiAvgDuration !== null ? `Across ${historyItems.filter(h => h.duration_s != null).length} runs` : 'No completed runs yet',
      grad: 'linear-gradient(135deg,rgba(59,130,246,0.15),rgba(59,130,246,0.03))',
      accent: '#60a5fa',
    },
    {
      label: 'CDC Throughput',
      value: kpiThroughput !== null ? `${kpiThroughput.toLocaleString()}/min` : 'N/A',
      icon: <Zap style={{ width: 16, height: 16, color: '#fbbf24' }} />,
      sub: metricsRaw.data?.available ? 'Rows processed (last 60 s)' : 'CDC pipeline idle',
      grad: 'linear-gradient(135deg,rgba(245,158,11,0.15),rgba(245,158,11,0.03))',
      accent: '#fbbf24',
    },
    {
      label: 'Error Rate',
      value: kpiErrorRate !== null ? `${(kpiErrorRate * 100).toFixed(2)}%` : 'N/A',
      icon: <AlertCircle style={{ width: 16, height: 16, color: kpiErrorRate === 0 ? '#34d399' : '#f87171' }} />,
      sub: kpiErrorRate === 0 ? '✓ No errors in rolling window' : 'DLQ / (DLQ + done) last hour',
      grad: kpiErrorRate === 0
        ? 'linear-gradient(135deg,rgba(16,185,129,0.15),rgba(16,185,129,0.03))'
        : 'linear-gradient(135deg,rgba(239,68,68,0.15),rgba(239,68,68,0.03))',
      accent: kpiErrorRate === 0 ? '#34d399' : '#f87171',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1200, margin: '0 auto' }}>

      {/* ── Header ── */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 style={{ width: 22, height: 22, color: '#60a5fa' }} />
            System Analytics
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
            Real-time sync performance · Multi-database pipeline · CDC health
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          {/* Auto-refresh toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)', cursor: 'pointer', userSelect: 'none' }}>
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
              style={{ accentColor: '#7c3aed', width: 14, height: 14 }}
            />
            Auto-refresh
          </label>

          {/* Manual refresh */}
          <button
            onClick={refetchAll}
            disabled={isLoading}
            className="ds-btn"
            style={{ fontSize: '0.8125rem', opacity: isLoading ? 0.6 : 1 }}
          >
            <RefreshCw style={{ width: 13, height: 13, ...(isLoading ? { animation: 'spin 0.8s linear infinite' } : {}) }} />
            Refresh
          </button>

          {/* Trigger Full Sync (single tenant) */}
          <button
            onClick={handleTriggerFull}
            disabled={!!triggering || isSyncing}
            className="ds-btn"
            title="Trigger full sync for tenant 1"
            style={{ fontSize: '0.8125rem', opacity: (triggering || isSyncing) ? 0.6 : 1 }}
          >
            {triggering === 'full'
              ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 0.8s linear infinite' }} />
              : <Play style={{ width: 13, height: 13 }} />}
            Trigger Sync
          </button>

          {/* Trigger Multi-DB Sync */}
          <button
            onClick={handleTriggerMulti}
            disabled={!!triggering || isSyncing}
            className="ds-btn ds-btn-primary"
            title="Trigger full sync across all configured database sources"
            style={{ fontSize: '0.8125rem', opacity: (triggering || isSyncing) ? 0.6 : 1 }}
          >
            {triggering === 'multi'
              ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 0.8s linear infinite' }} />
              : <Database style={{ width: 13, height: 13 }} />}
            Sync All DBs
          </button>
        </div>
      </div>

      {/* ── Error banner ── */}
      {pageError && (
        <ErrorBanner
          message="Failed to load analytics data"
          detail={pageError.userMessage || pageError.message || 'API request failed'}
          onRetry={refetchAll}
        />
      )}

      {/* ── Trigger result ── */}
      {triggerMsg && (() => {
        // Three visual states: success (green), warning/conflict (amber), error (red)
        const isWarn  = !triggerMsg.ok && triggerMsg.warn;
        const isOk    = triggerMsg.ok;
        const bg      = isOk    ? 'rgba(16,185,129,0.10)'
                      : isWarn  ? 'rgba(245,158,11,0.10)'
                                : 'rgba(239,68,68,0.10)';
        const border  = isOk    ? 'rgba(16,185,129,0.3)'
                      : isWarn  ? 'rgba(245,158,11,0.3)'
                                : 'rgba(239,68,68,0.3)';
        const color   = isOk    ? '#34d399'
                      : isWarn  ? '#fbbf24'
                                : '#f87171';
        const Icon    = isOk    ? CheckCircle2
                      : isWarn  ? AlertCircle
                                : AlertCircle;
        return (
          <div className="ds-animate" style={{
            display: 'flex', alignItems: 'flex-start', gap: '0.625rem',
            padding: '0.75rem 1rem', borderRadius: '0.75rem', fontSize: '0.8125rem',
            background: bg, border: `1px solid ${border}`, color,
          }}>
            <Icon style={{ width: 14, height: 14, flexShrink: 0, marginTop: 1 }} />
            <span style={{ lineHeight: 1.5 }}>{triggerMsg.msg}</span>
          </div>
        );
      })()}

      {/* ── Auto-sync notification ── */}
      {autoSyncNote && (
        <div className="ds-animate" style={{
          display: 'flex', alignItems: 'center', gap: '0.625rem',
          padding: '0.75rem 1rem', borderRadius: '0.75rem', fontSize: '0.8125rem',
          background: 'rgba(99,102,241,0.10)', border: '1px solid rgba(99,102,241,0.3)', color: '#818cf8',
        }}>
          <Wifi style={{ width: 14, height: 14, flexShrink: 0 }} />
          {autoSyncNote}
        </div>
      )}

      {/* ── Active sync progress bar ── */}
      {isSyncing && (
        <div className="ds-animate" style={card({ padding: '1rem 1.25rem' })}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.625rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Loader2 style={{ width: 14, height: 14, color: '#60a5fa', animation: 'spin 0.8s linear infinite' }} />
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                Sync in progress
              </span>
              {syncStep && (
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
                  — {syncStep}
                </span>
              )}
            </div>
            <span style={{ fontSize: '0.875rem', fontWeight: 800, color: '#60a5fa' }}>
              {syncProgress}%
            </span>
          </div>
          <div style={{ height: 6, background: 'var(--ds-table-head-bg)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: `${syncProgress}%`,
              background: 'linear-gradient(90deg,#3b82f6,#60a5fa)',
              borderRadius: 4,
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>
      )}

      {/* ── KPI cards ── */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: '1rem' }}>
        {kpis.map(k => (
          <div
            key={k.label}
            style={{
              background: k.grad,
              border: '1px solid var(--ds-card-border)',
              borderRadius: '1rem',
              boxShadow: 'var(--ds-card-shadow)',
              padding: '1.125rem',
              transition: 'border-color 0.2s, transform 0.2s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.borderColor = k.accent + '60';
              (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-border)';
              (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {k.label}
              </span>
              {k.icon}
            </div>
            <p style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>
              {k.value}
            </p>
            <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', margin: '0.375rem 0 0' }}>
              {k.sub}
            </p>
          </div>
        ))}
      </div>

      {/* ── Charts ── */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(420px,1fr))', gap: '1rem' }}>

        {/* Sync Trends — records per completed run */}
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 0.25rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
            Sync Trends — Records Processed
          </h2>
          <p style={{ margin: '0 0 1rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
            Records loaded per completed sync run (last 20)
          </p>
          {syncTrendsData.length === 0 ? (
            <div style={{ height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ds-text-muted)', fontSize: '0.8125rem' }}>
              No completed sync runs yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={syncTrendsData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                <XAxis dataKey="time" tick={axisProps} axisLine={false} tickLine={false} />
                <YAxis tick={axisProps} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar dataKey="records" name="Records" fill="#3b82f6" radius={[3, 3, 0, 0]} maxBarSize={32} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Performance — duration per run */}
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 0.25rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
            Performance Over Time
          </h2>
          <p style={{ margin: '0 0 1rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
            Sync duration in seconds per run (last 20)
          </p>
          {perfData.length === 0 ? (
            <div style={{ height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ds-text-muted)', fontSize: '0.8125rem' }}>
              No performance data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={perfData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
                <XAxis dataKey="time" tick={axisProps} axisLine={false} tickLine={false} />
                <YAxis tick={axisProps} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTip />} cursor={{ stroke: 'var(--ds-border)' }} />
                <Line type="monotone" dataKey="duration" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3, fill: '#8b5cf6' }} name="Duration (s)" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* ── Sync History Table ── */}
      <div className="ds-animate ds-animate-d3" style={card({ overflow: 'hidden' })}>
        <div style={{ padding: '1.125rem 1.25rem', borderBottom: '1px solid var(--ds-card-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
              Sync History
            </h2>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
              {historyItems.length > 0 ? `Last ${historyItems.length} sync runs` : 'No history available'}
            </p>
          </div>
          {historyRaw.loading && (
            <Loader2 style={{ width: 14, height: 14, color: 'var(--ds-text-muted)', animation: 'spin 0.8s linear infinite' }} />
          )}
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
            <thead>
              <tr style={{ background: 'var(--ds-table-head-bg)' }}>
                {['Type', 'Status', 'Started', 'Completed', 'Duration', 'Records', 'Error'].map(h => (
                  <th key={h} style={{
                    padding: '0.625rem 1rem', textAlign: 'left',
                    fontWeight: 700, fontSize: '0.6875rem',
                    textTransform: 'uppercase', letterSpacing: '0.04em',
                    color: 'var(--ds-text-muted)', whiteSpace: 'nowrap',
                    borderBottom: '1px solid var(--ds-table-border)',
                  }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {historyItems.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)' }}>
                    {historyRaw.loading ? 'Loading sync history…' : 'No sync history available'}
                  </td>
                </tr>
              ) : (
                historyItems.map((run: any, i: number) => {
                  const records = extractRecords(run.stats);
                  return (
                    <tr
                      key={run.sync_id}
                      style={{
                        borderBottom: i < historyItems.length - 1 ? '1px solid var(--ds-table-border)' : 'none',
                        background: i % 2 === 1 ? 'rgba(255,255,255,0.01)' : 'transparent',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = 'var(--ds-table-head-bg)'; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = i % 2 === 1 ? 'rgba(255,255,255,0.01)' : 'transparent'; }}
                    >
                      {/* Type */}
                      <td style={{ padding: '0.625rem 1rem', whiteSpace: 'nowrap' }}>
                        <span style={{
                          display: 'inline-block', padding: '0.15rem 0.5rem', borderRadius: '0.375rem',
                          fontSize: '0.6875rem', fontWeight: 700, textTransform: 'capitalize',
                          background: run.type === 'full' ? 'rgba(99,102,241,0.15)' : 'rgba(245,158,11,0.12)',
                          color: run.type === 'full' ? '#818cf8' : '#fbbf24',
                        }}>
                          {run.type ?? '—'}
                        </span>
                      </td>

                      {/* Status */}
                      <td style={{ padding: '0.625rem 1rem' }}>
                        <StatusBadge status={run.status ?? 'unknown'} />
                      </td>

                      {/* Started */}
                      <td style={{ padding: '0.625rem 1rem', color: 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>
                        {fmtTime(run.started_at)}
                      </td>

                      {/* Completed */}
                      <td style={{ padding: '0.625rem 1rem', color: 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>
                        {fmtTime(run.completed_at)}
                      </td>

                      {/* Duration */}
                      <td style={{ padding: '0.625rem 1rem', color: 'var(--ds-text-primary)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                        {fmtDuration(run.duration_s)}
                      </td>

                      {/* Records */}
                      <td style={{ padding: '0.625rem 1rem', color: 'var(--ds-text-primary)', fontWeight: 600 }}>
                        {records > 0 ? records.toLocaleString() : '—'}
                      </td>

                      {/* Error */}
                      <td style={{ padding: '0.625rem 1rem', maxWidth: 260 }}>
                        {run.error ? (
                          <span style={{ color: '#f87171', fontSize: '0.6875rem', fontStyle: 'italic' }} title={run.error}>
                            {run.error.length > 60 ? run.error.slice(0, 57) + '…' : run.error}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--ds-text-muted)' }}>—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── DB Connection Status (for auto-sync visibility) ── */}
      {connectorRaw.data?.databases && (
        <div className="ds-animate ds-animate-d4" style={card({ padding: '1.125rem 1.25rem' })}>
          <h2 style={{ margin: '0 0 0.875rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
            Database Connection Status
            <span style={{ marginLeft: '0.5rem', fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)' }}>
              — auto-sync triggers when a DB comes online
            </span>
          </h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            {connectorRaw.data.databases.map((db: any) => (
              <div key={db.name} style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.5rem 0.875rem', borderRadius: '2rem', fontSize: '0.75rem', fontWeight: 600,
                background: db.connected ? 'rgba(16,185,129,0.10)' : 'rgba(239,68,68,0.08)',
                border: `1px solid ${db.connected ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.2)'}`,
                color: db.connected ? '#34d399' : '#f87171',
              }}>
                {db.connected
                  ? <Wifi style={{ width: 11, height: 11, flexShrink: 0 }} />
                  : <WifiOff style={{ width: 11, height: 11, flexShrink: 0 }} />}
                {db.name}
                {db.latency_ms != null && (
                  <span style={{ opacity: 0.7, fontWeight: 400 }}>{Math.round(db.latency_ms)}ms</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};

export default SyncAnalyticsPage;
