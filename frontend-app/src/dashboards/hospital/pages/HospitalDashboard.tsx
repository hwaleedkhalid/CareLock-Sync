/** dashboards/hospital/pages/HospitalDashboard.tsx — Dark ds-* design system. */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, Activity, Database, Brain, RefreshCw, TrendingUp, CheckCircle2, Clock, ArrowRight, Zap, Lock } from 'lucide-react';
import { useAuth } from '../../../shared/context/AuthContext';
import { dashboardApi, syncApi } from '../../../shared/services/api';

const MOCK_ACTIVITY = [
  { time: '14:22', type: 'sync',    color: '#60a5fa', msg: '127 new encounter records synced to FHIR' },
  { time: '14:18', type: 'mapping', color: '#a78bfa', msg: 'AI mapping confirmed: lab_value → Observation.valueQuantity' },
  { time: '13:55', type: 'patient', color: '#2dd4bf', msg: 'New patient admitted — MRN 00129834 created' },
  { time: '13:40', type: 'sync',    color: '#60a5fa', msg: 'Incremental sync completed in 1.2s (99.8% success)' },
  { time: '13:01', type: 'cdc',     color: '#c084fc', msg: 'CDC agent detected 43 row changes in lab_results' },
];

const ICON_COLOR: Record<string, string> = { blue: '#60a5fa', emerald: '#34d399', purple: '#c084fc', amber: '#fbbf24' };
const ICON_BG: Record<string, string> = { blue: 'rgba(59,130,246,0.18)', emerald: 'rgba(16,185,129,0.18)', purple: 'rgba(192,132,252,0.18)', amber: 'rgba(245,158,11,0.18)' };
const ICON_GRAD: Record<string, string> = { blue: 'linear-gradient(135deg,rgba(59,130,246,0.18),rgba(59,130,246,0.04))', emerald: 'linear-gradient(135deg,rgba(16,185,129,0.18),rgba(16,185,129,0.04))', purple: 'linear-gradient(135deg,rgba(192,132,252,0.18),rgba(192,132,252,0.04))', amber: 'linear-gradient(135deg,rgba(245,158,11,0.18),rgba(245,158,11,0.04))' };

