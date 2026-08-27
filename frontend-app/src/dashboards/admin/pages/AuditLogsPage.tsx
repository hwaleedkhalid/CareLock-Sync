/** AuditLogsPage — theme-aware using ds-* tokens. All logic preserved. */
import React, { useState, useEffect } from 'react';
import { FileSearch, RefreshCw, Filter, Shield, User, Clock, Globe } from 'lucide-react';
import { systemApi, tenantApi } from '../../../shared/services/api';
import ErrorBanner from '../../../shared/ui/ErrorBanner';

interface AuditEvent { id: number; timestamp: string; user: string; action: string; hospital: string; ip: string; status: 'success' | 'blocked' | 'warning'; resource?: string }

const S: Record<AuditEvent['status'], { bg: string; color: string; border: string; dot: string; label: string }> = {
  success: { bg: 'var(--ds-status-active-bg)',  color: 'var(--ds-status-active-text)',  border: 'rgba(16,185,129,0.25)',  dot: '#34d399', label: 'Success' },
  blocked: { bg: 'var(--ds-status-error-bg)',   color: 'var(--ds-status-error-text)',   border: 'rgba(239,68,68,0.25)',   dot: '#f87171', label: 'Blocked' },
  warning: { bg: 'var(--ds-status-pending-bg)', color: 'var(--ds-status-pending-text)', border: 'rgba(245,158,11,0.25)',  dot: '#fbbf24', label: 'Warning' },
};

type FilterType = 'all' | 'success' | 'blocked' | 'warning';

function toStatus(et: string): AuditEvent['status'] {
  if (['LOGIN_FAILED', 'SYNC_FAILED'].includes(et)) return 'blocked';
  if (['SYNC_RESET'].includes(et)) return 'warning';
  return 'success';
}
function toResource(et: string): string | undefined {
  return { LOGIN_SUCCESS: '/api/v1/auth/login', LOGIN_FAILED: '/api/v1/auth/login', SYNC_TRIGGERED: '/api/v1/sync/full', SYNC_COMPLETED: '/api/v1/sync/full', SYNC_FAILED: '/api/v1/sync/full', SYNC_RESET: '/api/v1/sync/reset' }[et];
}

const COL = '140px 1fr 1fr 120px 110px 80px';

const AuditLogsPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filter, setFilter] = useState<FilterType>('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const [evResp, tenants] = await Promise.all([systemApi.events(100), tenantApi.list().catch(() => [])]);
      const tMap: Record<number, string> = {};
      if (Array.isArray(tenants)) tenants.forEach((t: any) => { tMap[t.id ?? t.tenant_id] = t.name ?? t.hospital_name ?? 'Unknown'; });
      const raw: any[] = evResp?.events ?? [];
      setEvents(raw.map((e): AuditEvent => ({ id: e.id, timestamp: new Date(e.timestamp + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }), user: e.user_email ?? 'system', action: e.message, hospital: e.tenant_id ? (tMap[e.tenant_id] ?? `Tenant #${e.tenant_id}`) : 'CareLock HQ', ip: e.ip_address ?? '—', status: toStatus(e.event_type), resource: toResource(e.event_type) })));
    } catch (e: any) {
      setEvents([]); setError(e?.response?.data?.detail ?? e?.message ?? 'Failed to load audit events');
    } finally { setLoading(false); setLastRefresh(new Date()); }
  };

  useEffect(() => { load(); }, []);

  const filtered = events.filter(e => {
    if (filter !== 'all' && e.status !== filter) return false;
    if (search.trim()) { const q = search.toLowerCase(); return e.user.toLowerCase().includes(q) || e.action.toLowerCase().includes(q) || e.hospital.toLowerCase().includes(q) || e.ip.toLowerCase().includes(q); }
    return true;
  });

  const counts: { all: number; success?: number; blocked?: number; warning?: number } & Record<string, number> = { all: events.length, ...events.reduce((acc, e) => { acc[e.status] = (acc[e.status] || 0) + 1; return acc; }, {} as Record<string, number>) };
  const KPI_COLORS = [{ color: '#60a5fa', bg: 'rgba(59,130,246,0.18)' }, { color: '#34d399', bg: 'rgba(16,185,129,0.18)' }, { color: '#f87171', bg: 'rgba(239,68,68,0.18)' }, { color: '#fbbf24', bg: 'rgba(245,158,11,0.18)' }];

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.25rem', fontFamily: "'Inter',sans-serif" }}>
      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.625rem', letterSpacing: '-0.02em' }}>
            <FileSearch style={{ width: 18, height: 18, color: '#60a5fa' }} />Audit Logs
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            All system events · HIPAA-compliant tamper-resistant log
            <span style={{ color: 'var(--ds-border)', margin: '0 0.25rem' }}>|</span>
            <Clock style={{ width: 11, height: 11 }} />
            <span style={{ fontSize: '0.75rem' }}>Refreshed {lastRefresh.toLocaleTimeString()}</span>
          </p>
        </div>
        <button onClick={load} className="ds-btn"><RefreshCw style={{ width: 13, height: 13, ...(loading ? { animation: 'spin 0.8s linear infinite' } : {}) }} />Refresh</button>
      </div>

      {error && <ErrorBanner message="Couldn't load audit events" detail={error} onRetry={load} retrying={loading} />}

      {/* KPIs */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: '1rem' }}>
        {[{ label: 'Total Events', value: counts.all ?? 0 }, { label: 'Success', value: counts.success ?? 0 }, { label: 'Blocked', value: counts.blocked ?? 0 }, { label: 'Warnings', value: counts.warning ?? 0 }].map((kpi, i) => (
          <div key={kpi.label} style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ width: 40, height: 40, borderRadius: '0.75rem', background: KPI_COLORS[i].bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <Shield style={{ width: 16, height: 16, color: KPI_COLORS[i].color }} />
            </div>
            <div>
              <div style={{ fontSize: '1.5rem', fontWeight: 800, color: KPI_COLORS[i].color, letterSpacing: '-0.02em', lineHeight: 1.1 }}>{kpi.value}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{kpi.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Table card */}
      <div className="ds-animate ds-animate-d2" style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', overflow: 'hidden' }}>
        {/* Filters */}
        <div style={{ padding: '0.875rem 1.25rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.75rem', borderBottom: '1px solid var(--ds-table-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--ds-surface-2)', borderRadius: '0.5rem', padding: '0.2rem', border: '1px solid var(--ds-border)' }}>
            {(['all', 'success', 'blocked', 'warning'] as FilterType[]).map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.375rem 0.625rem', borderRadius: '0.375rem', border: 'none', cursor: 'pointer', transition: 'all 0.2s', background: filter === f ? '#2563eb' : 'transparent', color: filter === f ? '#fff' : 'var(--ds-text-muted)', fontFamily: 'inherit', textTransform: 'capitalize' }}>
                {f === 'all' ? `All (${counts.all ?? 0})` : `${f} (${counts[f] ?? 0})`}
              </button>
            ))}
          </div>
          <div style={{ position: 'relative', flex: 1, minWidth: 0, maxWidth: 280 }}>
            <Filter style={{ width: 12, height: 12, color: 'var(--ds-text-muted)', position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)' }} />
            <input type="text" placeholder="Search user, action, IP…" value={search} onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', paddingLeft: '1.75rem', paddingRight: '0.75rem', paddingTop: '0.375rem', paddingBottom: '0.375rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-primary)', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit' }} />
          </div>
        </div>
        {/* Table head */}
        <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: COL, gap: '0.75rem', padding: '0.5rem 1.25rem' }}>
          <span>Time</span><span>User</span><span>Action</span><span>Hospital</span><span>IP Address</span><span>Status</span>
        </div>
        {/* Rows */}
        <div className="ds-scroll" style={{ maxHeight: 520, overflowY: 'auto' }}>
          {loading ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: COL, gap: '0.75rem', padding: '0.75rem 1.25rem', animation: 'ds-pulse 1.8s ease-in-out infinite', borderTop: '1px solid var(--ds-table-border)' }}>
                {[140, 120, 180, 90, 90, 60].map((w, j) => <div key={j} style={{ height: 14, background: 'rgba(255,255,255,0.04)', borderRadius: '0.25rem', maxWidth: w }} />)}
              </div>
            ))
          ) : filtered.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center' }}>
              <FileSearch style={{ width: 28, height: 28, color: 'var(--ds-text-muted)', margin: '0 auto 0.5rem' }} />
              <p style={{ fontSize: '0.875rem', color: 'var(--ds-text-muted)', margin: 0 }}>{events.length === 0 ? (error ? 'No events available' : 'No audit events recorded yet') : 'No events match your filter'}</p>
            </div>
          ) : filtered.map(ev => {
            const cfg = S[ev.status];
            return (
              <div key={ev.id} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: COL, gap: '0.75rem', alignItems: 'center', padding: '0.75rem 1.25rem' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', fontFamily: 'monospace' }}>{ev.timestamp}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                  <div style={{ width: 22, height: 22, background: 'rgba(59,130,246,0.18)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                    <User style={{ width: 11, height: 11, color: '#60a5fa' }} />
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.user}</span>
                </div>
                <div style={{ minWidth: 0 }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-secondary)', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.action}</span>
                  {ev.resource && <span style={{ fontSize: '0.625rem', color: 'var(--ds-text-muted)', fontFamily: 'monospace', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.resource}</span>}
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.hospital}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                  <Globe style={{ width: 11, height: 11, color: 'var(--ds-text-muted)', flexShrink: 0 }} />
                  <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', fontFamily: 'monospace' }}>{ev.ip}</span>
                </div>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.625rem', fontWeight: 700, padding: '0.25rem 0.5rem', borderRadius: '2rem', border: `1px solid ${cfg.border}`, background: cfg.bg, color: cfg.color, width: 'fit-content' }}>
                  <div style={{ width: 5, height: 5, borderRadius: '50%', background: cfg.dot, flexShrink: 0 }} />
                  {cfg.label}
                </span>
              </div>
            );
          })}
        </div>
        {/* Footer */}
        <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid var(--ds-table-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>Showing {filtered.length} of {events.length} events</p>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>Logs are HMAC-SHA256 chained · Tamper-resistant</p>
        </div>
      </div>
    </div>
  );
};

export default AuditLogsPage;
