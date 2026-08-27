/**
 * pages/DashboardPage.tsx — Legacy dashboard, dark glassmorphism.
 * Accessed via /dashboard through DashboardLayout (legacy route).
 */
import React, { useEffect, useState } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import StatCard from '../components/StatCard';
import LoadingSpinner from '../components/LoadingSpinner';
import { dashboardApi } from '../shared/services/api';
import { Users, FileText, Activity, Pill, Clock } from 'lucide-react';
import type { DashboardStats } from '../types';

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi.getStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <DashboardLayout><LoadingSpinner /></DashboardLayout>;

  return (
    <DashboardLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif" }}>
        {/* Header */}
        <div className="ds-animate">
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>Dashboard Overview</h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>Welcome to CareLock Sync</p>
        </div>

        {/* Stats */}
        <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: '1rem' }}>
          <StatCard title="Total Patients"      value={stats?.total_patients      ?? 0} icon={Users}    color="blue"   />
          <StatCard title="Total Encounters"    value={stats?.total_encounters    ?? 0} icon={FileText}  color="green"  />
          <StatCard title="Total Observations"  value={stats?.total_observations  ?? 0} icon={Activity}  color="purple" />
          <StatCard title="Total Medications"   value={stats?.total_medications   ?? 0} icon={Pill}      color="orange" />
        </div>

        {/* Recent activity */}
        <div className="ds-animate ds-animate-d2" style={{ background: 'var(--ds-card-bg)', backdropFilter: 'var(--ds-card-blur)', WebkitBackdropFilter: 'var(--ds-card-blur)' as any, border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', overflow: 'hidden' }}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)' }}>
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Clock style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} />Recent Activity
            </h2>
          </div>
          <div style={{ padding: '1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.625rem 0.875rem', background: 'var(--ds-status-syncing-bg)', borderRadius: '0.625rem', border: '1px solid rgba(59,130,246,0.20)' }}>
              <span style={{ fontSize: '0.8125rem', color: 'var(--ds-text-secondary)' }}>Last sync completed</span>
              <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-status-syncing-text)' }}>{stats?.recent_sync ?? 'Never'}</span>
            </div>
            <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--ds-text-muted)' }}>
              <p style={{ margin: 0, fontSize: '0.875rem' }}>System running smoothly ✓</p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default DashboardPage;
