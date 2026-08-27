/** dashboards/analyst/pages/AnalystDashboard.tsx — Dark ds-* design system. */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, Brain, TrendingUp, Database, BookOpen, MessageSquare, ArrowRight, Users, Activity, RefreshCw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { dashboardApi } from '../../../shared/services/api';

const SYNC_TREND = [
  { day: 'Mon', patients: 120, labs: 310 }, { day: 'Tue', patients: 98, labs: 280 },
  { day: 'Wed', patients: 143, labs: 420 }, { day: 'Thu', patients: 87, labs: 190 },
  { day: 'Fri', patients: 165, labs: 510 }, { day: 'Sat', patients: 52, labs: 140 },
  { day: 'Sun', patients: 44, labs: 98 },
];
const FHIR_COVERAGE = [
  { resource: 'Patient', coverage: 99.4, records: 8562 }, { resource: 'Encounter', coverage: 97.8, records: 24011 },
  { resource: 'Observation', coverage: 95.2, records: 84230 }, { resource: 'MedicationRequest', coverage: 93.7, records: 15631 },
];
const RESOURCE_PIE = [
  { name: 'Patients', value: 8562, color: '#3b82f6' }, { name: 'Encounters', value: 24011, color: '#8b5cf6' },
  { name: 'Labs', value: 84230, color: '#10b981' }, { name: 'Medications', value: 15631, color: '#f59e0b' },
];
const HOSPITAL_PERF = [
  { hospital: 'CGH', syncRate: 99.8, accuracy: 99.4, latency: 11 },
  { hospital: 'NMC', syncRate: 98.5, accuracy: 98.1, latency: 14 },
  { hospital: 'AKUH', syncRate: 99.9, accuracy: 99.7, latency: 9 },
];

const ICON_GRAD: Record<string, string> = { blue: 'linear-gradient(135deg,rgba(59,130,246,0.18),rgba(59,130,246,0.04))', purple: 'linear-gradient(135deg,rgba(139,92,246,0.18),rgba(139,92,246,0.04))', indigo: 'linear-gradient(135deg,rgba(99,102,241,0.20),rgba(99,102,241,0.04))', green: 'linear-gradient(135deg,rgba(34,197,94,0.18),rgba(34,197,94,0.04))' };
const ICON_BG: Record<string, string> = { blue: 'rgba(59,130,246,0.20)', purple: 'rgba(139,92,246,0.20)', indigo: 'rgba(99,102,241,0.22)', green: 'rgba(34,197,94,0.20)' };
const ICON_COLOR: Record<string, string> = { blue: '#60a5fa', purple: '#c084fc', indigo: '#818cf8', green: '#4ade80' };

