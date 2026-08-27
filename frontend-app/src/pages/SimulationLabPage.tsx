/**
 * SimulationLabPage — Dark glassmorphism, full ds-* design system.
 * Simulation & Testing Lab — trigger pipeline stages, failure/attack modes.
 */
import React, { useState, useRef } from 'react';
import {
  FlaskConical, Play, Database, Brain, Zap, RefreshCw,
  ChevronRight, Terminal, Plus, AlertTriangle, Gauge,
  Shield, ShieldAlert, CheckCircle2,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────
interface LogLine { time: string; level: 'info' | 'success' | 'error' | 'warn'; msg: string; }

const ts = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
const delay = (ms: number) => new Promise(r => setTimeout(r, ms));
const NAMES = ['Ayesha Malik', 'Usman Khan', 'Sara Baig', 'Raza Ahmed', 'Fatima Noor', 'Ali Hassan'];
const fakeName = () => NAMES[Math.floor(Math.random() * NAMES.length)];
const fakeMRN  = () => `MRN-${Math.floor(Math.random() * 9000 + 1000)}`;

const LOG_COLOR: Record<string, string> = {
  info:    'var(--ds-accent-blue)',
  success: 'var(--ds-accent-green)',
  error:   'var(--ds-status-error-text)',
  warn:    'var(--ds-accent-orange)',
};

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
const LogConsole: React.FC<{ lines: LogLine[]; speedLabel: string }> = ({ lines, speedLabel }) => {
  const ref = useRef<HTMLDivElement>(null);
  React.useEffect(() => { ref.current?.scrollIntoView({ behavior: 'smooth' }); }, [lines]);
  return (
    <div style={{ background: 'rgba(0,0,0,0.7)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '0.75rem', padding: '0.875rem', fontFamily: 'monospace', fontSize: '0.75rem', height: 220, overflowY: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.625rem', paddingBottom: '0.5rem', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', gap: '0.375rem' }}>
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444' }} />
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#f59e0b' }} />
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e' }} />
        </div>
        <span style={{ color: 'var(--ds-text-muted)', flex: 1 }}>carelock-pipeline — console</span>
        <span style={{ color: 'var(--ds-accent-orange)', fontWeight: 700 }}>{speedLabel}</span>
      </div>
      {lines.length === 0 && <span style={{ color: 'rgba(255,255,255,0.2)' }}>$ awaiting pipeline command…</span>}
      {lines.map((l, i) => (
        <div key={i} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.125rem' }}>
          <span style={{ color: 'rgba(255,255,255,0.25)', flexShrink: 0 }}>[{l.time}]</span>
          <span style={{ color: LOG_COLOR[l.level] }}>{l.msg}</span>
        </div>
      ))}
      <div ref={ref} />
    </div>
  );
};

interface SimCardProps {
  title: string; desc: string; icon: React.ReactNode;
  iconBg: string; iconColor: string;
  running: boolean; onRun: () => void; result?: string;
}
const SimCard: React.FC<SimCardProps> = ({ title, desc, icon, iconBg, iconColor, running, onRun, result }) => (
  <div style={{ ...card, padding: '1.125rem', display: 'flex', flexDirection: 'column' }}>
    <div style={{ width: 38, height: 38, borderRadius: '0.625rem', background: iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '0.625rem', color: iconColor }}>
      {icon}
    </div>
    <h3 style={{ margin: '0 0 0.25rem', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{title}</h3>
    <p style={{ margin: '0 0 0.875rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)', lineHeight: 1.5, flex: 1 }}>{desc}</p>
    {result && (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.5rem', padding: '0.375rem 0.625rem', marginBottom: '0.625rem', fontWeight: 600 }}>
        <CheckCircle2 style={{ width: 12, height: 12, flexShrink: 0 }} /> {result}
      </div>
    )}
    <button onClick={onRun} disabled={running}
      style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.375rem', fontSize: '0.75rem', fontWeight: 700, background: 'rgba(255,255,255,0.06)', color: 'var(--ds-text-primary)', border: '1px solid var(--ds-card-border)', borderRadius: '0.5rem', padding: '0.5rem 0.75rem', cursor: 'pointer', fontFamily: 'inherit', opacity: running ? 0.5 : 1, transition: 'opacity 0.2s, background 0.2s' }}
      onMouseOver={e => { if (!running) e.currentTarget.style.background = 'rgba(255,255,255,0.10)'; }}
      onMouseOut={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}>
      {running
        ? <><RefreshCw style={{ width: 12, height: 12, animation: 'spin 0.8s linear infinite' }} /> Running…</>
        : <><Play style={{ width: 12, height: 12 }} /> Run</>}
    </button>
  </div>
);

// ── Main ───────────────────────────────────────────────────────────────────────
const SimulationLabPage: React.FC = () => {
  const [logs, setLogs]         = useState<LogLine[]>([]);
  const [running, setRunning]   = useState<Record<string, boolean>>({});
  const [results, setResults]   = useState<Record<string, string>>({});
  const [speed, setSpeed]       = useState<1 | 2 | 5>(1);
  const [failMode, setFailMode] = useState(false);
  const [attackMode, setAttackMode] = useState(false);
  const [genCount, setGenCount] = useState(10);
  const [genHosp, setGenHosp]   = useState('hospital_a');

  const d      = (ms: number) => delay(ms / speed);
  const addLog = (level: LogLine['level'], msg: string) => setLogs(p => [...p, { time: ts(), level, msg }]);
  const setR   = (k: string, v: boolean) => setRunning(p => ({ ...p, [k]: v }));
  const setRes = (k: string, v: string)  => setResults(p => ({ ...p, [k]: v }));

  const runCDC = async () => {
    setR('cdc', true); setLogs([]);
    addLog('info', '[CDC] Connecting to hospital_a PostgreSQL adapter…'); await d(500);
    addLog('info', '[CDC] Polling for changes since watermark 2026-04-05T14:20:00Z…'); await d(700);
    if (failMode) {
      addLog('error', '[CDC] Connection timeout — adapter unreachable'); await d(400);
      addLog('warn',  '[CDC] Retrying (1/3)…'); await d(600);
      addLog('warn',  '[CDC] Retrying (2/3)…'); await d(600);
      addLog('error', '[CDC] Max retries exceeded — event queued for next poll cycle');
      setRes('cdc', 'Simulated CDC failure — retry exhausted');
    } else {
      addLog('success', '[CDC] 3 INSERT events detected on `patients`'); await d(300);
      addLog('info',    '[CDC] tenant_id=tenant-hosp-a attached'); await d(300);
      addLog('success', '[CDC] Events queued for ETL ✓'); await d(200);
      addLog('info',    '[CDC] Watermark advanced to 2026-04-05T14:30:00Z');
      setRes('cdc', '3 CDC events captured and queued');
    }
    setR('cdc', false);
  };

  const runETL = async () => {
    setR('etl', true); setLogs([]);
    addLog('info', '[ETL] Pipeline triggered for hospital_a'); await d(400);
    addLog('info', '[ETL] Extracting 3 records from event queue…'); await d(500);
    addLog('info', '[ETL] Applying FHIR R4 field mappings…'); await d(700);
    if (failMode) {
      addLog('error', '[ETL] FHIR validation failed — Patient.birthDate format invalid'); await d(300);
      addLog('warn',  '[ETL] Record moved to dead-letter queue for manual review');
      setRes('etl', 'ETL validation failure — 1 record quarantined');
    } else {
      addLog('success', '[ETL] Patient.id, name, birthDate, gender, telecom mapped ✓'); await d(400);
      addLog('success', '[ETL] FHIR R4 validation passed — 3/3 records valid ✓'); await d(300);
      addLog('info',    '[ETL] Writing to fhir_patients (partition: tenant_hospital_a)…'); await d(400);
      addLog('success', '[ETL] 3 records committed · Duration: 1.2s · Throughput: 2.5 rec/s');
      setRes('etl', '3 records extracted, transformed, loaded ✓');
    }
    setR('etl', false);
  };

  const runMapping = async () => {
    setR('mapping', true); setLogs([]);
    addLog('info',    '[AI] Schema submitted: PATIENT_MASTER (Hospital C)'); await d(400);
    addLog('info',    '[AI] Loading Ollama / LLaMA 3.2 model…'); await d(600);
    addLog('info',    '[AI] Running vector similarity search in ChromaDB (top-5)…'); await d(700);
    addLog('success', '[AI] PTNT_FULL_NM → Patient.name.family+given  [96.2%] ✓'); await d(300);
    addLog('success', '[AI] PTNT_BRTH_DT → Patient.birthDate          [74.1%] ⚠ DD/MM/YYYY transform needed'); await d(300);
    addLog('success', '[AI] GNDR_CD      → Patient.gender             [95.8%] ✓'); await d(300);
    addLog('success', '[AI] MED_REC_NO   → Patient.identifier[0].value [89.3%] ✓'); await d(400);
    addLog('info',    '[AI] Model: LLaMA 3.2 · Total inference: 1.4s · 3/4 auto-approved');
    setRes('mapping', '4 fields mapped — 3 auto-approved, 1 pending review');
    setR('mapping', false);
  };

  const runAttack = async () => {
    setR('attack', true); setLogs([]);
    addLog('warn',    '[ATTACK] Simulating brute-force login attempt…'); await d(400);
    addLog('warn',    '[ATTACK] Attempt 1/5 — invalid credentials'); await d(300);
    addLog('warn',    '[ATTACK] Attempt 2/5 — invalid credentials'); await d(300);
    addLog('warn',    '[ATTACK] Attempt 3/5 — invalid credentials'); await d(300);
    addLog('error',   '[SECURITY] Rate limit triggered — IP 10.99.0.1 blocked for 15 min'); await d(400);
    addLog('info',    '[ATTACK] Simulating cross-tenant SQL injection…'); await d(500);
    addLog('success', '[RLS] Query intercepted — tenant_isolation policy fired · 0 rows returned'); await d(300);
    addLog('info',    '[ATTACK] Attempting header manipulation (X-Tenant-Override)…'); await d(400);
    addLog('success', '[AUTH] Header rejected — tenant context set from JWT only · attack failed'); await d(300);
    addLog('success', '[SECURITY] All attack vectors blocked · 4 events logged to audit');
    setRes('attack', 'All attack vectors blocked — system secure');
    setR('attack', false);
  };

  const runRAG = async () => {
    setR('rag', true); setLogs([]);
    addLog('info',    '[RAG] Query: "How many diabetic patients admitted last month?"'); await d(300);
    addLog('info',    '[RAG] Generating embedding via all-MiniLM-L6-v2…'); await d(500);
    addLog('info',    '[RAG] ChromaDB similarity search — top 5 chunks retrieved'); await d(700);
    addLog('success', '[RAG] Chunk 1: fhir_conditions E11.x — 342 matches'); await d(200);
    addLog('success', '[RAG] Chunk 2: fhir_encounters March 2026 — 342 admissions'); await d(200);
    addLog('info',    '[RAG] Passing context to LLaMA / Gemini…'); await d(800);
    addLog('success', '[RAG] Answer: "342 diabetic patients admitted in March 2026"'); await d(200);
    addLog('info',    '[RAG] Confidence: 91.2% · Latency: 1.8s · Sources: 2 FHIR documents');
    setRes('rag', 'RAG answered with 91.2% confidence in 1.8s');
    setR('rag', false);
  };

  const runGenerate = async () => {
    setR('gen', true); setLogs([]);
    addLog('info', `[GEN] Generating ${genCount} synthetic patients for ${genHosp}…`); await d(300);
    addLog('info', '[GEN] Faker — Pakistani locale (Urdu names + CNIC format)'); await d(400);
    for (let i = 1; i <= Math.min(genCount, 6); i++) {
      addLog('success', `[GEN] Patient ${i}: ${fakeName()} · ${fakeMRN()}`); await d(180);
    }
    if (genCount > 6) addLog('info', `[GEN] … ${genCount - 6} more generated`);
    await d(300);
    addLog('success', `[GEN] ${genCount} records inserted into ${genHosp} ✓`);
    setRes('gen', `${genCount} synthetic patients generated`);
    setR('gen', false);
  };

  const runFull = async () => {
    setR('full', true); setLogs([]);
    addLog('info',    '[PIPELINE] ═══ CareLock Sync — full end-to-end demo ═══'); await d(300);
    addLog('info',    '[1/5] CDC polling hospital_a for changes…'); await d(500);
    addLog('success', '[1/5] CDC: 2 INSERT events captured — watermark advanced ✓'); await d(300);
    addLog('info',    '[2/5] ETL: extracting events from queue…'); await d(600);
    addLog('success', '[2/5] ETL: 2 records extracted and FHIR-transformed ✓'); await d(300);
    addLog('info',    '[3/5] AI Mapper: LLaMA inference for unmapped fields…'); await d(700);
    addLog('success', '[3/5] Mapper: 7/7 fields approved (avg confidence 96.2%) ✓'); await d(300);
    addLog('info',    '[4/5] Security: AES-256 encrypt + RLS partition write…'); await d(500);
    addLog('success', '[4/5] Security: records written to tenant_hospital_a partition ✓'); await d(300);
    addLog('info',    '[5/5] RAG: incremental vector rebuild…'); await d(600);
    addLog('success', '[5/5] RAG: 2 embeddings indexed in ChromaDB ✓'); await d(300);
    addLog('success', '[PIPELINE] ✓ Complete in 4.2s · 2 records · 0 errors · RLS verified');
    setRes('full', 'Full pipeline: CDC → ETL → FHIR → Security → RAG in 4.2s');
    setR('full', false);
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)',
    borderRadius: '0.5rem', padding: '0.5rem 0.75rem', fontSize: '0.8125rem',
    color: 'var(--ds-text-primary)', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header + controls */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FlaskConical style={{ width: 20, height: 20, color: 'var(--ds-accent-blue)' }} /> Simulation &amp; Testing Lab
          </h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
            Trigger individual stages or run the full pipeline — failure mode and attack simulation included
          </p>
        </div>

        {/* Control panel */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', flexWrap: 'wrap' }}>
          {/* Speed selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)', borderRadius: '0.75rem', padding: '0.25rem' }}>
            <Gauge style={{ width: 14, height: 14, color: 'var(--ds-text-muted)', marginLeft: '0.375rem' }} />
            {([1, 2, 5] as const).map(s => (
              <button key={s} onClick={() => setSpeed(s)}
                style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.3rem 0.625rem', borderRadius: '0.5rem', border: 'none', cursor: 'pointer', fontFamily: 'inherit', background: speed === s ? 'var(--ds-card-bg)' : 'transparent', color: speed === s ? 'var(--ds-text-primary)' : 'var(--ds-text-muted)', boxShadow: speed === s ? 'var(--ds-card-shadow)' : 'none', transition: 'all 0.2s' }}>
                {s}×
              </button>
            ))}
          </div>

          {/* Failure mode */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', fontWeight: 700, padding: '0.375rem 0.75rem', borderRadius: '0.625rem', border: `1px solid ${failMode ? 'rgba(245,158,11,0.4)' : 'var(--ds-border)'}`, background: failMode ? 'var(--ds-status-pending-bg)' : 'var(--ds-surface)', color: failMode ? 'var(--ds-status-pending-text)' : 'var(--ds-text-muted)', cursor: 'pointer', transition: 'all 0.2s' }}>
            <input type="checkbox" checked={failMode} onChange={e => setFailMode(e.target.checked)} style={{ width: 12, height: 12, accentColor: '#f59e0b' }} />
            <AlertTriangle style={{ width: 12, height: 12 }} /> Failure mode
          </label>

          {/* Attack mode */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', fontWeight: 700, padding: '0.375rem 0.75rem', borderRadius: '0.625rem', border: `1px solid ${attackMode ? 'rgba(239,68,68,0.4)' : 'var(--ds-border)'}`, background: attackMode ? 'var(--ds-status-error-bg)' : 'var(--ds-surface)', color: attackMode ? 'var(--ds-status-error-text)' : 'var(--ds-text-muted)', cursor: 'pointer', transition: 'all 0.2s' }}>
            <input type="checkbox" checked={attackMode} onChange={e => setAttackMode(e.target.checked)} style={{ width: 12, height: 12, accentColor: '#ef4444' }} />
            <ShieldAlert style={{ width: 12, height: 12 }} /> Attack simulation
          </label>
        </div>
      </div>

      {/* Mode banners */}
      {failMode && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.75rem 1rem', background: 'var(--ds-status-pending-bg)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '0.75rem', fontSize: '0.8125rem', color: 'var(--ds-status-pending-text)', fontWeight: 600 }}>
          <AlertTriangle style={{ width: 14, height: 14, flexShrink: 0 }} />
          Failure mode ON — CDC and ETL simulations will inject errors to test resilience and retry logic
        </div>
      )}
      {attackMode && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.75rem 1rem', background: 'var(--ds-status-error-bg)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '0.75rem', fontSize: '0.8125rem', color: 'var(--ds-status-error-text)', fontWeight: 600 }}>
          <ShieldAlert style={{ width: 14, height: 14, flexShrink: 0 }} />
          Attack simulation ON — use the "Simulate attack" card to test brute-force, SQL injection, and header-manipulation defences
        </div>
      )}

      {/* Simulation cards — 4-col */}
      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '1rem' }}>
        <SimCard title="Simulate CDC event"  desc="Trigger a Change Data Capture poll on Hospital A." icon={<Database style={{ width: 16, height: 16 }} />} iconBg="rgba(139,92,246,0.15)" iconColor="var(--ds-accent-purple)" running={!!running.cdc}     onRun={runCDC}     result={results.cdc}     />
        <SimCard title="Run ETL pipeline"    desc="Execute extract, transform (FHIR mapping), and load for queued events." icon={<Zap style={{ width: 16, height: 16 }} />} iconBg="rgba(245,158,11,0.15)" iconColor="var(--ds-accent-orange)" running={!!running.etl}     onRun={runETL}     result={results.etl}     />
        <SimCard title="Run AI mapping"      desc="Submit Hospital C's legacy schema to LLaMA and get FHIR field suggestions." icon={<Brain style={{ width: 16, height: 16 }} />} iconBg="rgba(99,102,241,0.15)" iconColor="#818cf8" running={!!running.mapping} onRun={runMapping} result={results.mapping} />
        <SimCard title="Test RAG query"      desc="Run a natural language query against the FHIR vector store." icon={<Terminal style={{ width: 16, height: 16 }} />} iconBg="rgba(16,185,129,0.15)" iconColor="var(--ds-accent-green)" running={!!running.rag}     onRun={runRAG}     result={results.rag}     />
      </div>

      {/* Second row — 3 col */}
      <div className="ds-animate ds-animate-d2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>

        {/* Full pipeline */}
        <div style={{ ...card, padding: '1.125rem', display: 'flex', flexDirection: 'column', background: 'linear-gradient(135deg,rgba(59,130,246,0.12) 0%,rgba(99,102,241,0.12) 100%)', borderColor: 'rgba(59,130,246,0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
            <Play style={{ width: 16, height: 16, color: 'var(--ds-accent-blue)' }} />
            <h3 style={{ margin: 0, fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Full end-to-end pipeline</h3>
          </div>
          <p style={{ margin: '0 0 0.875rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)', lineHeight: 1.5 }}>One click runs all 5 stages: CDC → ETL → AI Mapping → Security → RAG.</p>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', flexWrap: 'wrap', marginBottom: '0.875rem' }}>
            {['CDC', 'ETL', 'FHIR', 'Security', 'RAG'].map((s, i, arr) => (
              <React.Fragment key={s}>
                <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '0.375rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-card-border)', color: 'var(--ds-text-secondary)' }}>{s}</span>
                {i < arr.length - 1 && <ChevronRight style={{ width: 10, height: 10, color: 'var(--ds-text-muted)' }} />}
              </React.Fragment>
            ))}
          </div>
          {results.full && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.5rem', padding: '0.375rem 0.625rem', marginBottom: '0.625rem', fontWeight: 600 }}>
              <CheckCircle2 style={{ width: 12, height: 12, flexShrink: 0 }} /> {results.full}
            </div>
          )}
          <button onClick={runFull} disabled={!!running.full}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontSize: '0.8125rem', fontWeight: 700, background: 'linear-gradient(135deg,var(--ds-accent-blue),#4f46e5)', color: '#fff', border: 'none', borderRadius: '0.625rem', padding: '0.625rem 1rem', cursor: 'pointer', fontFamily: 'inherit', opacity: running.full ? 0.5 : 1, marginTop: 'auto', transition: 'opacity 0.2s' }}>
            {running.full ? <><RefreshCw style={{ width: 14, height: 14, animation: 'spin 0.8s linear infinite' }} /> Running…</> : <><Play style={{ width: 14, height: 14 }} /> Run full pipeline</>}
          </button>
        </div>

        {/* Attack simulation */}
        <div style={{ ...card, padding: '1.125rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
            <ShieldAlert style={{ width: 16, height: 16, color: 'var(--ds-status-error-text)' }} />
            <h3 style={{ margin: 0, fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Simulate attack vectors</h3>
          </div>
          <p style={{ margin: '0 0 0.875rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)', lineHeight: 1.5, flex: 1 }}>Tests brute-force login, cross-tenant SQL injection, and JWT header manipulation — all in one run.</p>
          {results.attack && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.5rem', padding: '0.375rem 0.625rem', marginBottom: '0.625rem', fontWeight: 600 }}>
              <Shield style={{ width: 12, height: 12, flexShrink: 0 }} /> {results.attack}
            </div>
          )}
          <button onClick={runAttack} disabled={!!running.attack}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontSize: '0.8125rem', fontWeight: 700, background: 'var(--ds-status-error-bg)', color: 'var(--ds-status-error-text)', border: '1px solid rgba(239,68,68,0.35)', borderRadius: '0.625rem', padding: '0.625rem 1rem', cursor: 'pointer', fontFamily: 'inherit', opacity: running.attack ? 0.5 : 1, transition: 'opacity 0.2s' }}>
            {running.attack ? <><RefreshCw style={{ width: 14, height: 14, animation: 'spin 0.8s linear infinite' }} /> Running…</> : <><ShieldAlert style={{ width: 14, height: 14 }} /> Simulate attack</>}
          </button>
        </div>

        {/* Generate synthetic patients */}
        <div style={{ ...card, padding: '1.125rem', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.375rem' }}>
            <Plus style={{ width: 16, height: 16, color: 'var(--ds-text-secondary)' }} />
            <h3 style={{ margin: 0, fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Generate synthetic patients</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem', marginBottom: '0.875rem', flex: 1 }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginBottom: '0.25rem' }}>Target hospital</label>
              <select value={genHosp} onChange={e => setGenHosp(e.target.value)} style={inputStyle}>
                <option value="hospital_a">Hospital A — Shifa</option>
                <option value="hospital_b">Hospital B — PIMS</option>
                <option value="hospital_c">Hospital C — Polyclinic</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginBottom: '0.25rem' }}>
                Patients: <span style={{ fontWeight: 700, color: 'var(--ds-text-primary)' }}>{genCount}</span>
              </label>
              <input type="range" min={1} max={500} step={1} value={genCount} onChange={e => setGenCount(Number(e.target.value))} style={{ width: '100%', accentColor: 'var(--ds-accent-purple)' }} />
            </div>
          </div>
          {results.gen && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.5rem', padding: '0.375rem 0.625rem', marginBottom: '0.625rem', fontWeight: 600 }}>
              <CheckCircle2 style={{ width: 12, height: 12, flexShrink: 0 }} /> {results.gen}
            </div>
          )}
          <button onClick={runGenerate} disabled={!!running.gen}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', fontSize: '0.8125rem', fontWeight: 700, background: 'rgba(255,255,255,0.06)', color: 'var(--ds-text-primary)', border: '1px solid var(--ds-card-border)', borderRadius: '0.625rem', padding: '0.625rem 1rem', cursor: 'pointer', fontFamily: 'inherit', opacity: running.gen ? 0.5 : 1, transition: 'all 0.2s' }}>
            {running.gen ? <><RefreshCw style={{ width: 14, height: 14, animation: 'spin 0.8s linear infinite' }} /> Generating…</> : <><Plus style={{ width: 14, height: 14 }} /> Generate {genCount}</>}
          </button>
        </div>
      </div>

      {/* Console */}
      <div className="ds-animate ds-animate-d3">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Terminal style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} />
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Console output</h2>
            {Object.values(running).some(Boolean) && (
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--ds-accent-green)', animation: 'pulse 2s infinite' }} />
            )}
          </div>
          <button onClick={() => setLogs([])} style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>Clear</button>
        </div>
        <LogConsole lines={logs} speedLabel={`${speed}× speed`} />
      </div>
    </div>
  );
};

export default SimulationLabPage;
