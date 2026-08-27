/**
 * pages/EncountersPage.tsx — Dark glassmorphism, full ds-* design system.
 * Used by /hospital/encounters and /doctor/encounters.
 */
import React, { useEffect, useState } from 'react';
import { encountersApi } from '../shared/services/api';
import { FileText, Search, Loader2 } from 'lucide-react';
import type { Encounter } from '../types';

const STATUS_MAP: Record<string, { bg: string; color: string; border: string }> = {
  finished:    { bg: 'var(--ds-status-active-bg)',  color: 'var(--ds-status-active-text)',  border: 'rgba(16,185,129,0.25)' },
  'in-progress': { bg: 'var(--ds-status-syncing-bg)', color: 'var(--ds-status-syncing-text)', border: 'rgba(59,130,246,0.25)' },
  cancelled:   { bg: 'var(--ds-status-error-bg)',   color: 'var(--ds-status-error-text)',   border: 'rgba(239,68,68,0.25)' },
  planned:     { bg: 'var(--ds-status-pending-bg)', color: 'var(--ds-status-pending-text)', border: 'rgba(245,158,11,0.25)' },
};

const EncountersPage: React.FC = () => {
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    encountersApi.list()
      .then(setEncounters)
      .catch(() => setEncounters([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = encounters.filter(e =>
    e.encounter_id?.toLowerCase().includes(search.toLowerCase()) ||
    e.encounter_type?.toLowerCase().includes(search.toLowerCase()) ||
    e.status?.toLowerCase().includes(search.toLowerCase()),
  );

  const card: React.CSSProperties = {
    background: 'var(--ds-card-bg)',
    backdropFilter: 'var(--ds-card-blur)',
    WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
    border: '1px solid var(--ds-card-border)',
    borderRadius: '1rem',
    boxShadow: 'var(--ds-card-shadow)',
  };

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '16rem' }}>
      <Loader2 style={{ width: 32, height: 32, color: '#818cf8', animation: 'spin 0.8s linear infinite' }} />
    </div>
  );

  const COLS = ['Encounter ID', 'Patient ID', 'Type', 'Start', 'End', 'Status'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate">
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FileText style={{ width: 20, height: 20, color: '#60a5fa' }} />Encounters
        </h1>
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
          Hospital visit records synced from source database
        </p>
      </div>

      {/* Search */}
      <div className="ds-animate ds-animate-d1" style={{ ...card, padding: '0.875rem 1rem' }}>
        <div style={{ position: 'relative' }}>
          <Search style={{ width: 14, height: 14, color: 'var(--ds-text-muted)', position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
          <input
            type="text"
            placeholder="Search by encounter ID, type, or status…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', paddingLeft: '2.25rem', paddingRight: '1rem', paddingTop: '0.5rem', paddingBottom: '0.5rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.625rem', fontSize: '0.8125rem', color: 'var(--ds-text-primary)', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', transition: 'border-color 0.2s, box-shadow 0.2s' }}
            onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.18)'; }}
            onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; e.target.style.boxShadow = 'none'; }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="ds-animate ds-animate-d2" style={{ ...card, overflow: 'hidden' }}>
        {/* Head */}
        <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '2fr 80px 1fr 110px 110px 100px', gap: '0.5rem', padding: '0.625rem 1.25rem' }}>
          {COLS.map(h => <span key={h}>{h}</span>)}
        </div>

        {/* Rows */}
        <div className="ds-scroll" style={{ maxHeight: 520, overflowY: 'auto' }}>
          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '4rem 1rem', color: 'var(--ds-text-muted)' }}>
              <FileText style={{ width: 40, height: 40, margin: '0 auto 0.75rem', opacity: 0.25 }} />
              <p style={{ fontSize: '0.875rem', margin: 0 }}>No encounters found</p>
            </div>
          ) : filtered.map(enc => {
            const s = STATUS_MAP[enc.status] ?? { bg: 'var(--ds-table-head-bg)', color: 'var(--ds-text-muted)', border: 'var(--ds-table-border)' };
            return (
              <div key={enc.id} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: '2fr 80px 1fr 110px 110px 100px', gap: '0.5rem', alignItems: 'center', padding: '0.75rem 1.25rem' }}>
                <span style={{ fontSize: '0.75rem', fontFamily: 'monospace', fontWeight: 700, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{enc.encounter_id}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{enc.patient_id}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-secondary)' }}>{enc.encounter_type || 'N/A'}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{enc.start_date ? new Date(enc.start_date).toLocaleDateString() : '—'}</span>
                <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{enc.end_date ? new Date(enc.end_date).toLocaleDateString() : '—'}</span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: s.bg, color: s.color, border: `1px solid ${s.border}`, width: 'fit-content', textTransform: 'capitalize' }}>
                  {enc.status}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', textAlign: 'right', margin: 0 }}>
        Showing {filtered.length} of {encounters.length} encounters
      </p>
    </div>
  );
};

export default EncountersPage;
