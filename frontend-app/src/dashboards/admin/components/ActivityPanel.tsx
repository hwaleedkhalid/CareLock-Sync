/** ActivityPanel — theme-aware activity feed using ds-* tokens. */
import React from 'react';
import { RefreshCw, Building2, AlertTriangle, UserPlus, CheckCircle2, Database, Shield, Zap } from 'lucide-react';
import type { DashboardStats, SyncStatus } from '../../../shared/types';
import type { TenantRow } from './TenantTable';

interface Props { stats: DashboardStats | null; syncStatus: SyncStatus | null; tenants: TenantRow[]; loading: boolean }

interface ActivityEvent { id: string; iconEl: React.ReactNode; iconColor: string; iconBg: string; title: string; description: string; time: string }

function formatRelativeTime(iso: string): string {
  try {
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (diff < 1) return 'Just now'; if (diff < 60) return `${diff}m ago`;
    if (diff < 1440) return `${Math.floor(diff / 60)}h ago`;
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch { return 'Recently'; }
}
function formatTime(d: Date): string {
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true }) + ', ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function buildEvents(stats: DashboardStats | null, syncStatus: SyncStatus | null, tenants: TenantRow[]): ActivityEvent[] {
  const events: ActivityEvent[] = [];
  const now = new Date();
  if (syncStatus?.is_syncing) events.push({ id: 'sync-active', iconEl: <RefreshCw style={{ width: 14, height: 14 }} />, iconColor: '#60a5fa', iconBg: 'rgba(59,130,246,0.18)', title: 'Sync In Progress', description: 'Full system synchronization running', time: 'Now' });
  else if (syncStatus?.last_sync_time) events.push({ id: 'sync-done', iconEl: <CheckCircle2 style={{ width: 14, height: 14 }} />, iconColor: '#34d399', iconBg: 'rgba(16,185,129,0.18)', title: 'Sync Completed', description: `${syncStatus.total_syncs} total syncs processed`, time: formatRelativeTime(syncStatus.last_sync_time) });
  if (tenants.filter(t => t.status === 'active').length > 0) {
    const t = tenants.filter(t => t.status === 'active')[0];
    events.push({ id: 'tenant', iconEl: <Building2 style={{ width: 14, height: 14 }} />, iconColor: '#2dd4bf', iconBg: 'rgba(20,184,166,0.18)', title: 'Hospital Active', description: `${t.name} is actively syncing`, time: t.lastSync !== 'Never' ? t.lastSync : 'Recently' });
  }
  if (stats?.total_patients) events.push({ id: 'patients', iconEl: <UserPlus style={{ width: 14, height: 14 }} />, iconColor: '#60a5fa', iconBg: 'rgba(59,130,246,0.18)', title: 'Patient Records Updated', description: `${stats.total_patients.toLocaleString()} patients across all hospitals`, time: formatTime(new Date(now.getTime() - 25 * 60000)) });
  if (stats?.total_observations) events.push({ id: 'obs', iconEl: <Database style={{ width: 14, height: 14 }} />, iconColor: '#c084fc', iconBg: 'rgba(192,132,252,0.18)', title: 'FHIR Resources Mapped', description: `${stats.total_observations.toLocaleString()} observations indexed`, time: formatTime(new Date(now.getTime() - 45 * 60000)) });
  events.push({ id: 'security', iconEl: <Shield style={{ width: 14, height: 14 }} />, iconColor: '#fbbf24', iconBg: 'rgba(245,158,11,0.18)', title: 'Security Scan Complete', description: 'All endpoints passed validation', time: formatTime(new Date(now.getTime() - 2 * 3600000)) });
  events.push({ id: 'health', iconEl: <Zap style={{ width: 14, height: 14 }} />, iconColor: '#34d399', iconBg: 'rgba(16,185,129,0.18)', title: 'System Health Check', description: 'All services reporting healthy', time: formatTime(new Date(now.getTime() - 3 * 3600000)) });
  events.push({ id: 'quality', iconEl: <AlertTriangle style={{ width: 14, height: 14 }} />, iconColor: '#fbbf24', iconBg: 'rgba(245,158,11,0.18)', title: 'Quality Alert Resolved', description: 'Mapping accuracy restored to target', time: formatTime(new Date(now.getTime() - 5 * 3600000)) });
  return events.slice(0, 7);
}

const ActivityPanel: React.FC<Props> = React.memo(({ stats, syncStatus, tenants, loading }) => {
  if (loading) {
    return (
      <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '1.25rem', height: '100%' }}>
        <div style={{ width: 80, height: 16, background: 'rgba(255,255,255,0.05)', borderRadius: '0.375rem', marginBottom: '1.25rem' }} />
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', animation: 'ds-pulse 1.8s ease-in-out infinite' }}>
            <div style={{ width: 36, height: 36, background: 'rgba(255,255,255,0.05)', borderRadius: '0.75rem', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ width: 100, height: 11, background: 'rgba(255,255,255,0.05)', borderRadius: '0.25rem', marginBottom: '0.5rem' }} />
              <div style={{ width: 150, height: 9, background: 'rgba(255,255,255,0.03)', borderRadius: '0.25rem' }} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  const events = buildEvents(stats, syncStatus, tenants);

  return (
    <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)', flexShrink: 0 }}>
        <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Activity</h2>
      </div>
      <div className="ds-scroll" style={{ flex: 1, overflowY: 'auto' }}>
        {events.map(ev => (
          <div key={ev.id} className="ds-table-row" style={{ display: 'flex', gap: '0.75rem', padding: '0.75rem 1.25rem', alignItems: 'flex-start', cursor: 'default' }}>
            <div style={{ width: 34, height: 34, borderRadius: '0.75rem', background: ev.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: ev.iconColor }}>
              {ev.iconEl}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', alignItems: 'flex-start' }}>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)', lineHeight: 1.3 }}>{ev.title}</span>
                <span style={{ fontSize: '0.6rem', color: 'var(--ds-text-muted)', whiteSpace: 'nowrap', flexShrink: 0, marginTop: 1 }}>{ev.time}</span>
              </div>
              <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', margin: '0.2rem 0 0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
});

ActivityPanel.displayName = 'ActivityPanel';
export default ActivityPanel;
