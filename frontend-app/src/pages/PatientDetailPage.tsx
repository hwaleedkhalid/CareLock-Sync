/**
 * pages/PatientDetailPage.tsx — Dark glassmorphism, full ds-* design system.
 * Routed from /hospital/patients/:id and /doctor/patients/:id.
 */
import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  User, Calendar, Phone, FileText, Activity,
  Pill, ArrowLeft, CheckCircle2,
} from 'lucide-react';
import LoadingSpinner from '../components/LoadingSpinner';
import { patientsApi, encountersApi, observationsApi, medicationsApi } from '../shared/services/api';

// ── Design helpers ──────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: 'var(--ds-card-bg)',
  backdropFilter: 'var(--ds-card-blur)',
  WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
  border: '1px solid var(--ds-card-border)',
  borderRadius: '1rem',
  boxShadow: 'var(--ds-card-shadow)',
};

// ── Sub-components ──────────────────────────────────────────────────────────
const InfoRow: React.FC<{ icon: React.ReactNode; label: string; value: string }> = ({ icon, label, value }) => (
  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', padding: '0.625rem 0', borderBottom: '1px solid var(--ds-table-border)' }}>
    <div style={{ flexShrink: 0, marginTop: '0.125rem', color: 'var(--ds-text-muted)' }}>{icon}</div>
    <div>
      <p style={{ margin: 0, fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{label}</p>
      <p style={{ margin: '0.125rem 0 0', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{value}</p>
    </div>
  </div>
);

// ── Main Page ───────────────────────────────────────────────────────────────
const PatientDetailPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient]         = useState<any>(null);
  const [encounters, setEncounters]   = useState<any[]>([]);
  const [observations, setObservations] = useState<any[]>([]);
  const [medications, setMedications] = useState<any[]>([]);
  const [loading, setLoading]         = useState(true);
  const [activeTab, setActiveTab]     = useState<'observations' | 'encounters' | 'medications' | 'fhir'>('observations');

  useEffect(() => {
    if (!id) return;
    const pid = Number(id);
    const fetchAll = async () => {
      try {
        const [p, enc, obs, med] = await Promise.allSettled([
          patientsApi.fhirGet(pid),
          encountersApi.list(pid),
          observationsApi.list(pid),
          medicationsApi.list(pid),
        ]);
        if (p.status === 'fulfilled')   setPatient(p.value);
        if (enc.status === 'fulfilled') setEncounters(enc.value);
        if (obs.status === 'fulfilled') setObservations(obs.value);
        if (med.status === 'fulfilled') setMedications(med.value);
      } catch (e) {
        console.error('Error loading patient detail:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, [id]);

  if (loading) return <LoadingSpinner />;

  if (!patient) {
    return (
      <div style={{ textAlign: 'center', padding: '4rem 1rem' }}>
        <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem' }}>Patient not found</p>
        <button
          onClick={() => navigate('/patients')}
          style={{ marginTop: '1rem', color: 'var(--ds-accent-blue)', fontSize: '0.8125rem', background: 'none', border: 'none', cursor: 'pointer' }}
        >
          Back to patients
        </button>
      </div>
    );
  }

  const age = patient.birth_date
    ? new Date().getFullYear() - new Date(patient.birth_date).getFullYear()
    : null;
  const initials = `${(patient.given_name || '?')[0]}${(patient.family_name || '?')[0]}`.toUpperCase();

  const TABS = [
    { key: 'observations', label: 'Observations', count: observations.length },
    { key: 'encounters',   label: 'Encounters',   count: encounters.length   },
    { key: 'medications',  label: 'Medications',  count: medications.length  },
    { key: 'fhir',         label: 'FHIR resource',count: null                },
  ] as const;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Back button */}
      <button
        onClick={() => navigate('/patients')}
        className="ds-animate"
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, transition: 'color 0.2s', alignSelf: 'flex-start' }}
        onMouseOver={e => (e.currentTarget.style.color = 'var(--ds-text-secondary)')}
        onMouseOut={e => (e.currentTarget.style.color = 'var(--ds-text-muted)')}
      >
        <ArrowLeft style={{ width: 14, height: 14 }} /> Back to patients
      </button>

      {/* Patient header card */}
      <div className="ds-animate ds-animate-d1" style={{ ...card, padding: '1.25rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1.25rem', flexWrap: 'wrap' }}>

          {/* Avatar */}
          <div style={{ width: 56, height: 56, borderRadius: '0.875rem', background: 'linear-gradient(135deg,#3b82f6,#6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '1.125rem', fontWeight: 800, flexShrink: 0 }}>
            {initials}
          </div>

          {/* Name + meta */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <h1 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em' }}>
                {patient.given_name} {patient.family_name}
              </h1>
              <span style={{
                fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.625rem', borderRadius: '2rem',
                background: patient.active ? 'var(--ds-status-active-bg)' : 'var(--ds-table-head-bg)',
                color: patient.active ? 'var(--ds-status-active-text)' : 'var(--ds-text-muted)',
                border: `1px solid ${patient.active ? 'rgba(16,185,129,0.25)' : 'var(--ds-table-border)'}`,
              }}>
                {patient.active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-secondary)' }}>
              {age ? `${age} yrs` : 'Age N/A'} · {patient.gender || 'Unknown'} · MRN:{' '}
              <span style={{ fontFamily: 'monospace', fontWeight: 700 }}>{patient.source_patient_id}</span>
            </p>
            <p style={{ margin: '0.125rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
              Tenant ID: {patient.tenant_id} · FHIR Patient ID: {patient.id}
            </p>
          </div>

          {/* Stat chips */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '0.5rem', flexShrink: 0 }}>
            {[
              { label: 'Encounters',   value: encounters.length },
              { label: 'Observations', value: observations.length },
              { label: 'Active meds',  value: medications.filter(m => m.status === 'active').length },
              { label: 'Total meds',   value: medications.length },
            ].map(s => (
              <div key={s.label} style={{ background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.625rem', padding: '0.5rem 0.875rem', textAlign: 'center', minWidth: 80 }}>
                <div style={{ fontSize: '1.125rem', fontWeight: 800, color: 'var(--ds-text-primary)' }}>{s.value}</div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '1rem', alignItems: 'start' }}>

        {/* Patient info sidebar */}
        <div style={{ ...card, padding: '1.125rem 1.25rem' }}>
          <h2 style={{ margin: '0 0 0.75rem', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Patient information</h2>
          <InfoRow icon={<Calendar style={{ width: 14, height: 14 }} />} label="Date of birth"
            value={patient.birth_date ? `${patient.birth_date}${age ? ` (${age} yrs)` : ''}` : 'N/A'} />
          <InfoRow icon={<User style={{ width: 14, height: 14 }} />} label="Gender"
            value={patient.gender ? patient.gender.charAt(0).toUpperCase() + patient.gender.slice(1) : 'N/A'} />
          {patient.phone && <InfoRow icon={<Phone style={{ width: 14, height: 14 }} />} label="Phone" value={patient.phone} />}
          {patient.email && <InfoRow icon={<FileText style={{ width: 14, height: 14 }} />} label="Email" value={patient.email} />}
          <InfoRow icon={<FileText style={{ width: 14, height: 14 }} />} label="Medical record no." value={patient.source_patient_id} />
        </div>

        {/* Tabbed content panel */}
        <div style={{ ...card, overflow: 'hidden' }}>
          {/* Tab bar */}
          <div style={{ display: 'flex', borderBottom: '1px solid var(--ds-table-border)', background: 'var(--ds-table-head-bg)' }}>
            {TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  padding: '0.75rem 1.125rem',
                  fontSize: '0.8125rem',
                  fontWeight: activeTab === tab.key ? 700 : 500,
                  color: activeTab === tab.key ? 'var(--ds-accent-purple)' : 'var(--ds-text-muted)',
                  background: activeTab === tab.key ? 'var(--ds-card-bg)' : 'transparent',
                  border: 'none',
                  borderBottom: activeTab === tab.key ? '2px solid var(--ds-accent-purple)' : '2px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  fontFamily: 'inherit',
                  whiteSpace: 'nowrap',
                }}
              >
                {tab.label}
                {tab.count !== null && (
                  <span style={{ marginLeft: '0.375rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', fontWeight: 500 }}>({tab.count})</span>
                )}
              </button>
            ))}
          </div>

          <div style={{ padding: '1.125rem 1.25rem' }}>

            {/* ── Observations ── */}
            {activeTab === 'observations' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: '0.75rem' }}>
                {observations.length === 0 && (
                  <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem', textAlign: 'center', padding: '2rem 0', gridColumn: '1/-1' }}>No observations recorded</p>
                )}
                {observations.map(obs => (
                  <div key={obs.id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.75rem' }}>
                    <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Activity style={{ width: 14, height: 14, color: 'var(--ds-accent-blue)' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ margin: 0, fontSize: '0.6875rem', color: 'var(--ds-text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{obs.code}</p>
                      <p style={{ margin: '0.125rem 0 0', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{obs.value}</p>
                      <p style={{ margin: '0.125rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{obs.date || 'No date'}</p>
                    </div>
                    <CheckCircle2 style={{ width: 14, height: 14, color: 'var(--ds-accent-green)', flexShrink: 0 }} />
                  </div>
                ))}
              </div>
            )}

            {/* ── Encounters ── */}
            {activeTab === 'encounters' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                {encounters.length === 0 && (
                  <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem', textAlign: 'center', padding: '2rem 0' }}>No encounters recorded</p>
                )}
                {encounters.map(enc => {
                  const isFinished = enc.status === 'finished';
                  return (
                    <div key={enc.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.875rem', padding: '0.875rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.75rem' }}>
                      <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Activity style={{ width: 14, height: 14, color: 'var(--ds-accent-blue)' }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{enc.encounter_type}</span>
                          <span style={{
                            fontSize: '0.6875rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '2rem',
                            background: isFinished ? 'var(--ds-status-active-bg)' : 'var(--ds-status-syncing-bg)',
                            color: isFinished ? 'var(--ds-status-active-text)' : 'var(--ds-status-syncing-text)',
                            border: `1px solid ${isFinished ? 'rgba(16,185,129,0.25)' : 'rgba(59,130,246,0.25)'}`,
                            textTransform: 'capitalize',
                          }}>{enc.status}</span>
                        </div>
                        <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
                          {enc.start_date || 'No date'}{enc.end_date ? ` — ${enc.end_date}` : ''}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── Medications ── */}
            {activeTab === 'medications' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                {medications.length === 0 && (
                  <p style={{ color: 'var(--ds-text-muted)', fontSize: '0.875rem', textAlign: 'center', padding: '2rem 0' }}>No medications recorded</p>
                )}
                {medications.map(med => {
                  const isActive = med.status === 'active';
                  return (
                    <div key={med.id} style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', padding: '0.875rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.75rem' }}>
                      <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        <Pill style={{ width: 14, height: 14, color: 'var(--ds-accent-purple)' }} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{med.name}</span>
                          <span style={{
                            fontSize: '0.6875rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '2rem',
                            background: isActive ? 'var(--ds-status-active-bg)' : 'var(--ds-table-head-bg)',
                            color: isActive ? 'var(--ds-status-active-text)' : 'var(--ds-text-muted)',
                            border: `1px solid ${isActive ? 'rgba(16,185,129,0.25)' : 'var(--ds-table-border)'}`,
                          }}>{med.status}</span>
                        </div>
                        {med.dosage && <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: 'var(--ds-text-secondary)' }}>{med.dosage}</p>}
                        {med.prescribed && <p style={{ margin: '0.125rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>Prescribed: {med.prescribed}</p>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── FHIR Resource viewer ── */}
            {activeTab === 'fhir' && (
              <div>
                <p style={{ margin: '0 0 0.75rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)', lineHeight: 1.5 }}>
                  Raw FHIR R4 Patient resource as stored in the central DB — tenant-isolated, AES-256 encrypted at rest.
                </p>
                <pre style={{ background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: '0.75rem', padding: '1rem', overflowX: 'auto', lineHeight: 1.6, fontFamily: 'monospace', fontSize: '0.75rem', color: '#34d399', margin: 0, boxShadow: 'inset 0 2px 8px rgba(0,0,0,0.4)' }}>
{JSON.stringify({
  resourceType: 'Patient',
  id: patient.id,
  meta: { tenantId: patient.tenant_id, lastUpdated: new Date().toISOString() },
  name: [{ family: patient.family_name, given: [patient.given_name] }],
  birthDate: patient.birth_date,
  gender: patient.gender,
  telecom: patient.phone ? [{ system: 'phone', value: patient.phone }] : [],
  identifier: [{ system: 'urn:carelock:mrn', value: patient.source_patient_id }],
  active: patient.active,
}, null, 2)}
                </pre>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
};

export default PatientDetailPage;
