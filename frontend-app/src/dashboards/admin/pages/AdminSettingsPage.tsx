/** AdminSettingsPage — theme-aware using ds-* tokens. All logic preserved. */
import React, { useState, useEffect } from 'react';
import { Settings, Server, Database, Shield, RefreshCw, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { statusApi } from '../../../shared/services/api';


const Card: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode }> = ({ title, icon, children }) => (
  <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.25rem' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '1rem' }}>
      <span style={{ color: '#60a5fa', display: 'flex', alignItems: 'center' }}>{icon}</span>
      <h3 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{title}</h3>
    </div>
    {children}
  </div>
);

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.625rem 0', borderBottom: '1px solid var(--ds-table-border)' }}
    className="last-child-no-border">
    <span style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>{label}</span>
    <span style={{ fontSize: '0.8125rem', color: 'var(--ds-text-secondary)', fontWeight: 500 }}>{value}</span>
  </div>
);

const AdminSettingsPage: React.FC = () => {
  const [health, setHealth] = useState<{ status: string; version?: string } | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [checking, setChecking] = useState(true);

  const checkHealth = async () => {
    setChecking(true); setHealthError(false);
    try { setHealth(await statusApi.health()); }
    catch { setHealthError(true); setHealth(null); }
    finally { setChecking(false); }
  };

  useEffect(() => { checkHealth(); }, []);
  const apiUrl = import.meta.env.VITE_API_URL ?? 'http://localhost:8003';

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif" }}>
      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.625rem', letterSpacing: '-0.02em' }}>
            <Settings style={{ width: 20, height: 20, color: 'var(--ds-text-muted)' }} />Settings
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>System configuration · read-only · edit via environment variables</p>
        </div>
        <button onClick={checkHealth} disabled={checking} className="ds-btn" style={{ opacity: checking ? 0.6 : 1 }}>
          <RefreshCw style={{ width: 13, height: 13, ...(checking ? { animation: 'spin 0.8s linear infinite' } : {}) }} />
          Re-check
        </button>
      </div>

      {/* Cards grid */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(440px,1fr))', gap: '1rem' }}>
        {/* API Connection */}
        <Card title="API Connection" icon={<Server style={{ width: 15, height: 15 }} />}>
          <Row label="Backend URL" value={<code style={{ fontSize: '0.75rem', background: 'var(--ds-table-head-bg)', padding: '0.15rem 0.375rem', borderRadius: '0.25rem', color: 'var(--ds-text-secondary)', fontFamily: 'monospace' }}>{apiUrl}</code>} />
          <Row label="Status" value={
            checking ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--ds-text-muted)' }}>
                <RefreshCw style={{ width: 12, height: 12, animation: 'spin 0.8s linear infinite' }} />Checking…
              </span>
            ) : healthError ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--ds-status-error-text)' }}>
                <XCircle style={{ width: 12, height: 12 }} />Unreachable
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: 'var(--ds-status-active-text)' }}>
                <CheckCircle2 style={{ width: 12, height: 12 }} />Connected
              </span>
            )
          } />
          {health && <>
            <Row label="API Version" value={health.version ?? '—'} />
            <Row label="API Status"  value={health.status ?? '—'} />
          </>}
        </Card>

        {/* Security */}
        <Card title="Security Configuration" icon={<Shield style={{ width: 15, height: 15 }} />}>
          <Row label="Token algorithm"    value="HS256 JWT" />
          <Row label="Token expiry"       value="30 minutes" />
          <Row label="Password hashing"   value="bcrypt" />
          <Row label="Transport security" value="TLS 1.3 (all endpoints)" />
          <Row label="Data encryption"    value="AES-256-GCM (PHI at rest)" />
          <Row label="Tenant isolation"   value="PostgreSQL RLS" />
        </Card>

        {/* Database */}
        <Card title="Database Configuration" icon={<Database style={{ width: 15, height: 15 }} />}>
          <Row label="Hospital DB port"   value="5432 (PostgreSQL)" />
          <Row label="Shared DB port"     value="5433 (PostgreSQL)" />
          <Row label="Shared DB sslmode"  value="prefer" />
          <Row label="Connection pooling" value="SQLAlchemy pool_pre_ping" />
          <Row label="Audit log"          value="SQLite (data/carelock_events.db)" />
        </Card>

        {/* Runtime */}
        <Card title="Runtime" icon={<Clock style={{ width: 15, height: 15 }} />}>
          <Row label="Frontend"   value="http://localhost:5173" />
          <Row label="API docs"   value={<a href={`${apiUrl}/docs`} target="_blank" rel="noreferrer" style={{ color: 'var(--ds-text-link)' }}>{apiUrl}/docs</a>} />
          <Row label="Environment" value={import.meta.env.MODE ?? 'development'} />
          <Row label="Build"       value={import.meta.env.PROD ? 'Production' : 'Development'} />
        </Card>
      </div>

      <p style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
        Configuration values come from{' '}
        <code style={{ background: 'var(--ds-table-head-bg)', padding: '0.1rem 0.375rem', borderRadius: '0.25rem', fontFamily: 'monospace' }}>config/.env</code>
        {' '}and{' '}
        <code style={{ background: 'var(--ds-table-head-bg)', padding: '0.1rem 0.375rem', borderRadius: '0.25rem', fontFamily: 'monospace' }}>frontend-app/.env</code>.
        {' '}Restart the server after editing environment files.
      </p>
    </div>
  );
};

export default AdminSettingsPage;
