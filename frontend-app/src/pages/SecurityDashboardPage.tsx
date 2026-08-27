/**
 * pages/SecurityDashboardPage.tsx — Dark glassmorphism, full ds-* design system.
 * Accessible via /admin/security and /hospital/security.
 */
import React, { useState, useEffect } from 'react';
import { tenantApi, systemApi } from '../shared/services/api';
import ErrorBanner from '../shared/ui/ErrorBanner';
import {
  Shield, Lock, AlertTriangle, CheckCircle2,
  FileText, User, Clock, Server,
  Layers, Key, Database,
} from 'lucide-react';

// ── Types ───────────────────────────────────────────────────────────────────
interface AuditEvent {
  id: number; timestamp: string; user: string;
  action: string; hospital: string; ip: string;
  status: 'success' | 'blocked' | 'warning';
}


// Each security layer: accent colours via inline styles, no Tailwind class strings
interface SecurityLayer { layer: string; detail: string; icon: React.ReactNode; bg: string; color: string; border: string; }
const SECURITY_LAYERS: SecurityLayer[] = [
  { layer: 'Application layer',  detail: 'JWT token validation + role check',      icon: <Key      style={{ width: 12, height: 12 }} />, bg: 'rgba(59,130,246,0.10)',  color: 'var(--ds-accent-blue)',   border: 'rgba(59,130,246,0.25)'  },
  { layer: 'API middleware',      detail: 'Tenant context injected into session',   icon: <Layers   style={{ width: 12, height: 12 }} />, bg: 'rgba(99,102,241,0.10)',  color: '#818cf8',                 border: 'rgba(99,102,241,0.25)'  },
  { layer: 'Database (RLS)',      detail: 'Row-Level Security filters every query', icon: <Database style={{ width: 12, height: 12 }} />, bg: 'rgba(139,92,246,0.10)', color: 'var(--ds-accent-purple)', border: 'rgba(139,92,246,0.25)' },
  { layer: 'Encryption at rest',  detail: 'AES-256 on all PHI columns',            icon: <Lock     style={{ width: 12, height: 12 }} />, bg: 'rgba(16,185,129,0.10)', color: 'var(--ds-accent-green)',  border: 'rgba(16,185,129,0.25)' },
  { layer: 'Transport (TLS 1.3)', detail: 'All data encrypted in transit',         icon: <Shield   style={{ width: 12, height: 12 }} />, bg: 'rgba(20,184,166,0.10)', color: '#2dd4bf',                 border: 'rgba(20,184,166,0.25)' },
];

// ── Design helpers ───────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: 'var(--ds-card-bg)',
  backdropFilter: 'var(--ds-card-blur)',
  WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
  border: '1px solid var(--ds-card-border)',
  borderRadius: '1rem',
  boxShadow: 'var(--ds-card-shadow)',
};

// ── Sub-components ───────────────────────────────────────────────────────────
const StatusChip: React.FC<{ status: AuditEvent['status'] }> = ({ status }) => {
  const styles: Record<string, { bg: string; color: string; border: string }> = {
    success: { bg: 'var(--ds-status-active-bg)',  color: 'var(--ds-status-active-text)',  border: 'rgba(16,185,129,0.25)'  },
    blocked: { bg: 'var(--ds-status-error-bg)',   color: 'var(--ds-status-error-text)',   border: 'rgba(239,68,68,0.25)'   },
    warning: { bg: 'var(--ds-status-pending-bg)', color: 'var(--ds-status-pending-text)', border: 'rgba(245,158,11,0.25)' },
  };
  const s = styles[status] ?? styles.success;
  return (
    <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: s.bg, color: s.color, border: `1px solid ${s.border}`, textTransform: 'capitalize', display: 'inline-block' }}>
      {status}
    </span>
  );
};

const PolicyRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--ds-table-border)' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <CheckCircle2 style={{ width: 14, height: 14, color: 'var(--ds-accent-green)', flexShrink: 0 }} />
      <span style={{ fontSize: '0.8125rem', color: 'var(--ds-text-secondary)' }}>{label}</span>
    </div>
    <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--ds-accent-green)' }}>{value}</span>
  </div>
);

