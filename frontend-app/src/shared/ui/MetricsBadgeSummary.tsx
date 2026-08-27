import React from 'react';
import { Shield, Brain, Zap, Building2 } from 'lucide-react';

const METRICS = [
  { icon: Shield,    label: 'Security',    value: '100%',  sub: 'RLS verified',   color: '#34d399', bg: 'rgba(16,185,129,0.15)'  },
  { icon: Brain,     label: 'AI accuracy', value: '99.4%', sub: 'mapping',        color: '#818cf8', bg: 'rgba(99,102,241,0.15)'  },
  { icon: Zap,       label: 'Avg latency', value: '12ms',  sub: 'API response',   color: '#60a5fa', bg: 'rgba(59,130,246,0.15)'  },
  { icon: Building2, label: 'Tenants',     value: '3',     sub: 'hospitals live', color: '#c084fc', bg: 'rgba(192,132,252,0.15)' },
];

const MetricsBadgeSummary: React.FC = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
    {METRICS.map(m => (
      <div key={m.label} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.25rem 0.625rem', borderRadius: '0.625rem', border: '1px solid var(--ds-border)', background: 'var(--ds-surface-2)', fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, borderRadius: '0.3rem', background: m.bg }}>
          <m.icon style={{ width: 11, height: 11, color: m.color }} />
        </div>
        <span>{m.label}:</span>
        <span style={{ color: 'var(--ds-text-primary)', fontWeight: 700 }}>{m.value}</span>
        <span style={{ opacity: 0.6, fontWeight: 400 }}>({m.sub})</span>
      </div>
    ))}
  </div>
);

export default MetricsBadgeSummary;
