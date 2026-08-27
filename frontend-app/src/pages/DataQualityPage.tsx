/**
 * DataQualityPage — Dark glassmorphism, full ds-* design system.
 * FHIR mapping accuracy and synchronization quality metrics.
 */
import React, { useEffect, useState } from 'react';
import { dashboardApi } from '../shared/services/api';
import { ChartColumn, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import ErrorBanner from '../shared/ui/ErrorBanner';
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell,
} from 'recharts';

interface QualityMetrics {
  completeness_score: number;
  sync_success_rate: number;
  mapping_accuracy: number;
  error_rate: number;
}

const FHIR_RESOURCES = [
  { name: 'Patient',           mapped: 12, total: 13 },
  { name: 'Encounter',         mapped: 8,  total: 9  },
  { name: 'Observation',       mapped: 15, total: 17 },
  { name: 'MedicationRequest', mapped: 10, total: 12 },
];

// ── ScoreRing — SVG circle progress indicator ─────────────────────────────────
const ScoreRing: React.FC<{ value: number; label: string; color: string }> = ({ value, label, color }) => {
  const pct  = Math.round(value * 100);
  const r    = 36;
  const circ = 2 * Math.PI * r;
  const off  = circ - (pct / 100) * circ;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.375rem' }}>
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeDasharray={circ} strokeDashoffset={off}
          strokeLinecap="round" transform="rotate(-90 50 50)" style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
        <text x="50" y="54" textAnchor="middle" fontSize="16" fontWeight="700" fill="var(--ds-text-primary)">{pct}%</text>
      </svg>
      <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', textAlign: 'center' }}>{label}</span>
    </div>
  );
};

