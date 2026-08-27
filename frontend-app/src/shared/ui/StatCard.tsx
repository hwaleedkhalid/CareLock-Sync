import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { value: number; isPositive: boolean };
  color?: 'blue' | 'green' | 'purple' | 'orange' | 'red';
}

const ACCENT: Record<string, { icon: string; bg: string }> = {
  blue:   { icon: 'rgba(59,130,246,0.85)',  bg: 'rgba(59,130,246,0.15)' },
  green:  { icon: 'rgba(16,185,129,0.85)',  bg: 'rgba(16,185,129,0.15)' },
  purple: { icon: 'rgba(139,92,246,0.85)',  bg: 'rgba(139,92,246,0.18)' },
  orange: { icon: 'rgba(249,115,22,0.85)',  bg: 'rgba(249,115,22,0.15)' },
  red:    { icon: 'rgba(239,68,68,0.85)',   bg: 'rgba(239,68,68,0.15)'  },
};

const StatCard: React.FC<StatCardProps> = ({ title, value, icon: Icon, trend, color = 'blue' }) => {
  const a = ACCENT[color];
  return (
    <div className="ds-card" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ flex: 1 }}>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', margin: '0 0 0.5rem' }}>{title}</p>
          <p style={{ fontSize: '1.875rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: '0 0 0.375rem', letterSpacing: '-0.02em' }}>{value}</p>
          {trend && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', fontWeight: 600, color: trend.isPositive ? '#34d399' : '#f87171' }}>
              {trend.isPositive ? <TrendingUp style={{ width: 12, height: 12 }} /> : <TrendingDown style={{ width: 12, height: 12 }} />}
              {Math.abs(trend.value)}%
            </div>
          )}
        </div>
        <div className="ds-icon-badge" style={{ background: a.bg, marginLeft: '0.75rem' }}>
          <Icon style={{ width: 20, height: 20, color: a.icon }} />
        </div>
      </div>
    </div>
  );
};

export default StatCard;
