/** AdminActions — ds-* theme-aware quick-action bar. All logic preserved. */
import React, { useEffect, useRef, useState } from 'react';
import { Play, RefreshCw, Building2, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { syncApi } from '../../../shared/services/api';
import type { SyncStatus } from '../../../shared/types';

interface Props { onRefresh: () => Promise<void>; syncStatus?: SyncStatus | null }

const POLL_MS = 2000;

const AdminActions: React.FC<Props> = ({ onRefresh, syncStatus }) => {
  const [triggering, setTriggering] = useState(false);
  const [activeSyncId, setActiveSyncId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'info' } | null>(null);
  const pollRef = useRef<number | null>(null);

  const externallyActive = syncStatus?.is_syncing ?? false;
  const disabled = triggering || externallyActive || activeSyncId !== null;

  const showToast = (msg: string, type: 'success' | 'error' | 'info') => {
    setToast({ msg, type });
    window.setTimeout(() => setToast(null), 4500);
  };

  const pollUntilDone = (syncId: string) => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const s: SyncStatus = await syncApi.status({ sync_id: syncId });
        if (!s.is_syncing) {
          if (pollRef.current) window.clearInterval(pollRef.current);
          pollRef.current = null;
          setActiveSyncId(null);
          if (s.status === 'completed') {
            const total = Object.values(s.records_processed || {}).reduce((a, b) => a + Number(b || 0), 0);
            showToast(`${s.mode === 'incremental' ? 'Incremental' : 'Full'} sync complete — ${total.toLocaleString()} records in ${s.duration_s ?? '?'}s`, 'success');
          } else {
            showToast(`Sync failed: ${s.error ?? 'unknown error'}`, 'error');
          }
          void onRefresh();
        }
      } catch { /* keep polling */ }
    }, POLL_MS);
  };

  const handleTriggerSync = async () => {
    setTriggering(true);
    try {
      const res = await syncApi.trigger();
      const syncId: string | undefined = res?.sync_id;
      const mode: string | undefined = res?.mode;
      if (syncId) {
        setActiveSyncId(syncId);
        showToast(`${(mode || 'Sync').toString().replace(/^./, c => c.toUpperCase())} queued — ${syncId.slice(0, 8)}…`, 'info');
        pollUntilDone(syncId);
      } else {
        showToast(res?.message || 'Sync triggered', 'success');
        setTimeout(() => onRefresh(), 1500);
      }
    } catch (err: any) {
      showToast(err?.response?.data?.detail || 'Failed to trigger sync', 'error');
    } finally {
      setTriggering(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await onRefresh(); showToast('Dashboard data refreshed', 'success'); }
    catch { showToast('Failed to refresh data', 'error'); }
    finally { setRefreshing(false); }
  };

  useEffect(() => {
    if (externallyActive && syncStatus?.sync_id && !pollRef.current) {
      setActiveSyncId(syncStatus.sync_id);
      pollUntilDone(syncStatus.sync_id);
    }
  }, [externallyActive, syncStatus?.sync_id]);

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);

  const syncLabel = disabled
    ? (syncStatus?.current_step ? `Syncing… ${syncStatus.current_step} ${syncStatus.progress ?? 0}%` : 'Syncing…')
    : 'Trigger Sync';

  const TOAST_STYLE: Record<string, { bg: string; color: string; border: string }> = {
    success: { bg: 'var(--ds-status-active-bg)',  color: 'var(--ds-status-active-text)',  border: 'rgba(16,185,129,0.30)' },
    error:   { bg: 'var(--ds-status-error-bg)',   color: 'var(--ds-status-error-text)',   border: 'rgba(239,68,68,0.30)'  },
    info:    { bg: 'var(--ds-status-syncing-bg)', color: 'var(--ds-status-syncing-text)', border: 'rgba(59,130,246,0.30)' },
  };

  return (
    <div style={{ position: 'relative' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' }}>
        {/* Trigger Sync */}
        <button onClick={handleTriggerSync} disabled={disabled} className="ds-btn ds-btn-primary" style={{ opacity: disabled ? 0.6 : 1, cursor: disabled ? 'not-allowed' : 'pointer' }}>
          {disabled ? <Loader2 style={{ width: 13, height: 13, animation: 'spin 0.8s linear infinite' }} /> : <Play style={{ width: 13, height: 13 }} />}
          {syncLabel}
        </button>
        {/* Refresh */}
        <button onClick={handleRefresh} disabled={refreshing} className="ds-btn" style={{ opacity: refreshing ? 0.6 : 1 }}>
          <RefreshCw style={{ width: 13, height: 13, ...(refreshing ? { animation: 'spin 0.8s linear infinite' } : {}) }} />
          Refresh
        </button>
        {/* Onboard */}
        <button onClick={() => { window.location.href = '/admin/onboard'; }} className="ds-btn"
          style={{ background: 'rgba(16,185,129,0.20)', borderColor: 'rgba(16,185,129,0.30)', color: '#34d399' }}>
          <Building2 style={{ width: 13, height: 13 }} />
          Onboard Hospital
        </button>
      </div>

      {toast && (() => { const t = TOAST_STYLE[toast.type]; return (
        <div style={{ position: 'absolute', top: 'calc(100% + 0.75rem)', left: 0, right: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', fontWeight: 500, padding: '0.75rem 1rem', borderRadius: '0.75rem', boxShadow: '0 8px 24px rgba(0,0,0,0.25)', zIndex: 10, border: `1px solid ${t.border}`, background: t.bg, color: t.color }}>
          {toast.type === 'success' ? <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0 }} /> : toast.type === 'error' ? <AlertCircle style={{ width: 14, height: 14, flexShrink: 0 }} /> : <Loader2 style={{ width: 14, height: 14, flexShrink: 0, animation: 'spin 0.8s linear infinite' }} />}
          {toast.msg}
        </div>
      ); })()}
    </div>
  );
};

export default AdminActions;
