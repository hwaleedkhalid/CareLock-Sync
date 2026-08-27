/**
 * pages/SystemDemoPage.tsx — Dark glassmorphism, full ds-* design system.
 * Interactive 5-step end-to-end pipeline demo with live animations.
 */
import React, { useState, useEffect, useRef } from 'react';
import DashboardLayout from '../layouts/DashboardLayout';
import {
  Play, ChevronRight, Database, ArrowRight, Brain,
  CheckCircle2, Lock, LockOpen, RefreshCw,
  AlertTriangle, Eye, Zap, Sparkles,
} from 'lucide-react';

// ── Static data ────────────────────────────────────────────────────────────────
const HOSPITAL_A_RAW = [
  { field: 'patient_id', value: '10482',           type: 'INTEGER' },
  { field: 'first_name', value: 'Ayesha',          type: 'VARCHAR' },
  { field: 'last_name',  value: 'Malik',           type: 'VARCHAR' },
  { field: 'dob',        value: '1991-03-12',      type: 'DATE'    },
  { field: 'gender_cd',  value: 'F',               type: 'CHAR'    },
  { field: 'cnic',       value: '35202-1234567-8', type: 'VARCHAR' },
  { field: 'phone_no',   value: '+92-300-1234567', type: 'VARCHAR' },
];
const HOSPITAL_B_RAW = [
  { field: 'PTNT_SEQ_NO',  value: '90021',                    type: 'BIGINT'  },
  { field: 'PTNT_FULL_NM', value: 'Usman Khan',               type: 'VARCHAR' },
  { field: 'PTNT_BRTH_DT', value: '15/08/1972',               type: 'VARCHAR' },
  { field: 'GNDR_CD',      value: 'M',                        type: 'CHAR'    },
  { field: 'MED_REC_NO',   value: 'MRN-B-0021',               type: 'VARCHAR' },
  { field: 'CNTCT_PHONE',  value: '051-1234567',              type: 'VARCHAR' },
  { field: 'HOME_ADDR_LN1',value: 'House 12, Street 5, F-7/2', type: 'VARCHAR' },
];
const AI_MAPPINGS_A = [
  { source: 'patient_id', target: 'Patient.id',                 confidence: 0.99, status: 'approved', ms: 82,  reasoning: "Exact semantic match — 'patient_id' maps to FHIR primary identifier. Verified by 847 similar mappings in knowledge base.", model: 'LLaMA 3.2' },
  { source: 'first_name', target: 'Patient.name.given',         confidence: 0.99, status: 'approved', ms: 91,  reasoning: "High-confidence n-gram match with FHIR HumanName.given. Confirmed via ChromaDB vector search (similarity: 0.98).", model: 'LLaMA 3.2' },
  { source: 'last_name',  target: 'Patient.name.family',        confidence: 0.98, status: 'approved', ms: 88,  reasoning: "Semantic pattern 'last_name' / 'surname' / 'family_name' all resolve to Patient.name.family in FHIR R4 spec.", model: 'LLaMA 3.2' },
  { source: 'dob',        target: 'Patient.birthDate',          confidence: 0.97, status: 'approved', ms: 105, reasoning: "Date-type field with 'dob' abbreviation matched against FHIR birthDate. ISO-8601 format confirmed in sample values.", model: 'LLaMA 3.2' },
  { source: 'gender_cd',  target: 'Patient.gender',             confidence: 0.95, status: 'approved', ms: 97,  reasoning: "CHAR(1) field with values 'M'/'F' matches FHIR gender coding. Transformation: M→male, F→female applied.", model: 'LLaMA 3.2' },
  { source: 'cnic',       target: 'Patient.identifier[0].value',confidence: 0.88, status: 'pending',  ms: 134, reasoning: "Pakistan CNIC number format matched as a national identifier. Low confidence due to ambiguity between CNIC and MRN — manual review recommended.", model: 'Gemini' },
  { source: 'phone_no',   target: 'Patient.telecom[0].value',   confidence: 0.92, status: 'approved', ms: 110, reasoning: "Phone number field mapped to FHIR telecom with system='phone'. E.164 normalisation transform applied.", model: 'LLaMA 3.2' },
];
const FHIR_RESULT = {
  resourceType: 'Patient',
  id: '10482',
  meta: { tenantId: 'tenant-hospital-a', lastUpdated: '2026-04-05T14:22:01Z' },
  name: [{ family: 'Malik', given: ['Ayesha'] }],
  birthDate: '1991-03-12',
  gender: 'female',
  telecom: [{ system: 'phone', value: '+92-300-1234567' }],
  identifier: [{ system: 'https://hospital-a.pk/cnic', value: '35202-1234567-8' }],
};
const STEPS = [
  { id: 1, title: 'Select hospital',   sub: 'Choose data source',         accent: 'rgba(59,130,246,0.8)',  accentBg: 'rgba(59,130,246,0.12)',  accentBorder: 'rgba(59,130,246,0.4)'  },
  { id: 2, title: 'CDC data capture',  sub: 'Real-time change detection', accent: 'rgba(139,92,246,0.8)', accentBg: 'rgba(139,92,246,0.12)', accentBorder: 'rgba(139,92,246,0.4)' },
  { id: 3, title: 'AI mapping',        sub: 'FHIR field suggestion',      accent: 'rgba(99,102,241,0.8)', accentBg: 'rgba(99,102,241,0.12)', accentBorder: 'rgba(99,102,241,0.4)' },
  { id: 4, title: 'FHIR output',       sub: 'Standardised record',        accent: 'rgba(16,185,129,0.8)', accentBg: 'rgba(16,185,129,0.12)', accentBorder: 'rgba(16,185,129,0.4)' },
  { id: 5, title: 'Tenant isolation',  sub: 'Zero cross-tenant leakage',  accent: 'rgba(239,68,68,0.8)',  accentBg: 'rgba(239,68,68,0.12)',  accentBorder: 'rgba(239,68,68,0.4)'  },
];
const CDC_LOGS = (hosp: 'A' | 'B') => [
  { ms: '+0ms',   msg: `[CDC] INSERT detected on ${hosp === 'A' ? 'patients' : 'PATIENT_MASTER'}`,              color: '#34d399' },
  { ms: '+42ms',  msg: `[CDC] tenant_id=${hosp === 'A' ? 'tenant-hosp-a' : 'tenant-hosp-b'} attached to event`, color: '#60a5fa' },
  { ms: '+89ms',  msg: '[CDC] Watermark checkpointed — no data loss guarantee',                                   color: '#c4b5fd' },
  { ms: '+120ms', msg: '[ETL] Record dequeued and sent to transform pipeline',                                    color: '#818cf8' },
  { ms: '+204ms', msg: '[ETL] Schema fingerprint matched — using cached mapping config',                          color: '#22d3ee' },
  { ms: '+450ms', msg: '[AI]  LLaMA inference complete — all fields resolved',                                    color: '#fbbf24' },
  { ms: '+612ms', msg: '[ETL] FHIR R4 record assembled and validated ✓',                                         color: '#34d399' },
];