const card = (extra?: React.CSSProperties): React.CSSProperties => ({ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', ...extra });

const AnalystDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<any>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => { dashboardApi.getStats().then(setStats).catch(() => {}); }, []);
  const refresh = async () => { setRefreshing(true); try { setStats(await dashboardApi.getStats()); } catch {} setTimeout(() => setRefreshing(false), 600); };

  const kpis = [
    { label: 'Total Patients', value: stats?.total_patients?.toLocaleString() ?? '8,562', accent: 'blue',   icon: <Users     style={{ width: 18, height: 18 }} />, trend: '+3.2%' },
    { label: 'FHIR Records',   value: '132,434',                                           accent: 'purple', icon: <Database  style={{ width: 18, height: 18 }} />, trend: '+8.7%' },
    { label: 'AI Accuracy',    value: '99.4%',                                             accent: 'indigo', icon: <Brain     style={{ width: 18, height: 18 }} />, trend: '+0.6%' },
    { label: 'Avg Sync Rate',  value: '99.4%',                                             accent: 'green',  icon: <Activity  style={{ width: 18, height: 18 }} />, trend: 'Nominal' },
  ];

  const TOOLTIP_STYLE = { background: 'var(--ds-surface-2)', border: '1px solid var(--ds-border)', borderRadius: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-primary)' };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif" }}>
      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>Analytics Overview</h1>
          <p style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)', margin: '0.25rem 0 0' }}>Cross-hospital FHIR data analysis · All tenants</p>
        </div>
        <button onClick={refresh} className="ds-btn"><RefreshCw style={{ width: 13, height: 13, ...(refreshing ? { animation: 'spin 0.7s linear infinite' } : {}) }} />Refresh</button>
      </div>

      {/* KPIs */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '1rem' }}>
        {kpis.map(k => (
          <div key={k.label} style={{ background: ICON_GRAD[k.accent], border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.25rem', transition: 'border-color 0.25s,transform 0.25s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-hover-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.875rem' }}>
              <div style={{ width: 40, height: 40, background: ICON_BG[k.accent], borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: ICON_COLOR[k.accent], display: 'flex' }}>{k.icon}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.5rem', background: 'rgba(16,185,129,0.15)', color: '#34d399' }}>
                <TrendingUp style={{ width: 10, height: 10 }} />{k.trend}
              </div>
            </div>
            <div style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>{k.value}</div>
            <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-secondary)', marginTop: '0.25rem' }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,2fr) minmax(0,1fr)', gap: '1rem' }}>
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>7-Day Data Sync Volume</h2>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={SYNC_TREND} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gP" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} /><stop offset="95%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient>
                <linearGradient id="gL" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#10b981" stopOpacity={0.3} /><stop offset="95%" stopColor="#10b981" stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' } as any} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' } as any} />
              <Tooltip contentStyle={TOOLTIP_STYLE} />
              <Area type="monotone" dataKey="patients" stroke="#3b82f6" fill="url(#gP)" name="Patients" strokeWidth={2} />
              <Area type="monotone" dataKey="labs" stroke="#10b981" fill="url(#gL)" name="Lab Results" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>FHIR Resource Distribution</h2>
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie data={RESOURCE_PIE} cx="50%" cy="50%" innerRadius={42} outerRadius={68} dataKey="value">
                {RESOURCE_PIE.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Pie>
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => (v as number).toLocaleString()} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', marginTop: '0.5rem' }}>
            {RESOURCE_PIE.map(r => (
              <div key={r.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: r.color, flexShrink: 0 }} />
                  <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-secondary)' }}>{r.name}</span>
                </div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{r.value.toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* FHIR coverage + Hospital performance */}
      <div className="ds-animate ds-animate-d3" style={{ display: 'grid', gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)', gap: '1rem' }}>
        <div style={card({ padding: '1.25rem' })}>
          <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>FHIR Mapping Coverage</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {FHIR_COVERAGE.map(r => (
              <div key={r.resource}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>{r.resource}</span>
                  <div style={{ display: 'flex', gap: '0.625rem', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{r.records.toLocaleString()} records</span>
                    <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--ds-text-primary)' }}>{r.coverage}%</span>
                  </div>
                </div>
                <div style={{ height: 6, background: 'var(--ds-table-head-bg)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${r.coverage}%`, background: 'linear-gradient(90deg,#3b82f6,#6366f1)', borderRadius: '3px', transition: 'width 0.7s ease' }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div style={card({ overflow: 'hidden' })}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)' }}>
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Hospital Performance</h2>
          </div>
          <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '1fr 5rem 5.5rem 4.5rem', gap: '0.5rem', padding: '0.625rem 1.25rem' }}>
            <span>Hospital</span><span style={{ textAlign: 'right' }}>Sync Rate</span><span style={{ textAlign: 'right' }}>AI Accuracy</span><span style={{ textAlign: 'right' }}>Latency</span>
          </div>
          {HOSPITAL_PERF.map(h => (
            <div key={h.hospital} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: '1fr 5rem 5.5rem 4.5rem', gap: '0.5rem', padding: '0.75rem 1.25rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{h.hospital}</span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: h.syncRate >= 99 ? '#34d399' : '#fbbf24', textAlign: 'right' }}>{h.syncRate}%</span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#818cf8', textAlign: 'right' }}>{h.accuracy}%</span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-secondary)', textAlign: 'right' }}>{h.latency}ms</span>
            </div>
          ))}
        </div>
      </div>

      {/* Quick tools */}
      <div className="ds-animate ds-animate-d4" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '1rem' }}>
        {[
          { label: 'Data Quality Report', desc: 'Completeness, accuracy, sync metrics', icon: BarChart3,      color: '#c084fc', bg: 'rgba(192,132,252,0.15)', to: '/analyst/data-quality' },
          { label: 'Research Papers',     desc: 'System architecture & findings',       icon: BookOpen,       color: '#60a5fa', bg: 'rgba(59,130,246,0.15)',  to: '/analyst/research' },
          { label: 'AI Query Chat',       desc: 'Natural language FHIR queries',        icon: MessageSquare,  color: '#818cf8', bg: 'rgba(99,102,241,0.15)',  to: '/analyst/chat' },
        ].map(a => (
          <button key={a.label} onClick={() => navigate(a.to)} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', padding: '1rem 1.125rem', borderRadius: '1rem', border: '1px solid var(--ds-border)', background: 'var(--ds-surface-2)', cursor: 'pointer', textAlign: 'left', transition: 'border-color 0.25s,transform 0.2s,box-shadow 0.25s', fontFamily: "'Inter',sans-serif" }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-hover-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 8px 24px rgba(139,92,246,0.15)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-border)'; (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; (e.currentTarget as HTMLElement).style.boxShadow = 'none'; }}>
            <div style={{ width: 38, height: 38, borderRadius: '0.75rem', background: a.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <a.icon style={{ width: 18, height: 18, color: a.color }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{a.label}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{a.desc}</div>
            </div>
            <ArrowRight style={{ width: 14, height: 14, color: 'var(--ds-text-muted)', flexShrink: 0, marginTop: 3 }} />
          </button>
        ))}
      </div>
    </div>
  );
};

export default AnalystDashboard;
