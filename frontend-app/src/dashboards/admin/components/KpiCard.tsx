/**
 * KpiCard — Theme-aware KPI metric card.
 * Uses --ds-* CSS variables so it correctly adapts to dark AND light mode.
 */
import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';

export interface KpiCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  accent: string;
  trend?: { value: string; up: boolean };
  period?: string;
  loading?: boolean;
}

/* Accent → solid icon color mapping (same in both themes) */
const ICON_COLOR: Record<string, string> = {
  blue:    '#60a5fa', teal:   '#2dd4bf', emerald: '#34d399',
  amber:   '#fbbf24', indigo: '#818cf8', rose:    '#fb7185',
  green:   '#4ade80', purple: '#c084fc', cyan:    '#22d3ee',
};

/* Accent → rgba icon badge background */
const ICON_BG: Record<string, string> = {
  blue:    'rgba(59,130,246,0.15)',   teal:    'rgba(20,184,166,0.15)',
  emerald: 'rgba(16,185,129,0.15)',   amber:   'rgba(245,158,11,0.15)',
  indigo:  'rgba(99,102,241,0.18)',   rose:    'rgba(244,63,94,0.15)',
  green:   'rgba(34,197,94,0.15)',    purple:  'rgba(192,132,252,0.18)',
  cyan:    'rgba(34,211,238,0.15)',
};

const KpiCard: React.FC<KpiCardProps> = React.memo(
  ({ label, value, subtitle, icon, accent, trend, period, loading }) => {
    const iconColor = ICON_COLOR[accent] ?? '#60a5fa';
    const iconBg    = ICON_BG[accent]    ?? 'rgba(59,130,246,0.15)';

    if (loading) {
      return (
        <div style={{
          background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)',
          borderRadius: '1rem', padding: '1.25rem', animation: 'ds-pulse 1.8s ease-in-out infinite',
        }}>
          <div style={{ width: 44, height: 44, background: 'rgba(255,255,255,0.05)', borderRadius: '0.75rem', marginBottom: '1rem' }} />
          <div style={{ width: 80, height: 28, background: 'rgba(255,255,255,0.05)', borderRadius: '0.375rem', marginBottom: '0.5rem' }} />
          <div style={{ width: 120, height: 12, background: 'rgba(255,255,255,0.03)', borderRadius: '0.25rem' }} />
        </div>
      );
    }

    return (
      <div style={{
        background: 'var(--ds-card-bg)',
        border: '1px solid var(--ds-card-border)',
        borderRadius: '1rem',
        padding: '1.25rem',
        boxShadow: 'var(--ds-card-shadow)',
        transition: 'border-color 0.28s, box-shadow 0.28s, transform 0.25s',
        cursor: 'default',
      }}
        onMouseEnter={e => {
          (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-hover-border)';
          (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
          (e.currentTarget as HTMLElement).style.boxShadow = 'var(--ds-card-hover-shadow)';
        }}
        onMouseLeave={e => {
          (e.currentTarget as HTMLElement).style.borderColor = 'var(--ds-card-border)';
          (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
          (e.currentTarget as HTMLElement).style.boxShadow = 'var(--ds-card-shadow)';
        }}
      >
        {/* Top: icon + trend */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.875rem' }}>
          <div style={{ width: 44, height: 44, background: iconBg, borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, transition: 'transform 0.25s' }}>
            <span style={{ color: iconColor, display: 'flex' }}>{icon}</span>
          </div>
          {trend && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', fontWeight: 700, padding: '0.25rem 0.5rem', borderRadius: '0.5rem', background: trend.up ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)', color: trend.up ? '#34d399' : '#f87171' }}>
              {trend.up ? <TrendingUp style={{ width: 11, height: 11 }} /> : <TrendingDown style={{ width: 11, height: 11 }} />}
              {trend.value}
            </div>
          )}
        </div>

        {/* Label */}
        <div style={{ fontSize: '0.6875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ds-text-muted)', marginBottom: '0.375rem' }}>{label}</div>

        {/* Value */}
        <div style={{ fontSize: '1.625rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1, marginBottom: '0.25rem' }}>{value}</div>

        {/* Subtitle + period */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {subtitle && <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{subtitle}</span>}
          {period && (
            <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '0.375rem', background: iconBg, color: iconColor }}>
              {period}
            </span>
          )}
        </div>
      </div>
    );
  },
);

KpiCard.displayName = 'KpiCard';
export default KpiCard;
