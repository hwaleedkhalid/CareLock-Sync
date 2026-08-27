/** AdminCharts — theme-aware charts panel using ds-* tokens. All logic preserved. */
import React, { useMemo, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { BarChart3 } from 'lucide-react';
import type { DashboardStats, SystemMetrics } from '../../../shared/types';
import type { SyncHistoryEntry } from '../hooks/useDashboardData';

interface Props { stats: DashboardStats | null; systemMetrics: SystemMetrics | null; syncHistory: SyncHistoryEntry[]; loading: boolean }
type Period = 'Weekly' | 'Monthly' | 'Yearly';

function buildFromHistory(history: SyncHistoryEntry[], period: Period) {
  const now = new Date();
  const getBucket = (iso: string) => {
    const d = new Date(iso);
    if (period === 'Weekly') return d.toLocaleDateString(undefined, { weekday: 'short' });
    if (period === 'Monthly') return d.toLocaleDateString(undefined, { month: 'short' });
    return String(d.getFullYear());
  };
  const labels: string[] = [];
  if (period === 'Weekly') { for (let i = 6; i >= 0; i--) { const d = new Date(now); d.setDate(d.getDate() - i); labels.push(d.toLocaleDateString(undefined, { weekday: 'short' })); } }
  else if (period === 'Monthly') { const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']; for (let i = 11; i >= 0; i--) { const d = new Date(now); d.setMonth(d.getMonth() - i); labels.push(m[d.getMonth()]); } }
  else { for (let i = 4; i >= 0; i--) labels.push(String(now.getFullYear() - i)); }
  const buckets: Record<string, { total: number; newRec: number; updated: number }> = {};
  labels.forEach(l => { buckets[l] = { total: 0, newRec: 0, updated: 0 }; });
  history.forEach(h => {
    const b = getBucket(h.started_at); if (!buckets[b]) return;
    const s = h.stats ?? {};
    buckets[b].total   += 1;
    buckets[b].newRec  += (s.patients_synced ?? s.total_synced ?? s.inserted ?? 0);
    buckets[b].updated += (s.encounters_synced ?? s.updated ?? 0);
  });
  return labels.map(l => ({ name: l, 'Total Syncs': buckets[l]?.total ?? 0, 'New Records': buckets[l]?.newRec ?? 0, 'Updated': buckets[l]?.updated ?? 0 }));
}

function buildFromStats(stats: DashboardStats | null, period: Period) {
  const WL = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const ML = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const YL = ['2022','2023','2024','2025','2026'];
  const WC = [0.72,0.88,0.95,0.91,0.85,0.42,0.30];
  const MC = [0.55,0.58,0.65,0.70,0.72,0.75,0.80,0.85,0.88,0.90,0.92,0.95];
  const YC = [0.40,0.55,0.70,0.85,0.95];
  const labels = period === 'Weekly' ? WL : period === 'Monthly' ? ML : YL;
  const curve  = period === 'Weekly' ? WC : period === 'Monthly' ? MC : YC;
  const base = stats ? { patients: stats.total_patients, encounters: stats.total_encounters, observations: stats.total_observations } : { patients: 0, encounters: 0, observations: 0 };
  const div = labels.length;
  return labels.map((label, i) => ({ name: label, 'Total Syncs': Math.round((base.patients / div) * curve[i]), 'New Records': Math.round((base.encounters / div) * curve[i] * 0.8), 'Updated': Math.round((base.observations / div) * curve[i] * 0.6) }));
}

const LEGEND = [{ value: 'Total Syncs', color: '#22c55e' }, { value: 'New Records', color: '#f43f5e' }, { value: 'Updated', color: '#3b82f6' }];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;
  return (
    <div style={{ background: 'var(--ds-surface-2)', border: '1px solid var(--ds-border)', borderRadius: '0.75rem', padding: '0.75rem 1rem', boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
      <p style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-primary)', marginBottom: '0.5rem' }}>{label}</p>
      {payload.map((e: any, i: number) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem' }}>
          <div style={{ width: 8, height: 8, borderRadius: '2px', background: e.color, flexShrink: 0 }} />
          <span style={{ color: 'var(--ds-text-muted)' }}>{e.name}:</span>
          <span style={{ color: 'var(--ds-text-primary)', fontWeight: 700 }}>{e.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
};

const AdminCharts: React.FC<Props> = React.memo(({ stats, systemMetrics: _sm, syncHistory, loading }) => {
  const [period, setPeriod] = useState<Period>('Weekly');
  const chartData = useMemo(() => syncHistory.length > 0 ? buildFromHistory(syncHistory, period) : buildFromStats(stats, period), [stats, syncHistory, period]);
  const isLive = syncHistory.length > 0;

  if (loading) {
    return (
      <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '1.25rem', animation: 'ds-pulse 1.8s ease-in-out infinite' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
          <div style={{ width: 160, height: 16, background: 'rgba(255,255,255,0.05)', borderRadius: '0.375rem' }} />
          <div style={{ display: 'flex', gap: '0.5rem' }}>{[1,2,3].map(i => <div key={i} style={{ width: 56, height: 28, background: 'rgba(255,255,255,0.05)', borderRadius: '0.5rem' }} />)}</div>
        </div>
        <div style={{ width: '100%', height: 280, background: 'rgba(255,255,255,0.02)', borderRadius: '0.75rem' }} />
      </div>
    );
  }

  return (
    <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', padding: '1.25rem' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 style={{ width: 14, height: 14, color: '#60a5fa' }} />Sync Trends
          </h2>
          {isLive && <span style={{ fontSize: '0.625rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)' }}>Live</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', background: 'var(--ds-surface-2)', borderRadius: '0.5rem', padding: '0.2rem', border: '1px solid var(--ds-border)' }}>
          {(['Weekly', 'Monthly', 'Yearly'] as Period[]).map(p => (
            <button key={p} onClick={() => setPeriod(p)} style={{ fontSize: '0.75rem', fontWeight: 600, padding: '0.375rem 0.75rem', borderRadius: '0.375rem', border: 'none', cursor: 'pointer', transition: 'all 0.2s', background: period === p ? '#2563eb' : 'transparent', color: period === p ? '#fff' : 'var(--ds-text-muted)', boxShadow: period === p ? '0 1px 4px rgba(37,99,235,0.4)' : 'none' }}>
              {p}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', marginBottom: '0.5rem' }}>
        {LEGEND.map(item => (
          <div key={item.value} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
            <span style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--ds-text-muted)' }}>{item.value}</span>
          </div>
        ))}
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} barGap={4} barCategoryGap="20%">
          <CartesianGrid strokeDasharray="3 3" stroke="var(--ds-table-border)" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' } as any} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: 'var(--ds-text-muted)' } as any} axisLine={false} tickLine={false} tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v)} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="Total Syncs" fill="#22c55e" radius={[4, 4, 0, 0]} maxBarSize={32} />
          <Bar dataKey="New Records" fill="#f43f5e" radius={[4, 4, 0, 0]} maxBarSize={32} />
          <Bar dataKey="Updated"     fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={32} />
        </BarChart>
      </ResponsiveContainer>

      {!isLive && <p style={{ textAlign: 'center', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.5rem' }}>No sync history yet — run a sync to see live data</p>}
    </div>
  );
});

AdminCharts.displayName = 'AdminCharts';
export default AdminCharts;
