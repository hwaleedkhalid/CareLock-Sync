/**
 * pages/PatientsPage.tsx — Dark glassmorphism, full ds-* design system.
 * Used by /hospital/patients and /doctor/patients.
 */
import React, { useEffect, useState } from 'react';
import { patientsApi } from '../shared/services/api';
import type { FHIRPatient } from '../shared/types';
import { Search, User, Loader2 } from 'lucide-react';

const PatientsPage: React.FC = () => {
  const [patients, setPatients] = useState<FHIRPatient[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    patientsApi.fhirList(0, 50)
      .then(data => setPatients(data.patients ?? data ?? []))
      .catch(() => setPatients([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = patients.filter(p =>
    p.family_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.given_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.source_patient_id?.toLowerCase().includes(searchTerm.toLowerCase()),
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate">
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', margin: 0, letterSpacing: '-0.02em' }}>Patient Management</h1>
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>FHIR patient records from central database</p>
      </div>

      {/* Search */}
      <div className="ds-animate ds-animate-d1" style={{ ...card, padding: '0.875rem 1rem' }}>
        <div style={{ position: 'relative' }}>
          <Search style={{ width: 14, height: 14, color: 'var(--ds-text-muted)', position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
          <input
            type="text"
            placeholder="Search patients by name or ID…"
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{ width: '100%', paddingLeft: '2.25rem', paddingRight: '1rem', paddingTop: '0.5rem', paddingBottom: '0.5rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.625rem', fontSize: '0.8125rem', color: 'var(--ds-text-primary)', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit', transition: 'border-color 0.2s, box-shadow 0.2s' }}
            onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.18)'; }}
            onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; e.target.style.boxShadow = 'none'; }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="ds-animate ds-animate-d2" style={{ ...card, overflow: 'hidden' }}>
        <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '120px 1fr 110px 90px 100px', gap: '0.5rem', padding: '0.625rem 1.25rem' }}>
          <span>Patient ID</span><span>Name</span><span>Birth Date</span><span>Gender</span><span>Status</span>
        </div>

        <div className="ds-scroll" style={{ maxHeight: 540, overflowY: 'auto' }}>
          {filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '4rem 1rem', color: 'var(--ds-text-muted)' }}>
              <User style={{ width: 40, height: 40, margin: '0 auto 0.75rem', opacity: 0.25 }} />
              <p style={{ fontSize: '0.875rem', margin: 0 }}>No patients found</p>
            </div>
          ) : filtered.map(p => (
            <div key={p.id} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: '120px 1fr 110px 90px 100px', gap: '0.5rem', alignItems: 'center', padding: '0.75rem 1.25rem' }}>
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', fontWeight: 700, color: 'var(--ds-text-muted)' }}>{p.source_patient_id}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg,#3b82f6,#6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, flexShrink: 0 }}>
                  {`${p.family_name?.[0] ?? ''}${p.given_name?.[0] ?? ''}`.toUpperCase()}
                </div>
                <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {p.family_name}{p.given_name ? `, ${p.given_name}` : ''}
                </span>
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{p.birth_date ?? 'N/A'}</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-secondary)', textTransform: 'capitalize' }}>{p.gender ?? 'Unknown'}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: p.active ? 'var(--ds-status-active-bg)' : 'var(--ds-table-head-bg)', color: p.active ? 'var(--ds-status-active-text)' : 'var(--ds-text-muted)', border: `1px solid ${p.active ? 'rgba(16,185,129,0.25)' : 'var(--ds-table-border)'}`, width: 'fit-content' }}>
                {p.active ? 'Active' : 'Inactive'}
              </span>
            </div>
          ))}
        </div>
      </div>

      <p style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', textAlign: 'right', margin: 0 }}>
        Showing {filtered.length} of {patients.length} patients
      </p>
    </div>
  );
};

export default PatientsPage;
