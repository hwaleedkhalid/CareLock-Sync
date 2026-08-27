/** TenantTable — theme-aware hospital list panel using ds-* tokens. */
import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Search, ChevronRight, Users } from 'lucide-react';

export interface TenantRow { id: number; name: string; code: string; status: 'active' | 'inactive'; patients: number; lastSync: string }

interface Props { tenants: TenantRow[]; loading: boolean }

const AVATAR_COLORS = [
  'linear-gradient(135deg,#3b82f6,#2563eb)', 'linear-gradient(135deg,#10b981,#059669)',
  'linear-gradient(135deg,#8b5cf6,#7c3aed)', 'linear-gradient(135deg,#f59e0b,#d97706)',
  'linear-gradient(135deg,#f43f5e,#e11d48)', 'linear-gradient(135deg,#06b6d4,#0891b2)',
  'linear-gradient(135deg,#6366f1,#4f46e5)', 'linear-gradient(135deg,#14b8a6,#0d9488)',
];

const TenantTable: React.FC<Props> = React.memo(({ tenants, loading }) => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();
    return q ? tenants.filter(t => t.name.toLowerCase().includes(q) || t.code.toLowerCase().includes(q)) : tenants;
  }, [tenants, search]);

  if (loading) {
    return (
      <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.25rem' }}>
          <div style={{ width: 120, height: 16, background: 'rgba(255,255,255,0.05)', borderRadius: '0.375rem', marginBottom: '0.75rem' }} />
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1.25rem', borderTop: '1px solid var(--ds-table-border)', animation: 'ds-pulse 1.8s ease-in-out infinite' }}>
            <div style={{ width: 38, height: 38, background: 'rgba(255,255,255,0.05)', borderRadius: '0.75rem', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ width: 130, height: 11, background: 'rgba(255,255,255,0.05)', borderRadius: '0.25rem', marginBottom: '0.4rem' }} />
              <div style={{ width: 80, height: 9, background: 'rgba(255,255,255,0.03)', borderRadius: '0.25rem' }} />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
        <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Building2 style={{ width: 14, height: 14, color: '#2dd4bf' }} />Onboarded Hospitals
        </h2>
        <div style={{ position: 'relative', flexShrink: 0 }}>
          <Search style={{ position: 'absolute', left: '0.5rem', top: '50%', transform: 'translateY(-50%)', width: 12, height: 12, color: 'var(--ds-text-muted)' }} />
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search…"
            style={{ paddingLeft: '1.625rem', paddingRight: '0.625rem', paddingTop: '0.25rem', paddingBottom: '0.25rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-primary)', outline: 'none', width: 120, fontFamily: 'inherit' }}
          />
        </div>
      </div>

      {/* Table head */}
      <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '2.5rem 1fr 5rem 5rem 5.5rem', gap: '0.75rem', padding: '0.5rem 1.25rem', alignItems: 'center' }}>
        <span /><span>Hospital</span><span>Patients</span><span>Last Sync</span><span>Status</span>
      </div>

      {/* Rows */}
      {filtered.length === 0
        ? <div style={{ padding: '2rem', textAlign: 'center', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>No hospitals found</div>
        : filtered.map((t, i) => (
          <div key={t.id} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: '2.5rem 1fr 5rem 5rem 5.5rem', gap: '0.75rem', padding: '0.75rem 1.25rem', alignItems: 'center', cursor: 'pointer' }}
            onClick={() => navigate('/admin/tenants')}>
            <div style={{ width: 36, height: 36, borderRadius: '0.75rem', background: AVATAR_COLORS[i % AVATAR_COLORS.length], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.625rem', fontWeight: 800, color: '#fff', letterSpacing: '0.02em', flexShrink: 0 }}>
              {t.code}
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>#{t.id}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--ds-text-secondary)' }}>
              <Users style={{ width: 11, height: 11 }} />{t.patients.toLocaleString()}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{t.lastSync}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: t.status === 'active' ? '#34d399' : 'var(--ds-text-muted)', flexShrink: 0 }} />
              <span className={`ds-chip ${t.status === 'active' ? 'ds-chip-active' : 'ds-chip-pending'}`}>{t.status}</span>
            </div>
          </div>
        ))
      }

      <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid var(--ds-table-border)', display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={() => navigate('/admin/tenants')} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-text-link)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          Manage all <ChevronRight style={{ width: 12, height: 12 }} />
        </button>
      </div>
    </div>
  );
});

TenantTable.displayName = 'TenantTable';
export default TenantTable;