// ── Custom chart tooltip ───────────────────────────────────────────────────────
const ChartTooltip: React.FC<any> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'rgba(13,20,42,0.95)', border: '1px solid var(--ds-card-border)', borderRadius: '0.5rem', padding: '0.5rem 0.75rem', fontSize: '0.75rem', color: 'var(--ds-text-primary)' }}>
      <p style={{ margin: '0 0 0.25rem', fontWeight: 700 }}>{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ margin: 0, color: p.color ?? 'var(--ds-text-secondary)' }}>
          {p.name ?? 'Value'}: {typeof p.value === 'number' ? `${p.value}%` : p.value}
          {p.payload?.mapped != null ? ` (${p.payload.mapped}/${p.payload.total} fields)` : ''}
        </p>
      ))}
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const DataQualityPage: React.FC = () => {
  const [metrics, setMetrics] = useState<QualityMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);

    dashboardApi.getDataQuality()
      .then(setMetrics)
      .catch(err => {
        console.error('[DataQualityPage] Failed to load metrics:', err);
        setError(err?.message || 'Failed to load data quality metrics');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '16rem' }}>
      <Loader2 style={{ width: 32, height: 32, color: '#818cf8', animation: 'spin 0.8s linear infinite' }} />
    </div>
  );

  if (error) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: 1100, margin: '0 auto' }}>
      <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)' }}>Data Quality</h1>
      <ErrorBanner message="Failed to load data quality metrics" detail={error} onRetry={loadData} />
    </div>
  );

  const overallScore = metrics
    ? Math.round(((metrics.completeness_score + metrics.sync_success_rate + metrics.mapping_accuracy + (1 - metrics.error_rate)) / 4) * 100)
    : 0;

  const radarData = metrics
    ? [
        { subject: 'Completeness',    value: Math.round(metrics.completeness_score * 100) },
        { subject: 'Sync Success',    value: Math.round(metrics.sync_success_rate  * 100) },
        { subject: 'Mapping Accuracy',value: Math.round(metrics.mapping_accuracy   * 100) },
        { subject: 'Error-Free',      value: Math.round((1 - metrics.error_rate)   * 100) },
        { subject: 'FHIR Coverage',   value: 93 },
      ]
    : [];

  const barData = FHIR_RESOURCES.map((r) => ({
    name: r.name, accuracy: Math.round((r.mapped / r.total) * 100), mapped: r.mapped, total: r.total,
  }));

  const BAR_COLORS = ['#3b82f6', '#22c55e', '#8b5cf6', '#f59e0b'];

  const card: React.CSSProperties = {
    background: 'var(--ds-card-bg)',
    backdropFilter: 'var(--ds-card-blur)',
    WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
    border: '1px solid var(--ds-card-border)',
    borderRadius: '1rem',
    boxShadow: 'var(--ds-card-shadow)',
  };

  const scoreColor =
    overallScore >= 95 ? 'var(--ds-accent-green)' :
    overallScore >= 80 ? 'var(--ds-accent-orange)' :
                         '#ef4444';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ChartColumn style={{ width: 20, height: 20, color: 'var(--ds-accent-blue)' }} /> Data Quality
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
            FHIR mapping accuracy and synchronization quality metrics
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p style={{ margin: 0, fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>Overall quality score</p>
          <p style={{ margin: 0, fontSize: '2.5rem', fontWeight: 800, color: scoreColor, letterSpacing: '-0.04em', lineHeight: 1 }}>{overallScore}%</p>
        </div>
      </div>

      {/* Score rings */}
      <div className="ds-animate ds-animate-d1" style={{ ...card, padding: '1.25rem' }}>
        <h2 style={{ margin: '0 0 1.25rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Quality dimensions</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', gap: '1rem', justifyItems: 'center' }}>
          <ScoreRing value={metrics?.completeness_score ?? 0} label="Data completeness" color="#3b82f6" />
          <ScoreRing value={metrics?.sync_success_rate  ?? 0} label="Sync success rate"  color="#22c55e" />
          <ScoreRing value={metrics?.mapping_accuracy   ?? 0} label="Mapping accuracy"   color="#8b5cf6" />
          <ScoreRing value={1 - (metrics?.error_rate    ?? 0)} label="Error-free rate"   color="#f59e0b" />
        </div>
      </div>

      {/* Charts row */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* Radar chart */}
        <div style={{ ...card, padding: '1.125rem 1.25rem' }}>
          <h2 style={{ margin: '0 0 0.875rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Quality radar</h2>
          <ResponsiveContainer width="100%" height={220}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }} />
              <Radar dataKey="value" stroke="#818cf8" fill="#818cf8" fillOpacity={0.18} strokeWidth={2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        {/* Bar chart per FHIR resource */}
        <div style={{ ...card, padding: '1.125rem 1.25rem' }}>
          <h2 style={{ margin: '0 0 0.875rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Mapping coverage by FHIR resource</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' }} unit="%" axisLine={false} tickLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: 'var(--ds-text-secondary)' }} width={135} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="accuracy" radius={[0, 4, 4, 0]}>
                {barData.map((_, i) => <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Targets vs actual */}
      <div className="ds-animate ds-animate-d3" style={{ ...card, padding: '1.125rem 1.25rem' }}>
        <h2 style={{ margin: '0 0 0.875rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Targets vs current</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {[
            { label: 'Schema mapping accuracy', target: 99,   actual: Math.round((metrics?.mapping_accuracy  ?? 0) * 100) },
            { label: 'Sync success rate',        target: 99.5, actual: Math.round((metrics?.sync_success_rate ?? 0) * 100) },
            { label: 'Data completeness',        target: 95,   actual: Math.round((metrics?.completeness_score ?? 0) * 100) },
            { label: 'Error rate',               target: 1,    actual: Math.round((metrics?.error_rate ?? 0) * 100), invert: true },
          ].map((row) => {
            const met = row.invert ? row.actual <= row.target : row.actual >= row.target;
            return (
              <div key={row.label} style={{ display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                <div style={{ width: 180, fontSize: '0.8125rem', color: 'var(--ds-text-secondary)', flexShrink: 0 }}>{row.label}</div>
                <div style={{ flex: 1, height: 6, background: 'var(--ds-table-border)', borderRadius: 999, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.min(row.actual, 100)}%`, background: met ? 'var(--ds-accent-green)' : 'var(--ds-accent-orange)', borderRadius: 999, transition: 'width 0.7s ease' }} />
                </div>
                <div style={{ width: 48, textAlign: 'right', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)', flexShrink: 0 }}>{row.actual}%</div>
                <div style={{ width: 88, fontSize: '0.6875rem', color: 'var(--ds-text-muted)', flexShrink: 0 }}>target: {row.target}%</div>
                {met
                  ? <CheckCircle2 style={{ width: 14, height: 14, color: 'var(--ds-accent-green)', flexShrink: 0 }} />
                  : <AlertTriangle style={{ width: 14, height: 14, color: 'var(--ds-accent-orange)', flexShrink: 0 }} />
                }
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default DataQualityPage;