// ── Design helpers ─────────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: 'var(--ds-card-bg)',
  backdropFilter: 'var(--ds-card-blur)',
  WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
  border: '1px solid var(--ds-card-border)',
  borderRadius: '1rem',
  boxShadow: 'var(--ds-card-shadow)',
};

// ── Sub-components ─────────────────────────────────────────────────────────────
const ProgressBar: React.FC<{ step: number; total: number }> = ({ step, total }) => {
  const pct   = Math.round(((step - 1) / (total - 1)) * 100);
  const s     = STEPS[step - 1];
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
      <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>Step {step}/{total}</span>
      <div style={{ flex: 1, height: 6, background: 'var(--ds-table-border)', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct === 0 ? 2 : pct}%`, background: s.accent, borderRadius: 999, transition: 'width 0.7s ease, background 0.4s ease' }} />
      </div>
      <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', whiteSpace: 'nowrap' }}>{s.title}</span>
    </div>
  );
};

const StepDot: React.FC<{ step: typeof STEPS[0]; active: boolean; done: boolean; onClick: () => void }> = ({ step, active, done, onClick }) => {
  const bg     = done ? 'var(--ds-accent-green)' : active ? step.accentBg    : 'var(--ds-surface)';
  const border = done ? 'rgba(16,185,129,0.7)'   : active ? step.accentBorder : 'var(--ds-table-border)';
  const color  = done ? '#fff'                    : active ? step.accent      : 'var(--ds-text-muted)';
  return (
    <button onClick={onClick}
      style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem', padding: '0.5rem 0.75rem', minWidth: 88, borderRadius: '0.75rem', border: `2px solid ${border}`, background: bg, color, cursor: 'pointer', fontFamily: 'inherit', transition: 'all 0.3s', transform: active && !done ? 'scale(1.05)' : 'scale(1)', boxShadow: active && !done ? `0 4px 16px ${step.accentBg}` : 'none' }}>
      {done ? <CheckCircle2 style={{ width: 14, height: 14 }} /> : <span style={{ fontSize: '0.875rem', fontWeight: 800 }}>{step.id}</span>}
      <span style={{ fontSize: '0.6875rem', fontWeight: 700, textAlign: 'center', lineHeight: 1.2 }}>{step.title}</span>
    </button>
  );
};

const CdcLogLine: React.FC<{ ms: string; msg: string; color: string; delay: number }> = ({ ms, msg, color, delay }) => {
  const [vis, setVis] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVis(true), delay); return () => clearTimeout(t); }, [delay]);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', fontFamily: 'monospace', fontSize: '0.6875rem', marginBottom: '0.25rem', opacity: vis ? 1 : 0, transform: vis ? 'translateY(0)' : 'translateY(6px)', transition: 'all 0.4s ease' }}>
      <span style={{ color: 'rgba(255,255,255,0.25)', width: 56, flexShrink: 0 }}>{ms}</span>
      <span style={{ color }}>{msg}</span>
    </div>
  );
};

const AnimRow: React.FC<{ field: string; value: string; type: string; delay: number }> = ({ field, value, type, delay }) => {
  const [vis, setVis] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVis(true), delay); return () => clearTimeout(t); }, [delay]);
  return (
    <tr style={{ opacity: vis ? 1 : 0, transform: vis ? 'translateX(0)' : 'translateX(-16px)', transition: 'all 0.5s ease' }}>
      <td style={{ padding: '0.5rem 0.75rem', fontFamily: 'monospace', fontSize: '0.6875rem', color: 'var(--ds-accent-blue)', fontWeight: 600 }}>{field}</td>
      <td style={{ padding: '0.5rem 0.75rem', fontSize: '0.75rem', color: 'var(--ds-text-primary)' }}>{value}</td>
      <td style={{ padding: '0.5rem 0.75rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{type}</td>
    </tr>
  );
};

const MappingRow: React.FC<{ m: typeof AI_MAPPINGS_A[0]; delay: number }> = ({ m, delay }) => {
  const [vis, setVis]           = useState(false);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { const t = setTimeout(() => setVis(true), delay); return () => clearTimeout(t); }, [delay]);
  const pct = Math.round(m.confidence * 100);

  const confBg    = pct >= 95 ? 'var(--ds-status-active-bg)'  : pct >= 80 ? 'var(--ds-status-pending-bg)'  : 'var(--ds-status-error-bg)';
  const confColor = pct >= 95 ? 'var(--ds-status-active-text)' : pct >= 80 ? 'var(--ds-status-pending-text)' : 'var(--ds-status-error-text)';
  const confBorder = pct >= 95 ? 'rgba(16,185,129,0.3)' : pct >= 80 ? 'rgba(245,158,11,0.3)' : 'rgba(239,68,68,0.3)';

  const modelBg     = m.model === 'LLaMA 3.2' ? 'rgba(99,102,241,0.12)' : 'rgba(20,184,166,0.12)';
  const modelColor  = m.model === 'LLaMA 3.2' ? '#818cf8'                : '#2dd4bf';
  const modelBorder = m.model === 'LLaMA 3.2' ? 'rgba(99,102,241,0.3)'  : 'rgba(20,184,166,0.3)';

  return (
    <div style={{ borderBottom: '1px solid var(--ds-table-border)', opacity: vis ? 1 : 0, transition: 'opacity 0.5s ease' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.25rem', cursor: 'pointer', borderRadius: '0.5rem', transition: 'background 0.15s' }}
        onClick={() => setExpanded(e => !e)}
        onMouseOver={e => ((e.currentTarget as HTMLElement).style.background = 'var(--ds-surface)')}
        onMouseOut={e => ((e.currentTarget as HTMLElement).style.background = 'transparent')}>
        <span style={{ fontFamily: 'monospace', fontSize: '0.6875rem', color: 'var(--ds-text-secondary)', width: 128, flexShrink: 0 }}>{m.source}</span>
        <ArrowRight style={{ width: 11, height: 11, color: 'var(--ds-text-muted)', flexShrink: 0 }} />
        <span style={{ fontFamily: 'monospace', fontSize: '0.6875rem', color: 'var(--ds-accent-blue)', flex: 1 }}>{m.target}</span>
        <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.15rem 0.375rem', borderRadius: '2rem', background: confBg, color: confColor, border: `1px solid ${confBorder}`, flexShrink: 0 }}>{pct}%</span>
        <span style={{ fontSize: '0.6875rem', padding: '0.15rem 0.375rem', borderRadius: '0.25rem', background: modelBg, color: modelColor, border: `1px solid ${modelBorder}`, flexShrink: 0 }}>{m.model}</span>
        <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', width: 40, textAlign: 'right', flexShrink: 0 }}>{m.ms}ms</span>
        {m.status === 'approved'
          ? <CheckCircle2 style={{ width: 12, height: 12, color: 'var(--ds-accent-green)', flexShrink: 0 }} />
          : <AlertTriangle style={{ width: 12, height: 12, color: 'var(--ds-accent-orange)', flexShrink: 0 }} />
        }
        <ChevronRight style={{ width: 11, height: 11, color: 'var(--ds-text-muted)', flexShrink: 0, transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
      </div>
      {expanded && (
        <div style={{ margin: '0 0.25rem 0.5rem', padding: '0.5rem 0.75rem', background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.18)', borderRadius: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.375rem' }}>
            <Brain style={{ width: 11, height: 11, color: '#818cf8', flexShrink: 0, marginTop: 2 }} />
            <p style={{ margin: 0, fontSize: '0.6875rem', color: 'var(--ds-text-secondary)', lineHeight: 1.55 }}>
              <strong>AI reasoning:</strong> {m.reasoning}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

// ── Main ───────────────────────────────────────────────────────────────────────
const SystemDemoPage: React.FC = () => {
  const [step, setStep]               = useState(1);
  const [hospital, setHospital]       = useState<'A' | 'B'>('A');
  const [playing, setPlaying]         = useState(false);
  const [cdcReady, setCdcReady]       = useState(false);
  const [isolation, setIsolation]     = useState<null | 'running' | 'blocked'>(null);
  const [showFinalMsg, setShowFinalMsg] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const playDemo = () => {
    setPlaying(true); setStep(1); setCdcReady(false);
    setIsolation(null); setShowFinalMsg(false);
    let s = 1;
    const next = () => {
      s++;
      if (s > 5) { setPlaying(false); return; }
      setStep(s);
      if (s === 2) setCdcReady(true);
      timer.current = setTimeout(next, s === 3 ? 2800 : s === 5 ? 2000 : 2200);
    };
    timer.current = setTimeout(next, 1600);
  };

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  const doIsolation = () => {
    setIsolation('running');
    setTimeout(() => { setIsolation('blocked'); setShowFinalMsg(true); }, 1400);
  };

  const raw = hospital === 'A' ? HOSPITAL_A_RAW : HOSPITAL_B_RAW;

  return (
    <DashboardLayout>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', fontFamily: "'Inter',sans-serif" }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em' }}>Live System Demo</h1>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>End-to-end walkthrough — raw hospital DB → AI-mapped → FHIR-compliant → tenant-isolated</p>
          </div>
          <button onClick={playDemo} disabled={playing}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'linear-gradient(135deg,var(--ds-accent-blue),#4f46e5)', color: '#fff', border: 'none', borderRadius: '0.75rem', padding: '0.625rem 1.25rem', fontSize: '0.875rem', fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', opacity: playing ? 0.55 : 1, transition: 'opacity 0.2s' }}>
            {playing ? <><RefreshCw style={{ width: 14, height: 14, animation: 'spin 0.8s linear infinite' }} /> Running auto-demo…</> : <><Play style={{ width: 14, height: 14 }} /> Auto-play full demo</>}
          </button>
        </div>

        {/* Progress bar */}
        <ProgressBar step={step} total={5} />

        {/* Step dots */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.25rem' }}>
          {STEPS.map((s, i) => (
            <React.Fragment key={s.id}>
              <StepDot step={s} active={step === s.id} done={step > s.id} onClick={() => { setPlaying(false); setStep(s.id); }} />
              {i < STEPS.length - 1 && (
                <ChevronRight style={{ width: 14, height: 14, flexShrink: 0, color: step > s.id ? 'var(--ds-accent-green)' : 'var(--ds-text-muted)', transition: 'color 0.3s' }} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* ── Step 1: Select hospital ── */}
        {step === 1 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {(['A', 'B'] as const).map(h => (
              <button key={h} onClick={() => { setHospital(h); setCdcReady(false); setStep(2); }}
                style={{ ...card, padding: '1.5rem', textAlign: 'left', cursor: 'pointer', fontFamily: 'inherit', border: `2px solid ${hospital === h ? 'rgba(59,130,246,0.55)' : 'var(--ds-card-border)'}`, background: hospital === h ? 'rgba(59,130,246,0.08)' : 'var(--ds-card-bg)', transition: 'all 0.25s' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.875rem' }}>
                  <div style={{ width: 40, height: 40, borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: '1.125rem', background: h === 'A' ? 'linear-gradient(135deg,#3b82f6,#4f46e5)' : 'linear-gradient(135deg,#8b5cf6,#6366f1)' }}>H{h}</div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ds-text-primary)' }}>{h === 'A' ? 'Shifa International' : 'PIMS Hospital'}</div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{h === 'A' ? 'PostgreSQL · normalised schema' : 'Legacy flat schema · denormalised'}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem', fontSize: '0.8125rem', color: 'var(--ds-text-secondary)' }}>
                  <div>Tables: <span style={{ fontFamily: 'monospace', color: 'var(--ds-text-primary)', fontWeight: 600 }}>{h === 'A' ? 'patients, encounters, obs' : 'PATIENT_MASTER'}</span></div>
                  <div>Records: <span style={{ fontWeight: 700, color: 'var(--ds-text-primary)' }}>{h === 'A' ? '4,821' : '3,102'}</span></div>
                  <div>Tenant: <span style={{ fontFamily: 'monospace', color: 'var(--ds-accent-blue)', fontWeight: 600 }}>{h === 'A' ? 'tenant-hosp-a' : 'tenant-hosp-b'}</span></div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* ── Step 2: CDC capture ── */}
        {step === 2 && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {/* Raw DB record */}
            <div style={{ ...card, overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1rem', background: 'var(--ds-table-head-bg)', borderBottom: '1px solid var(--ds-table-border)' }}>
                <Database style={{ width: 14, height: 14, color: 'var(--ds-accent-purple)' }} />
                <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Hospital {hospital} — raw DB record</span>
                <span style={{ marginLeft: 'auto', fontSize: '0.6875rem', fontWeight: 700, padding: '0.15rem 0.5rem', borderRadius: '2rem', background: cdcReady ? 'var(--ds-status-active-bg)' : 'var(--ds-surface)', color: cdcReady ? 'var(--ds-status-active-text)' : 'var(--ds-text-muted)', border: `1px solid ${cdcReady ? 'rgba(16,185,129,0.3)' : 'var(--ds-table-border)'}`, animation: cdcReady ? 'pulse 2s infinite' : 'none' }}>
                  {cdcReady ? 'CDC captured' : 'Listening…'}
                </span>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ds-table-border)' }}>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', fontWeight: 600 }}>Field</th>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', fontWeight: 600 }}>Value</th>
                    <th style={{ padding: '0.5rem 0.75rem', textAlign: 'left', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', fontWeight: 600 }}>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {raw.map((r, i) => <AnimRow key={r.field} field={r.field} value={r.value} type={r.type} delay={i * 140} />)}
                </tbody>
              </table>
            </div>

            {/* CDC event stream */}
            <div style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)' as any, border: '1px solid rgba(255,255,255,0.07)', borderRadius: '1rem', padding: '1.125rem', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.875rem' }}>
                <Zap style={{ width: 14, height: 14, color: '#fbbf24' }} />
                <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: '#f8fafc' }}>CDC event stream</span>
                <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: cdcReady ? '#34d399' : 'rgba(255,255,255,0.15)', animation: cdcReady ? 'pulse 2s infinite' : 'none' }} />
                  <span style={{ fontSize: '0.6875rem', color: 'rgba(255,255,255,0.35)' }}>{cdcReady ? 'Active' : 'Idle'}</span>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                {CDC_LOGS(hospital).map((l, i) => <CdcLogLine key={i} ms={l.ms} msg={l.msg} color={l.color} delay={i * 320} />)}
              </div>
              <button onClick={() => setStep(3)} style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--ds-accent-blue)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit', transition: 'opacity 0.2s' }}>
                Next: AI mapping <ChevronRight style={{ width: 12, height: 12 }} />
              </button>
            </div>
          </div>
        )}

        {/* ── Step 3: AI mapping ── */}
        {step === 3 && (
          <div style={{ ...card, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.25rem', background: 'rgba(99,102,241,0.08)', borderBottom: '1px solid var(--ds-table-border)' }}>
              <Brain style={{ width: 18, height: 18, color: '#818cf8' }} />
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>AI mapping engine — Hospital {hospital} → FHIR R4 Patient</div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>
                  Model: <span style={{ fontWeight: 600, color: '#818cf8' }}>Ollama / LLaMA 3.2</span> + <span style={{ fontWeight: 600, color: '#2dd4bf' }}>Gemini (fallback)</span> · ChromaDB vector similarity · Click any row for AI reasoning
                </div>
              </div>
              <span style={{ marginLeft: 'auto', fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.625rem', borderRadius: '2rem', background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)', flexShrink: 0 }}>
                {AI_MAPPINGS_A.filter(m => m.status === 'approved').length}/{AI_MAPPINGS_A.length} approved
              </span>
            </div>
            <div style={{ padding: '0.75rem 1.25rem' }}>
              <div style={{ display: 'grid', fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', marginBottom: '0.25rem', padding: '0 0.25rem', gridTemplateColumns: '128px 12px 1fr 60px 90px 48px 16px 16px', gap: '0.25rem' }}>
                <span>Source field</span><span /><span>FHIR target</span><span>Confidence</span><span>Model</span><span>Time</span><span /><span />
              </div>
              {AI_MAPPINGS_A.map((m, i) => <MappingRow key={m.source} m={m} delay={i * 180} />)}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.625rem 1.25rem', background: 'var(--ds-table-head-bg)', borderTop: '1px solid var(--ds-table-border)' }}>
              <div style={{ display: 'flex', gap: '0.75rem', fontSize: '0.75rem' }}>
                <span style={{ color: 'var(--ds-accent-green)', fontWeight: 700 }}>6 auto-approved (≥90%)</span>
                <span style={{ color: 'var(--ds-accent-orange)', fontWeight: 700 }}>1 pending manual review</span>
              </div>
              <button onClick={() => setStep(4)} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.8125rem', color: 'var(--ds-accent-blue)', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                View FHIR output <ChevronRight style={{ width: 14, height: 14 }} />
              </button>
            </div>
          </div>
        )}

        {/* ── Step 4: FHIR output ── */}
        {step === 4 && (
          <div style={{ ...card, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.25rem', background: 'rgba(16,185,129,0.08)', borderBottom: '1px solid var(--ds-table-border)' }}>
              <CheckCircle2 style={{ width: 18, height: 18, color: 'var(--ds-accent-green)' }} />
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>FHIR R4 Patient resource — generated and stored</div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>Central DB · tenant-isolated partition · AES-256 encrypted at rest · TLS 1.3 in transit</div>
              </div>
              <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.375rem', flexShrink: 0 }}>
                {[
                  { label: 'Valid FHIR R4', bg: 'var(--ds-status-active-bg)',  color: 'var(--ds-status-active-text)',  border: 'rgba(16,185,129,0.3)'  },
                  { label: 'AES-256',       bg: 'rgba(59,130,246,0.12)',        color: 'var(--ds-accent-blue)',          border: 'rgba(59,130,246,0.3)'  },
                  { label: 'RLS active',    bg: 'rgba(139,92,246,0.12)',       color: 'var(--ds-accent-purple)',        border: 'rgba(139,92,246,0.3)' },
                ].map(tag => (
                  <span key={tag.label} style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: tag.bg, color: tag.color, border: `1px solid ${tag.border}` }}>{tag.label}</span>
                ))}
              </div>
            </div>
            <div style={{ padding: '1.125rem 1.25rem' }}>
              <pre style={{ background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(16,185,129,0.18)', borderRadius: '0.75rem', padding: '1rem', overflowX: 'auto', lineHeight: 1.6, fontFamily: 'monospace', fontSize: '0.75rem', color: '#34d399', margin: 0 }}>
                {JSON.stringify(FHIR_RESULT, null, 2)}
              </pre>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.625rem 1.25rem', background: 'var(--ds-table-head-bg)', borderTop: '1px solid var(--ds-table-border)', fontSize: '0.75rem' }}>
              <span style={{ color: 'var(--ds-text-muted)' }}>Partition: <span style={{ fontFamily: 'monospace', color: 'var(--ds-accent-blue)' }}>fhir_patients_tenant_hospital_a</span> · Record ID: <span style={{ fontFamily: 'monospace' }}>10482</span></span>
              <button onClick={() => setStep(5)} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.8125rem', color: 'var(--ds-accent-blue)', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
                Test tenant isolation <ChevronRight style={{ width: 14, height: 14 }} />
              </button>
            </div>
          </div>
        )}

        {/* ── Step 5: Tenant isolation ── */}
        {step === 5 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              {/* Hospital A — authorised */}
              <div style={{ ...card, overflow: 'hidden', borderColor: 'rgba(59,130,246,0.4)', borderWidth: 2 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 1rem', background: 'rgba(59,130,246,0.08)', borderBottom: '1px solid rgba(59,130,246,0.2)' }}>
                  <div style={{ width: 24, height: 24, borderRadius: '0.5rem', background: 'linear-gradient(135deg,#3b82f6,#4f46e5)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800 }}>A</div>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Hospital A session</span>
                  <span style={{ marginLeft: 'auto', fontFamily: 'monospace', fontSize: '0.6875rem', color: 'var(--ds-accent-blue)' }}>tenant-hosp-a</span>
                </div>
                <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
                    <LockOpen style={{ width: 12, height: 12, color: 'var(--ds-accent-green)' }} /> Authorised query:
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: '0.625rem', padding: '0.75rem', fontFamily: 'monospace', fontSize: '0.6875rem', lineHeight: 1.6, color: '#fbbf24' }}>
                    SELECT * FROM fhir_patients<br />
                    WHERE tenant_id = <span style={{ color: '#60a5fa' }}>'tenant-hosp-a'</span>;
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: '0.625rem', padding: '0.75rem', fontFamily: 'monospace', fontSize: '0.6875rem', lineHeight: 1.6, color: '#34d399' }}>
                    → 4,821 rows returned ✓<br />
                    id: 10482 | Ayesha Malik | 1991-03-12<br />
                    id: 10483 | Sara Baig    | 1996-11-22<br />
                    <span style={{ color: 'rgba(255,255,255,0.3)' }}>… 4,819 more rows</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.6875rem', color: 'var(--ds-accent-green)', fontWeight: 700 }}>
                    <CheckCircle2 style={{ width: 12, height: 12 }} /> RLS grants access to own tenant data
                  </div>
                </div>
              </div>

              {/* Hospital B — blocked */}
              <div style={{ ...card, overflow: 'hidden', borderColor: isolation === 'blocked' ? 'rgba(239,68,68,0.5)' : 'var(--ds-card-border)', borderWidth: 2, transition: 'border-color 0.4s' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 1rem', background: isolation === 'blocked' ? 'rgba(239,68,68,0.08)' : 'rgba(139,92,246,0.08)', borderBottom: `1px solid ${isolation === 'blocked' ? 'rgba(239,68,68,0.2)' : 'rgba(139,92,246,0.2)'}`, transition: 'all 0.4s' }}>
                  <div style={{ width: 24, height: 24, borderRadius: '0.5rem', background: 'linear-gradient(135deg,#8b5cf6,#6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800 }}>B</div>
                  <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Hospital B session — attempting breach</span>
                  <span style={{ marginLeft: 'auto', fontFamily: 'monospace', fontSize: '0.6875rem', color: 'var(--ds-accent-purple)' }}>tenant-hosp-b</span>
                </div>
                <div style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
                    <Eye style={{ width: 12, height: 12, color: 'var(--ds-status-error-text)' }} /> Cross-tenant query attempt:
                  </div>
                  <div style={{ background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: '0.625rem', padding: '0.75rem', fontFamily: 'monospace', fontSize: '0.6875rem', lineHeight: 1.6, color: '#fbbf24' }}>
                    SELECT * FROM fhir_patients<br />
                    WHERE tenant_id = <span style={{ color: '#f87171' }}>'tenant-hosp-a'</span>;<br />
                    <span style={{ color: 'rgba(255,255,255,0.3)' }}>-- Hospital B trying to read Hospital A data</span>
                  </div>

                  {isolation === null && (
                    <button onClick={doIsolation}
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%', background: 'var(--ds-status-error-bg)', color: 'var(--ds-status-error-text)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: '0.75rem', padding: '0.75rem', fontSize: '0.8125rem', fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', transition: 'opacity 0.2s' }}>
                      <AlertTriangle style={{ width: 14, height: 14 }} /> Attempt unauthorised access
                    </button>
                  )}
                  {isolation === 'running' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)', fontFamily: 'monospace', padding: '0.5rem 0' }}>
                      <RefreshCw style={{ width: 12, height: 12, animation: 'spin 0.8s linear infinite', color: 'var(--ds-accent-blue)' }} /> Evaluating RLS policies…
                    </div>
                  )}
                  {isolation === 'blocked' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div style={{ background: 'rgba(0,0,0,0.55)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '0.625rem', padding: '0.75rem', fontFamily: 'monospace', fontSize: '0.6875rem', lineHeight: 1.6, color: '#f87171' }}>
                        ERROR: permission denied for table fhir_patients<br />
                        DETAIL: RLS policy "tenant_isolation" blocked row access<br />
                        HINT:   session tenant_id ≠ row tenant_id<br />
                        <span style={{ color: 'rgba(255,255,255,0.3)', display: 'block', marginTop: 4 }}>→ 0 rows returned · HTTP 403 Forbidden</span>
                      </div>
                      <div style={{ background: 'var(--ds-status-pending-bg)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '0.625rem', padding: '0.625rem 0.875rem', fontSize: '0.6875rem', color: 'var(--ds-status-pending-text)', lineHeight: 1.55 }}>
                        <strong>Why was this blocked?</strong><br />
                        PostgreSQL Row-Level Security evaluated the session's <code style={{ fontFamily: 'monospace' }}>tenant_id = 'tenant-hosp-b'</code> against the requested row's <code style={{ fontFamily: 'monospace' }}>tenant_id = 'tenant-hosp-a'</code>. The RLS policy <code style={{ fontFamily: 'monospace' }}>tenant_isolation</code> filters all rows where these do not match — at the database engine level, before any application code runs.
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.5rem' }}>
                        {['API Auth ✓', 'Tenant Context ✓', 'RLS Policy ✓'].map(label => (
                          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', background: 'var(--ds-status-active-bg)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.5rem', padding: '0.375rem 0.625rem' }}>
                            <CheckCircle2 style={{ width: 11, height: 11, color: 'var(--ds-accent-green)', flexShrink: 0 }} />
                            <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: 'var(--ds-status-active-text)' }}>{label}</span>
                          </div>
                        ))}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.6875rem', color: 'var(--ds-accent-green)', fontWeight: 700 }}>
                        <Lock style={{ width: 12, height: 12 }} /> Event logged to carelock_audit.db · alert raised
                      </div>
                      <button onClick={() => { setIsolation(null); setShowFinalMsg(false); }} style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', padding: 0, fontFamily: 'inherit' }}>Reset</button>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Final impact message */}
            {showFinalMsg && (
              <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '1rem', padding: '1.125rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <Sparkles style={{ width: 16, height: 16, color: 'var(--ds-accent-green)' }} />
                  <span style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Demo complete — all systems verified</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.75rem' }}>
                  {[
                    { icon: <CheckCircle2 style={{ width: 14, height: 14, color: 'var(--ds-accent-green)' }} />, msg: 'Data securely processed end-to-end', bg: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: 'rgba(16,185,129,0.3)' },
                    { icon: <Brain style={{ width: 14, height: 14, color: '#818cf8' }} />, msg: 'AI-assisted FHIR transformation complete', bg: 'rgba(99,102,241,0.12)', color: '#818cf8', border: 'rgba(99,102,241,0.3)' },
                    { icon: <Lock style={{ width: 14, height: 14, color: 'var(--ds-status-error-text)' }} />, msg: 'Zero cross-tenant data leakage — RLS enforced', bg: 'var(--ds-status-error-bg)', color: 'var(--ds-status-error-text)', border: 'rgba(239,68,68,0.3)' },
                  ].map(item => (
                    <div key={item.msg} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', background: item.bg, border: `1px solid ${item.border}`, borderRadius: '0.75rem', padding: '0.75rem', fontSize: '0.75rem', fontWeight: 600, color: item.color, lineHeight: 1.45 }}>
                      <div style={{ flexShrink: 0, marginTop: 1 }}>{item.icon}</div>
                      {item.msg}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Bottom metrics strip */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '1rem 1.25rem', ...card }}>
          {[
            { v: '3',       l: 'Hospitals',        c: 'var(--ds-accent-blue)'   },
            { v: '48,210',  l: 'FHIR records',      c: 'var(--ds-accent-purple)' },
            { v: '99.4%',   l: 'Mapping accuracy', c: 'var(--ds-accent-green)'  },
            { v: '100%',    l: 'Isolation proof',  c: 'var(--ds-status-error-text)' },
            { v: 'AES-256', l: 'Encryption',        c: '#818cf8'                 },
            { v: '<2 wks',  l: 'Onboarding time',  c: 'var(--ds-accent-orange)' },
          ].map((s, i) => (
            <React.Fragment key={s.l}>
              <div style={{ flex: 1, textAlign: 'center', padding: '0.25rem 0' }}>
                <div style={{ fontSize: '0.9375rem', fontWeight: 800, color: s.c, letterSpacing: '-0.02em' }}>{s.v}</div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{s.l}</div>
              </div>
              {i < 5 && <div style={{ width: 1, height: 32, background: 'var(--ds-table-border)', flexShrink: 0 }} />}
            </React.Fragment>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
};

export default SystemDemoPage;
