/** SystemHealthPanel — theme-aware system health metrics using ds-* tokens. */
import React from 'react';
import { Activity, Gauge, AlertTriangle, Zap, RefreshCw } from 'lucide-react';
import type { SystemMetrics } from '../../../shared/types';

interface Props { metrics: SystemMetrics | null; loading: boolean }

function getLagStatus(s: number): 'green' | 'yellow' | 'red' { return s <= 10 ? 'green' : s <= 60 ? 'yellow' : 'red'; }
function getErrorRateStatus(r: number): 'green' | 'yellow' | 'red' { return r <= 0.02 ? 'green' : r <= 0.05 ? 'yellow' : 'red'; }
function fmtLag(s: number | null | undefined): string {
  if (s == null) return '--'; if (s < 1) return '<1s'; if (s < 60) return `${Math.round(s)}s`;
  if (s < 3600) return `${Math.round(s / 60)}m`; return `${(s / 3600).toFixed(1)}h`;
}

const STATUS_CSS: Record<string, { dot: string; bg: string; text: string; border: string }> = {
  green:  { dot: '#34d399', bg: 'var(--ds-status-active-bg)',  text: 'var(--ds-status-active-text)',  border: 'rgba(16,185,129,0.25)'  },
  yellow: { dot: '#fbbf24', bg: 'var(--ds-status-pending-bg)', text: 'var(--ds-status-pending-text)', border: 'rgba(245,158,11,0.25)'  },
  red:    { dot: '#f87171', bg: 'var(--ds-status-error-bg)',   text: 'var(--ds-status-error-text)',   border: 'rgba(239,68,68,0.25)'   },
};

const SystemHealthPanel: React.FC<Props> = React.memo(({ metrics, loading }) => {
  if (loading) {
    return (
      <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
          <div style={{ width: 110, height: 16, background: 'rgba(255,255,255,0.05)', borderRadius: '0.375rem' }} />
        </div>
        {[1, 2, 3, 4].map(i => <div key={i} style={{ height: 56, background: 'rgba(255,255,255,0.03)', borderRadius: '0.75rem', marginBottom: '0.625rem', animation: 'ds-pulse 1.8s ease-in-out infinite' }} />)}
      </div>
    );
  }

  const replicationLagS  = metrics?.ingestion_lag_seconds ?? 0;
  const errorRate        = metrics?.error_rate ?? 0;
  const apiLatencyMs     = metrics?.avg_latency ?? 0;
  const cdcActive        = (metrics?.cdc_operations ?? 0) > 0;
  const throughput       = metrics?.throughput_per_min != null ? metrics.throughput_per_min / 60 : null;

  const items = [
    { label: 'Replication Lag',   value: fmtLag(replicationLagS),         status: getLagStatus(replicationLagS),    icon: <RefreshCw style={{ width: 15, height: 15 }} />, detail: 'CDC stream lag to FHIR DB' },
    { label: 'API Error Rate',    value: `${(errorRate * 100).toFixed(2)}%`, status: getErrorRateStatus(errorRate),  icon: <AlertTriangle style={{ width: 15, height: 15 }} />, detail: `${(errorRate * 100).toFixed(2)}% of requests failed` },
    { label: 'API Latency',       value: apiLatencyMs > 0 ? `${Math.round(apiLatencyMs)}ms` : '--', status: apiLatencyMs <= 200 ? 'green' : apiLatencyMs <= 500 ? 'yellow' : 'red' as any, icon: <Gauge style={{ width: 15, height: 15 }} />, detail: 'Avg response time (p50)' },
    { label: 'CDC Agent',         value: cdcActive ? 'Active' : 'Inactive', status: cdcActive ? 'green' : 'red' as any, icon: <Zap style={{ width: 15, height: 15 }} />, detail: 'PostgreSQL WAL listener' },
    ...(throughput != null ? [{ label: 'Throughput', value: `${throughput.toFixed(1)} rec/s`, status: 'green' as const, icon: <Activity style={{ width: 15, height: 15 }} />, detail: 'Real-time sync throughput' }] : []),
  ];

  return (
    <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.25rem' }}>
      <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Activity style={{ width: 14, height: 14, color: '#34d399' }} />System Health
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
        {items.map(item => {
          const s = STATUS_CSS[item.status];
          return (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: s.bg, border: `1px solid ${s.border}`, borderRadius: '0.75rem', padding: '0.75rem' }}>
              <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: s.text }}>
                {item.icon}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{item.label}</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{item.value}</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.6875rem', fontWeight: 700, color: s.text, flexShrink: 0 }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: s.dot }} />
                {item.status === 'green' ? 'Healthy' : item.status === 'yellow' ? 'Warning' : 'Critical'}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

SystemHealthPanel.displayName = 'SystemHealthPanel';
export default SystemHealthPanel;