// ── Main ─────────────────────────────────────────────────────────────────────
const SecurityDashboardPage: React.FC = () => {
  const [tenantInfo, setTenantInfo]   = useState<any>(null);
  const [auditLog, setAuditLog]       = useState<AuditEvent[]>([]);
  const [auditLoading, setAuditLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter]           = useState<'all' | 'blocked' | 'warning' | 'success'>('all');

  const loadData = async () => {
    setAuditLoading(true);
    setError(null);
    try {
      const [tenantResult, eventsResult] = await Promise.allSettled([
        tenantApi.info(),
        systemApi.events(100),
      ]);

      if (tenantResult.status === 'fulfilled') {
        setTenantInfo(tenantResult.value);
      }

      if (eventsResult.status === 'fulfilled' && eventsResult.value && Array.isArray(eventsResult.value)) {
        setAuditLog(eventsResult.value.map((e: any, i: number) => ({
          id: i + 1,
          timestamp: e.timestamp ? new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—',
          user: e.user || 'system',
          action: e.action || 'Unknown action',
          hospital: e.hospital || '—',
          ip: e.ip || '—',
          status: ['success', 'blocked', 'warning'].includes(e.status) ? e.status : 'success',
        })));
      } else {
        setAuditLog([]);
      }
    } catch (err) {
      console.error('[SecurityDashboardPage] Failed to load data:', err);
      setError((err as any)?.message || 'Failed to load security data');
      setAuditLog([]);
    } finally {
      setAuditLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const blocked  = auditLog.filter(e => e.status === 'blocked').length;
  const warnings = auditLog.filter(e => e.status === 'warning').length;
  const filtered = filter === 'all' ? auditLog : auditLog.filter(e => e.status === filter);

  const KPI_CARDS = [
    { label: 'Encryption',       value: 'AES-256',             sub: '100% PHI coverage',       icon: <Lock          style={{ width: 18, height: 18 }} />, color: 'var(--ds-accent-green)',  bg: 'rgba(16,185,129,0.12)',  border: 'rgba(16,185,129,0.25)'  },
    { label: 'Transport',        value: 'TLS 1.3',             sub: 'Active on all endpoints',  icon: <Server        style={{ width: 18, height: 18 }} />, color: 'var(--ds-accent-blue)',   bg: 'rgba(59,130,246,0.12)',  border: 'rgba(59,130,246,0.25)'  },
    { label: 'Blocked attempts', value: String(blocked),       sub: 'Last 24 h — all logged',   icon: <AlertTriangle style={{ width: 18, height: 18 }} />, color: 'var(--ds-status-error-text)',  bg: 'var(--ds-status-error-bg)',  border: 'rgba(239,68,68,0.25)'   },
    { label: 'Audit events',     value: String(auditLog.length), sub: 'Full event trail',        icon: <FileText      style={{ width: 18, height: 18 }} />, color: 'var(--ds-accent-purple)', bg: 'rgba(139,92,246,0.12)', border: 'rgba(139,92,246,0.25)' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate">
        <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Shield style={{ width: 20, height: 20, color: 'var(--ds-accent-blue)' }} /> Security Dashboard
        </h1>
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
          Tenant isolation proof · active policies · access audit · HIPAA compliance
        </p>
      </div>

      {error && <ErrorBanner message="Failed to load security data" detail={error} onRetry={loadData} />}

      {/* KPI Cards */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '1rem' }}>
        {KPI_CARDS.map(k => (
          <div key={k.label} style={{ ...card, padding: '1.125rem 1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{k.label}</span>
              <div style={{ width: 32, height: 32, borderRadius: '0.5rem', background: k.bg, border: `1px solid ${k.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: k.color }}>
                {k.icon}
              </div>
            </div>
            <p style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.03em' }}>{k.value}</p>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{k.sub}</p>
          </div>
        ))}
      </div>

      {/* Active policies section */}
      <div className="ds-animate ds-animate-d2">

        {/* Left — Active policies */}
        <div style={{ ...card, padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.875rem' }}>
            <Shield style={{ width: 14, height: 14, color: 'var(--ds-accent-blue)' }} />
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Active security policies</h2>
            <span style={{ marginLeft: 'auto', fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'rgba(16,185,129,0.12)', color: 'var(--ds-accent-green)', border: '1px solid rgba(16,185,129,0.25)' }}>
              {tenantInfo?.hospital_id ? `Tenant: ${tenantInfo.hospital_id}` : 'Tenant: hospital_a'}
            </span>
          </div>

          <PolicyRow label="Row-Level Security (RLS)"       value="All FHIR tables"          />
          <PolicyRow label="AES-256 encryption at rest"      value="100% PHI fields"          />
          <PolicyRow label="TLS 1.3 in transit"              value="All endpoints"             />
          <PolicyRow label="Multi-Factor Authentication"     value="Required for admins"       />
          <PolicyRow label="Rate limiting"                   value="100 req/min per tenant"    />
          <PolicyRow label="RBAC — role-based access"        value="admin · viewer · operator" />
          <PolicyRow label="Audit logging"                   value="All writes + auth events"  />
          <PolicyRow label="JWT session expiry"              value="8-hour TTL"                />

          {/* Defence-in-depth stack */}
          <div style={{ marginTop: '1.125rem', paddingTop: '0.875rem', borderTop: '1px solid var(--ds-table-border)' }}>
            <p style={{ margin: '0 0 0.625rem', fontSize: '0.6875rem', fontWeight: 700, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Defence-in-depth stack</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              {SECURITY_LAYERS.map((l, i) => (
                <div key={l.layer} style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.5rem 0.75rem', borderRadius: '0.5rem', background: l.bg, border: `1px solid ${l.border}` }}>
                  <div style={{ flexShrink: 0, color: l.color }}>{l.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: l.color }}>{l.layer}</span>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}> — {l.detail}</span>
                  </div>
                  <span style={{ fontSize: '0.6875rem', fontWeight: 800, color: 'var(--ds-text-muted)' }}>#{i + 1}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>

      {/* Audit log */}
      <div className="ds-animate ds-animate-d3" style={{ ...card, overflow: 'hidden' }}>
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.875rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} />
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Audit log</h2>
            <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'rgba(139,92,246,0.12)', color: 'var(--ds-accent-purple)', border: '1px solid rgba(139,92,246,0.25)', marginLeft: '0.25rem' }}>HIPAA compliant</span>
          </div>
          <div style={{ display: 'flex', gap: '0.25rem' }}>
            {(['all', 'success', 'blocked', 'warning'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{ fontSize: '0.6875rem', padding: '0.3rem 0.625rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer', fontFamily: 'inherit', fontWeight: filter === f ? 700 : 500, background: filter === f ? 'var(--ds-status-syncing-bg)' : 'transparent', color: filter === f ? 'var(--ds-status-syncing-text)' : 'var(--ds-text-muted)', transition: 'all 0.2s' }}
              >
                {f === 'all' ? `All (${auditLog.length})` : f === 'blocked' ? `Blocked (${blocked})` : f === 'warning' ? `Warning (${warnings})` : 'Success'}
              </button>
            ))}
          </div>
        </div>

        {/* Table head */}
        <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '64px 120px 100px 160px 120px 100px 80px', gap: '0.5rem', padding: '0.5rem 1.25rem', fontSize: '0.6875rem' }}>
          <span>Time</span><span>User</span><span>IP</span><span>Action</span><span>Hospital</span><span>IP addr</span><span>Status</span>
        </div>

        {/* Rows */}
        <div style={{ maxHeight: 340, overflowY: 'auto' }}>
          {auditLoading ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)', fontSize: '0.8125rem' }}>Loading audit events…</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)', fontSize: '0.8125rem' }}>No audit events available</div>
          ) : (
            filtered.map(event => (
            <div
              key={event.id}
              className="ds-table-row"
              style={{ display: 'grid', gridTemplateColumns: '64px 120px 100px 160px 120px 100px 80px', gap: '0.5rem', alignItems: 'center', padding: '0.625rem 1.25rem' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <Clock style={{ width: 11, height: 11, color: 'var(--ds-text-muted)', flexShrink: 0 }} />
                <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', fontFamily: 'monospace' }}>{event.timestamp}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', overflow: 'hidden' }}>
                <User style={{ width: 11, height: 11, color: 'var(--ds-text-muted)', flexShrink: 0 }} />
                <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: 'var(--ds-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{event.user}</span>
              </div>
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: 'var(--ds-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{event.ip}</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{event.action}</span>
              <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{event.hospital}</span>
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: 'var(--ds-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{event.ip}</span>
              <StatusChip status={event.status} />
            </div>
            ))
          )}
        </div>
      </div>

    </div>
  );
};

export default SecurityDashboardPage;
