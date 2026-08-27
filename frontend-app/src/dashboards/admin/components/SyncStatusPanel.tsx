/** SyncStatusPanel — theme-aware live sync monitor using ds-* tokens. */
import React from 'react';
import { RefreshCw, Clock, Database, Activity, Loader2, CheckCircle2, AlertTriangle, Zap, Hash } from 'lucide-react';
import type { SyncStatus } from '../../../shared/types';

interface Props { syncStatus: SyncStatus | null; loading: boolean }

function formatSyncTime(iso: string | null): string {
  if (!iso) return 'Never';
  try {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (diff < 1) return 'Just now'; if (diff < 60) return `${diff}m ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

const SyncStatusPanel: React.FC<Props> = React.memo(({ syncStatus, loading }) => {
  if (loading) {
    return (
      <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '1.25rem' }}>
        <div style={{ width: 110, height: 16, background: 'rgba(255,255,255,0.05)', borderRadius: '0.375rem', marginBottom: '1.25rem' }} />
        {[1, 2, 3].map(i => <div key={i} style={{ height: 56, background: 'rgba(255,255,255,0.03)', borderRadius: '0.75rem', marginBottom: '0.625rem', animation: 'ds-pulse 1.8s ease-in-out infinite' }} />)}
      </div>
    );
  }

  const isSyncing = syncStatus?.is_syncing ?? false;
  const status    = syncStatus?.status ?? 'idle';
  const progress  = Math.max(0, Math.min(100, syncStatus?.progress ?? 0));
  const step      = syncStatus?.current_step ?? null;
  const mode      = syncStatus?.mode ?? null;
  const syncId    = syncStatus?.sync_id ?? null;
  const duration  = syncStatus?.duration_s ?? null;
  const lastSyncTime = syncStatus?.last_sync_time ?? null;
  const lastStats    = (syncStatus?.last_sync_stats ?? {}) as Record<string, number>;
  const liveStats    = (syncStatus?.records_processed ?? {}) as Record<string, number>;
  const shownStats   = isSyncing ? liveStats : lastStats;
  const totalSyncs   = syncStatus?.total_syncs ?? 0;
  const lastSyncRecords = Object.values(lastStats).reduce((s, n) => s + Number(n || 0), 0);
  const error = syncStatus?.error ?? null;
  const isStale = syncStatus?.is_stale ?? false;
  const heartbeatAt = syncStatus?.last_heartbeat_at ?? null;
  const staleThresholdMin = syncStatus?.stale_threshold_seconds ? Math.round(syncStatus.stale_threshold_seconds / 60) : 10;

  const pillColor = status === 'failed' ? { bg: 'var(--ds-status-error-bg)', text: 'var(--ds-status-error-text)', border: 'var(--ds-status-error-bg)' }
    : isSyncing ? { bg: 'var(--ds-status-syncing-bg)', text: 'var(--ds-status-syncing-text)', border: 'var(--ds-status-syncing-bg)' }
    : { bg: 'var(--ds-status-active-bg)', text: 'var(--ds-status-active-text)', border: 'var(--ds-status-active-bg)' };

  const itemBox: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--ds-table-head-bg)', border: '1px solid var(--ds-table-border)', borderRadius: '0.75rem', padding: '0.875rem' };
  const iconBox = (active = false): React.CSSProperties => ({ width: 36, height: 36, borderRadius: '0.625rem', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, background: active ? 'rgba(59,130,246,0.20)' : 'rgba(255,255,255,0.05)' });

  return (
    <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.25rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <RefreshCw style={{ width: 14, height: 14, color: '#60a5fa', ...(isSyncing ? { animation: 'spin 0.8s linear infinite' } : {}) }} />
          Sync Status
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.6875rem', fontWeight: 700, padding: '0.25rem 0.625rem', borderRadius: '2rem', background: pillColor.bg, color: pillColor.text, border: `1px solid ${pillColor.border}` }}>
          {status === 'failed' ? <AlertTriangle style={{ width: 11, height: 11 }} /> : isSyncing ? <Loader2 style={{ width: 11, height: 11, animation: 'spin 0.8s linear infinite' }} /> : <CheckCircle2 style={{ width: 11, height: 11 }} />}
          {status === 'failed' ? 'Failed' : (status as string) === 'queued' ? 'Queued' : status === 'running' ? 'Running' : 'Idle'}
        </div>
      </div>

      {/* Stale warning */}
      {isStale && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.25)', borderRadius: '0.625rem', padding: '0.625rem 0.75rem', marginBottom: '1rem', color: '#fbbf24', fontSize: '0.75rem' }}>
          <AlertTriangle style={{ width: 13, height: 13, flexShrink: 0, marginTop: 1 }} />
          <div><div style={{ fontWeight: 700 }}>Sync appears stuck</div>
            <div style={{ opacity: 0.8 }}>No heartbeat for over {staleThresholdMin} min{heartbeatAt ? ` (last: ${formatSyncTime(heartbeatAt)})` : ''}. Auto-reap on next trigger.</div>
          </div>
        </div>
      )}

      {/* Progress bar */}
      {(isSyncing || status === 'failed') && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.375rem' }}>
            <span style={{ color: 'var(--ds-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{step ? `Step: ${step}` : isSyncing ? 'Starting…' : 'Stopped'}</span>
            <span style={{ color: isSyncing ? '#60a5fa' : '#f87171' }}>{progress}%</span>
          </div>
          <div style={{ height: 6, borderRadius: '3px', background: 'var(--ds-table-head-bg)', overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${progress}%`, background: status === 'failed' ? '#f87171' : 'linear-gradient(90deg,#3b82f6,#06b6d4)', borderRadius: '3px', transition: 'width 0.5s ease' }} />
          </div>
          {error && <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#f87171', background: 'var(--ds-status-error-bg)', borderRadius: '0.5rem', padding: '0.5rem 0.625rem' }}>{error}</div>}
        </div>
      )}

      {/* Status items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
        <div style={{ ...itemBox, background: isSyncing ? 'rgba(59,130,246,0.10)' : 'var(--ds-table-head-bg)', borderColor: isSyncing ? 'rgba(59,130,246,0.25)' : 'var(--ds-table-border)' }}>
          <div style={iconBox(isSyncing)}><Activity style={{ width: 15, height: 15, color: isSyncing ? '#60a5fa' : 'var(--ds-text-muted)' }} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Current State</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 700, color: isSyncing ? '#60a5fa' : 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {isSyncing ? (step ? `Syncing — ${step}` : 'Synchronising…') : 'All systems idle'}
            </div>
            {(mode || syncId) && (
              <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
                {mode && <span style={{ fontSize: '0.625rem', fontFamily: 'monospace', padding: '0.1rem 0.375rem', borderRadius: '0.25rem', background: 'rgba(255,255,255,0.06)', color: 'var(--ds-text-muted)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}><Zap style={{ width: 9, height: 9 }} />{mode}</span>}
                {syncId && <span style={{ fontSize: '0.625rem', fontFamily: 'monospace', padding: '0.1rem 0.375rem', borderRadius: '0.25rem', background: 'rgba(255,255,255,0.06)', color: 'var(--ds-text-muted)', display: 'flex', alignItems: 'center', gap: '0.2rem' }}><Hash style={{ width: 9, height: 9 }} />{syncId.slice(0, 8)}</span>}
                {duration !== null && <span style={{ fontSize: '0.625rem', fontFamily: 'monospace', padding: '0.1rem 0.375rem', borderRadius: '0.25rem', background: 'rgba(255,255,255,0.06)', color: 'var(--ds-text-muted)' }}>{duration}s</span>}
              </div>
            )}
          </div>
        </div>

        <div style={itemBox}>
          <div style={iconBox()}><Clock style={{ width: 15, height: 15, color: 'var(--ds-text-muted)' }} /></div>
          <div>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Last Sync</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{formatSyncTime(lastSyncTime)}</div>
          </div>
        </div>

        <div style={itemBox}>
          <div style={iconBox()}><Database style={{ width: 15, height: 15, color: 'var(--ds-text-muted)' }} /></div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{isSyncing ? 'Records Processing' : 'Records Processed'}</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{lastSyncRecords > 0 ? lastSyncRecords.toLocaleString() : '--'}</div>
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', textAlign: 'right' }}>{totalSyncs} total syncs</div>
        </div>

        {Object.keys(shownStats).length > 0 && (
          <div style={{ paddingTop: '0.5rem', borderTop: '1px solid var(--ds-table-border)' }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', marginBottom: '0.5rem' }}>{isSyncing ? 'Live Breakdown' : 'Last Sync Breakdown'}</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
              {Object.entries(shownStats).map(([resource, count]) => (
                <span key={resource} style={{ fontSize: '0.6875rem', padding: '0.25rem 0.5rem', borderRadius: '0.375rem', background: 'var(--ds-table-head-bg)', border: '1px solid var(--ds-table-border)', color: 'var(--ds-text-secondary)', fontWeight: 500 }}>
                  {resource}: {Number(count).toLocaleString()}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
});

SyncStatusPanel.displayName = 'SyncStatusPanel';
export default SyncStatusPanel;