const card = (extra?: React.CSSProperties): React.CSSProperties => ({ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', ...extra });

const HospitalDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<any>(null);
  const [syncStatus, setSyncStatus] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    try {
      const [s, ss] = await Promise.allSettled([dashboardApi.getStats(), syncApi.status()]);
      if (s.status === 'fulfilled') setStats(s.value);
      if (ss.status === 'fulfilled') setSyncStatus(ss.value);
    } catch { /* demo */ }
  };

  useEffect(() => { fetchData(); }, []);
  const refresh = async () => { setRefreshing(true); await fetchData(); setTimeout(() => setRefreshing(false), 600); };

  const kpis = [
    { label: 'Patients',    value: stats?.total_patients?.toLocaleString() ?? '2,847',  sub: 'in FHIR central DB',   accent: 'blue',    icon: <Users     style={{ width: 18, height: 18 }} />, trend: '+12 today' },
    { label: 'Encounters',  value: stats?.total_encounters?.toLocaleString() ?? '9,201', sub: 'total encounters',     accent: 'emerald', icon: <Activity  style={{ width: 18, height: 18 }} />, trend: '+34 today' },
    { label: 'Lab Results', value: stats?.total_observations?.toLocaleString() ?? '31,450', sub: 'FHIR Observations', accent: 'purple', icon: <Database  style={{ width: 18, height: 18 }} /> },
    { label: 'Medications', value: stats?.total_medications?.toLocaleString() ?? '5,631', sub: 'MedicationRequests', accent: 'amber',  icon: <Brain     style={{ width: 18, height: 18 }} /> },
  ];

  const sh = syncStatus
    ? { status: syncStatus.is_syncing ? 'Syncing…' : 'Idle', rate: ((syncStatus.successful_syncs / Math.max(syncStatus.total_syncs, 1)) * 100).toFixed(1) + '%', total: syncStatus.total_syncs?.toLocaleString() ?? '1,847', last: syncStatus.last_sync_time ? new Date(syncStatus.last_sync_time).toLocaleTimeString() : '< 2 min ago' }
    : { status: 'Active', rate: '99.8%', total: '1,847', last: '< 2 min ago' };

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif" }}>
      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>{user?.hospital_name ?? 'Hospital'} — Dashboard</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)', margin: '0.25rem 0 0' }}>Tenant #{user?.tenant_id ?? 1} · Isolated with RLS</p>
        </div>
        <button onClick={refresh} className="ds-btn"><RefreshCw style={{ width: 13, height: 13, ...(refreshing ? { animation: 'spin 0.7s linear infinite' } : {}) }} />Refresh</button>
      </div>

      {/* KPIs */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '1rem' }}>
        {kpis.map(k => (
          <div key={k.label} style={{ background: ICON_GRAD[k.accent], border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.25rem', transition: 'border-color 0.25s,transform 0.25s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-hover-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}>
            <div style={{ width: 42, height: 42, background: ICON_BG[k.accent], borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.875rem' }}>
              <span style={{ color: ICON_COLOR[k.accent], display: 'flex' }}>{k.icon}</span>
            </div>
            <div style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>{k.value}</div>
            <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-secondary)', marginTop: '0.25rem' }}>{k.label}</div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{k.sub}</div>
            {k.trend && <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', fontWeight: 700, color: '#34d399', marginTop: '0.5rem' }}><TrendingUp style={{ width: 11, height: 11 }} />{k.trend}</div>}
          </div>
        ))}
      </div>

      {/* Middle row */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr) minmax(0,1fr)', gap: '1rem' }}>
        {/* Sync status */}
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Zap style={{ width: 14, height: 14, color: '#60a5fa' }} />CDC Sync Status
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            {[{ label: 'Status', value: sh.status, color: '#34d399' }, { label: 'Success Rate', value: sh.rate, color: 'var(--ds-text-primary)' }, { label: 'Total Syncs', value: sh.total, color: 'var(--ds-text-primary)' }, { label: 'Last Sync', value: sh.last, color: 'var(--ds-text-muted)' }].map(r => (
              <div key={r.label} className="ds-table-row" style={{ display: 'flex', justifyContent: 'space-between', padding: '0.375rem 0', border: 'none', borderBottom: '1px solid var(--ds-table-border)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{r.label}</span>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: r.color }}>{r.value}</span>
              </div>
            ))}
          </div>
          <button onClick={() => navigate('/hospital/monitoring')} style={{ marginTop: '1rem', background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-text-link)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            View full monitor <ArrowRight style={{ width: 11, height: 11 }} />
          </button>
        </div>

        {/* Security */}
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Lock style={{ width: 14, height: 14, color: '#34d399' }} />Security Status
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {['Row-Level Security', 'AES-256 Encryption', 'TLS 1.3 in Transit', 'MFA Enforcement', 'Audit Logging', 'Rate Limiting'].map(s => (
              <div key={s} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-secondary)' }}>{s}</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', fontWeight: 700, color: '#34d399' }}>
                  <CheckCircle2 style={{ width: 11, height: 11 }} />Enabled
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Activity */}
        <div style={card({ overflow: 'hidden' })}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Clock style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} />
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Recent Activity</h2>
          </div>
          {MOCK_ACTIVITY.map((ev, i) => (
            <div key={i} className="ds-table-row" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.625rem', padding: '0.625rem 1rem' }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: ev.color, flexShrink: 0, marginTop: 5 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-secondary)', margin: '0 0 0.125rem', lineHeight: 1.4 }}>{ev.msg}</p>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.5625rem', fontWeight: 700, padding: '0.1rem 0.35rem', borderRadius: '0.3rem', background: `${ev.color}22`, color: ev.color }}>{ev.type}</span>
                  <span style={{ fontSize: '0.6rem', color: 'var(--ds-text-muted)' }}>{ev.time}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quick actions */}
      <div className="ds-animate ds-animate-d3" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(150px,1fr))', gap: '1rem' }}>
        {[
          { label: 'View Patients', icon: Users,      color: '#60a5fa', bg: 'rgba(59,130,246,0.15)',   to: '/hospital/patients' },
          { label: 'Sync Monitor',  icon: RefreshCw,  color: '#34d399', bg: 'rgba(16,185,129,0.15)',   to: '/hospital/monitoring' },
          { label: 'AI Mapping',    icon: Brain,      color: '#c084fc', bg: 'rgba(192,132,252,0.15)',  to: '/hospital/mapping' },
          { label: 'Data Sources',  icon: Database,   color: '#818cf8', bg: 'rgba(99,102,241,0.15)',   to: '/hospital/data-sources' },
        ].map(a => (
          <button key={a.label} onClick={() => navigate(a.to)} className="ds-quick-action">
            <div style={{ width: 40, height: 40, borderRadius: '0.875rem', background: a.bg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <a.icon style={{ width: 19, height: 19, color: a.color }} />
            </div>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>{a.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default HospitalDashboard;
