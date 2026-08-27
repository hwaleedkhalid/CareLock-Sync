/**
 * pages/HospitalOnboardingPage.tsx
 * Public hospital onboarding page — dark glassmorphism theme matching the landing page.
 * Accessible at /onboarding without authentication.
 * On success shows a confirmation screen with a link to sign in.
 */
import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Building2, ArrowRight, ArrowLeft, CheckCircle2, AlertCircle,
  Loader2, Wifi, Eye, EyeOff, X, Shield, Lock, Zap,
} from 'lucide-react';
import { apiClient } from '../shared/services/apiClient';
import type { ApiError } from '../shared/services/apiClient';
import { PUBLIC_ROUTES } from '../shared/constants/routes';

// ── Dark palette (mirroring the landing page / login page colours) ────────────

const DARK = {
  bg:          '#080c18',
  cardBg:      'rgba(255,255,255,0.04)',
  cardBorder:  'rgba(255,255,255,0.09)',
  surface:     'rgba(255,255,255,0.06)',
  border:      'rgba(255,255,255,0.09)',
  rowBg:       'rgba(255,255,255,0.06)',
  divider:     'rgba(255,255,255,0.06)',
  textPrimary: 'rgba(255,255,255,0.93)',
  textSub:     'rgba(255,255,255,0.60)',
  textMuted:   'rgba(255,255,255,0.40)',
  accent:      '#3b82f6',
  accentGlow:  'rgba(59,130,246,0.25)',
  green:       '#34d399',
  greenBg:     'rgba(16,185,129,0.12)',
  greenBorder: 'rgba(16,185,129,0.25)',
  amber:       '#fbbf24',
  amberBg:     'rgba(245,158,11,0.12)',
  amberBorder: 'rgba(245,158,11,0.25)',
  red:         '#ef4444',
  redBg:       'rgba(239,68,68,0.10)',
  redBorder:   'rgba(239,68,68,0.30)',
  blue:        '#60a5fa',
  blueBg:      'rgba(59,130,246,0.10)',
  blueBorder:  'rgba(59,130,246,0.25)',
};

// ── Types ─────────────────────────────────────────────────────────────────────

type DBType = 'postgresql' | 'mysql' | 'mongodb' | 'sqlserver' | 'oracle';

const DEFAULT_PORTS: Record<DBType, string> = {
  postgresql: '5432', mysql: '3306', mongodb: '27017',
  sqlserver: '1433', oracle: '1521',
};

interface WizardForm {
  hospitalName: string; hospitalCode: string; city: string;
  dbType: DBType; dbHost: string; dbPort: string;
  dbName: string; dbUser: string; dbPass: string;
}

type WizardErrors = Partial<Record<keyof WizardForm, string>>;

interface SchemaTable { name: string; cols: number; rows: string }
interface MappingRow  { src: string; fhir: string; conf: number }

const WIZARD_STEPS = [
  { n: 1, label: 'Hospital Info' },
  { n: 2, label: 'DB Connection' },
  { n: 3, label: 'Schema Detection' },
  { n: 4, label: 'AI Mapping' },
  { n: 5, label: 'Review & Launch' },
];

// ── Style helpers ─────────────────────────────────────────────────────────────

const inp: React.CSSProperties = {
  width: '100%', padding: '0.625rem 0.875rem',
  background: DARK.surface,
  border: `1px solid ${DARK.border}`,
  borderRadius: '0.625rem', fontSize: '0.875rem',
  color: DARK.textPrimary, outline: 'none',
  boxSizing: 'border-box', fontFamily: 'inherit',
};
const inpErr: React.CSSProperties = { ...inp, border: `1px solid ${DARK.red}` };
const lbl: React.CSSProperties = {
  display: 'block', fontSize: '0.75rem', fontWeight: 600,
  color: DARK.textSub, marginBottom: '0.3rem',
};
const errTxt: React.CSSProperties = {
  fontSize: '0.6875rem', color: DARK.red, marginTop: '0.25rem',
};

const btnPrimary: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '0.375rem',
  padding: '0.625rem 1.25rem',
  background: 'linear-gradient(135deg,#3b82f6,#6366f1)',
  color: '#fff', border: 'none', borderRadius: '0.75rem',
  fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer',
  transition: 'opacity 0.2s',
};
const btnSecondary: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '0.375rem',
  padding: '0.625rem 1.25rem',
  background: DARK.surface,
  color: DARK.textSub,
  border: `1px solid ${DARK.border}`,
  borderRadius: '0.75rem', fontSize: '0.875rem',
  fontWeight: 500, cursor: 'pointer',
};
const btnOutline: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '0.375rem',
  padding: '0.5rem 1rem',
  background: DARK.surface,
  color: DARK.textSub,
  border: `1px solid ${DARK.border}`,
  borderRadius: '0.625rem', fontSize: '0.8125rem',
  fontWeight: 500, cursor: 'pointer',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function normaliseSchemaResponse(raw: unknown): SchemaTable[] {
  if (!raw || typeof raw !== 'object') return [];
  const r = raw as Record<string, unknown>;
  if (r.tables && typeof r.tables === 'object') {
    return Object.entries(r.tables as Record<string, any>).map(([name, info]) => ({
      name,
      cols: Array.isArray(info?.columns) ? info.columns.length : (info?.column_count ?? 0),
      rows: info?.row_count != null ? Number(info.row_count).toLocaleString() : '—',
    }));
  }
  const topLevel = Object.entries(r).filter(([, v]) => v && typeof v === 'object');
  if (topLevel.length > 0) {
    return topLevel.map(([name, info]: [string, any]) => ({
      name,
      cols: Array.isArray(info?.columns) ? info.columns.length : 0,
      rows: info?.row_count != null ? Number(info.row_count).toLocaleString() : '—',
    }));
  }
  return [];
}

function extractColumnsForTable(raw: unknown, tableName: string): { name: string; type: string }[] {
  if (!raw || typeof raw !== 'object') return [];
  const r = raw as Record<string, any>;
  const tableData = r.tables?.[tableName] ?? r[tableName];
  if (!tableData) return [];
  const cols: unknown[] = Array.isArray(tableData.columns) ? tableData.columns : [];
  return cols
    .filter((c): c is Record<string, any> => typeof c === 'object' && c !== null)
    .map(c => ({ name: String(c.name ?? c.column_name ?? ''), type: String(c.type ?? c.data_type ?? 'varchar') }))
    .filter(c => c.name);
}

function normaliseMappings(raw: unknown): MappingRow[] {
  if (!raw || typeof raw !== 'object') return [];
  const r = raw as Record<string, any>;
  const list: unknown[] = Array.isArray(r.mappings) ? r.mappings
    : Array.isArray(r.suggestions) ? r.suggestions
    : [];
  return list
    .filter((m): m is Record<string, any> => typeof m === 'object' && m !== null)
    .map(m => ({
      src:  String(m.source_field ?? m.field ?? ''),
      fhir: String(m.target_path ?? m.fhir_path ?? m.fhir_field ?? ''),
      conf: Math.round(Number(m.confidence ?? 0) * 100),
    }))
    .filter(m => m.src && m.fhir);
}

// ── Alert banner ──────────────────────────────────────────────────────────────

const WizardAlert: React.FC<{ type: 'error' | 'warning' | 'info'; message: string }> = ({ type, message }) => {
  const colour = {
    error:   { bg: DARK.redBg,   border: DARK.redBorder,   color: DARK.red },
    warning: { bg: DARK.amberBg, border: DARK.amberBorder, color: DARK.amber },
    info:    { bg: DARK.blueBg,  border: DARK.blueBorder,  color: DARK.blue },
  }[type];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.625rem', padding: '0.75rem', borderRadius: '0.75rem', background: colour.bg, border: `1px solid ${colour.border}` }}>
      <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, marginTop: 2, color: colour.color }} />
      <span style={{ fontSize: '0.8125rem', color: colour.color, lineHeight: 1.5 }}>{message}</span>
    </div>
  );
};

// ── Success screen ────────────────────────────────────────────────────────────

const SuccessScreen: React.FC<{ hospitalName: string; onSignIn: () => void }> = ({ hospitalName, onSignIn }) => (
  <div style={{ textAlign: 'center', padding: '3rem 2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1.5rem' }}>
    <div style={{ width: 72, height: 72, borderRadius: '50%', background: DARK.greenBg, border: `2px solid ${DARK.greenBorder}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <CheckCircle2 style={{ width: 36, height: 36, color: DARK.green }} />
    </div>
    <div>
      <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: DARK.textPrimary }}>
        Hospital Registered!
      </h2>
      <p style={{ margin: '0.5rem 0 0', fontSize: '1rem', color: DARK.textSub }}>
        <strong style={{ color: DARK.textPrimary }}>{hospitalName}</strong> has been successfully onboarded to CareLock.
      </p>
    </div>
    <div style={{ background: DARK.cardBg, border: `1px solid ${DARK.cardBorder}`, borderRadius: '1rem', padding: '1.25rem', maxWidth: 400, width: '100%', textAlign: 'left' }}>
      {[
        'Tenant partition created in central FHIR database',
        'Row-Level Security (RLS) activated',
        'CDC agent will begin monitoring on the next sync cycle',
        'AES-256 encryption applied to all PHI fields',
      ].map(item => (
        <div key={item} style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', padding: '0.35rem 0', fontSize: '0.8125rem', color: DARK.green }}>
          <CheckCircle2 style={{ width: 13, height: 13, flexShrink: 0 }} />{item}
        </div>
      ))}
    </div>
    <p style={{ margin: 0, fontSize: '0.875rem', color: DARK.textMuted }}>
      Your hospital account is ready. Sign in to access the hospital dashboard.
    </p>
    <button onClick={onSignIn} style={{ ...btnPrimary, padding: '0.75rem 2rem', fontSize: '0.9375rem' }}>
      <ArrowRight style={{ width: 16, height: 16 }} />
      Sign In to Dashboard
    </button>
  </div>
);

// ── Main wizard component ─────────────────────────────────────────────────────

const HospitalOnboardingPage: React.FC = () => {
  const navigate = useNavigate();

  const [step, setStep]           = useState(1);
  const [showPw, setShowPw]       = useState(false);
  const [done, setDone]           = useState(false);

  // Form
  const [form, setForm] = useState<WizardForm>({
    hospitalName: '', hospitalCode: '', city: '',
    dbType: 'postgresql', dbHost: '', dbPort: '5432',
    dbName: '', dbUser: '', dbPass: '',
  });
  const [errors, setErrors] = useState<WizardErrors>({});

  const set = (k: keyof WizardForm, v: string) =>
    setForm(f => ({
      ...f, [k]: v,
      ...(k === 'dbType' ? { dbPort: DEFAULT_PORTS[v as DBType] } : {}),
    }));

  // Step 3 — Schema Detection
  const [detecting, setDetecting]           = useState(false);
  const [schemaRaw, setSchemaRaw]           = useState<unknown>(null);
  const [detectedSchema, setDetectedSchema] = useState<SchemaTable[]>([]);
  const [schemaError, setSchemaError]       = useState<string | null>(null);

  const runDetection = useCallback(async () => {
    setDetecting(true);
    setSchemaError(null);
    setDetectedSchema([]);
    setSchemaRaw(null);
    try {
      const raw = await apiClient.get('/api/v1/connector/schema');
      setSchemaRaw(raw);
      const tables = normaliseSchemaResponse(raw);
      setDetectedSchema(tables);
      if (tables.length === 0)
        setSchemaError('Schema endpoint returned no tables. Ensure the hospital DB is reachable.');
    } catch (err) {
      const e = err as ApiError;
      setSchemaError(e.userMessage ?? e.message ?? 'Schema detection failed. Check backend connectivity.');
    } finally {
      setDetecting(false);
    }
  }, []);

  // Step 4 — AI Mapping
  const [mappingLoading, setMappingLoading]   = useState(false);
  const [mappingRows, setMappingRows]         = useState<MappingRow[]>([]);
  const [mappingError, setMappingError]       = useState<string | null>(null);
  const [mappingFetched, setMappingFetched]   = useState(false);

  const fetchMapping = useCallback(async () => {
    if (mappingFetched) return;
    setMappingLoading(true);
    setMappingError(null);
    const tableName = detectedSchema[0]?.name ?? 'patients';
    const columns   = extractColumnsForTable(schemaRaw, tableName);
    const colsPayload = columns.length > 0 ? columns : [
      { name: 'first_name',    type: 'varchar' },
      { name: 'last_name',     type: 'varchar' },
      { name: 'date_of_birth', type: 'date' },
      { name: 'gender',        type: 'varchar' },
      { name: 'phone_number',  type: 'varchar' },
      { name: 'email',         type: 'varchar' },
    ];
    try {
      const result = await apiClient.post('/api/v1/rag/suggest/schema', {
        table_name: tableName, columns: colsPayload, fhir_resource: 'Patient',
      });
      const rows = normaliseMappings(result);
      setMappingRows(rows);
      if (rows.length === 0)
        setMappingError('AI mapping returned no suggestions. You can proceed and map manually later.');
    } catch (err) {
      const e = err as ApiError;
      setMappingError(e.userMessage ?? e.message ?? 'AI mapping service is unavailable. You can proceed and configure mappings later.');
    } finally {
      setMappingLoading(false);
      setMappingFetched(true);
    }
  }, [detectedSchema, schemaRaw, mappingFetched]);

  useEffect(() => {
    if (step === 4) fetchMapping();
  }, [step, fetchMapping]);

  // Submission
  const [submitting, setSubmitting]   = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Validation
  const validateStep1 = (): boolean => {
    const e: WizardErrors = {};
    if (!form.hospitalName.trim()) e.hospitalName = 'Hospital name is required';
    if (!form.hospitalCode.trim()) e.hospitalCode = 'Hospital code is required';
    else if (form.hospitalCode.trim().length < 2) e.hospitalCode = 'Code must be at least 2 characters';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const validateStep2 = (): boolean => {
    const e: WizardErrors = {};
    if (!form.dbHost.trim()) e.dbHost = 'Host is required';
    if (!form.dbName.trim()) e.dbName = 'Database name is required';
    if (!form.dbUser.trim()) e.dbUser = 'Username is required';
    if (!form.dbPass.trim()) e.dbPass = 'Password is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleNext = () => {
    setSubmitError(null);
    if (step === 1 && !validateStep1()) return;
    if (step === 2 && !validateStep2()) return;
    setErrors({});
    if (step < WIZARD_STEPS.length) setStep(s => s + 1);
  };

  const handleSubmit = async () => {
    if (!validateStep1() || !validateStep2()) {
      setSubmitError('Some required fields are missing. Please go back and complete them.');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const healthy = await apiClient.isBackendHealthy();
      if (!healthy) {
        setSubmitError('Backend is currently unavailable. Please wait and try again.');
        return;
      }
      await apiClient.post('/api/v1/tenants', {
        hospital_name: form.hospitalName.trim(),
        hospital_code: form.hospitalCode.trim().toUpperCase(),
        city:          form.city.trim() || undefined,
        db_type:       form.dbType,
        db_host:       form.dbHost.trim(),
        db_port:       parseInt(form.dbPort, 10) || 5432,
        db_name:       form.dbName.trim(),
        db_user:       form.dbUser.trim(),
        db_password:   form.dbPass,
      });
      setDone(true);
    } catch (err) {
      const e = err as ApiError;
      setSubmitError(
        e.userMessage ??
        (e.status === 409 ? e.message : null) ??
        'Failed to onboard hospital. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  // ── Field component ───────────────────────────────────────────────────────

  const Field: React.FC<{
    label: string;
    fieldKey: keyof WizardForm;
    placeholder?: string;
    style?: React.CSSProperties;
    type?: string;
    maxLength?: number;
    children?: React.ReactNode;
  }> = ({ label: labelText, fieldKey, placeholder, style, type = 'text', maxLength, children }) => (
    <div>
      <label style={lbl}>{labelText}</label>
      {children ?? (
        <input
          type={type}
          value={form[fieldKey]}
          onChange={e => {
            const v = fieldKey === 'hospitalCode' ? e.target.value.toUpperCase() : e.target.value;
            set(fieldKey, v);
            if (errors[fieldKey]) setErrors(prev => { const n = { ...prev }; delete n[fieldKey]; return n; });
          }}
          maxLength={maxLength}
          style={{ ...(errors[fieldKey] ? inpErr : inp), ...style }}
          placeholder={placeholder}
        />
      )}
      {errors[fieldKey] && <p style={errTxt}>{errors[fieldKey]}</p>}
    </div>
  );

  // ── Step renderers ────────────────────────────────────────────────────────

  const renderStep1 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
      <div>
        <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: DARK.textPrimary }}>Hospital Information</h3>
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.8125rem', color: DARK.textMuted }}>Tell us about your hospital to create your tenant account.</p>
      </div>
      <Field label="Hospital Name *" fieldKey="hospitalName" placeholder="e.g. City General Hospital" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
        <Field label="Hospital Code *" fieldKey="hospitalCode" placeholder="CGH" maxLength={10} style={{ fontFamily: 'monospace', letterSpacing: '0.05em' }} />
        <Field label="City" fieldKey="city" placeholder="Karachi" />
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
      <div>
        <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: DARK.textPrimary }}>Database Connection</h3>
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.8125rem', color: DARK.textMuted }}>Provide read access to your hospital database so CareLock can sync records.</p>
      </div>
      <div>
        <label style={lbl}>Database Engine</label>
        <select
          value={form.dbType}
          onChange={e => set('dbType', e.target.value)}
          style={{ ...inp, background: DARK.surface }}
        >
          {(['postgresql', 'mysql', 'mongodb', 'sqlserver', 'oracle'] as DBType[]).map(t => (
            <option key={t} value={t} style={{ background: '#1a1f2e' }}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </option>
          ))}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.875rem' }}>
        <Field label="Host *" fieldKey="dbHost" placeholder="localhost" />
        <Field label="Port" fieldKey="dbPort" placeholder="5432" style={{ fontFamily: 'monospace' }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem' }}>
        <Field label="Database Name *" fieldKey="dbName" placeholder="hospital_db" />
        <Field label="Username *" fieldKey="dbUser" placeholder="hospital_user" />
      </div>
      <div>
        <label style={lbl}>Password *</label>
        <div style={{ position: 'relative' }}>
          <input
            type={showPw ? 'text' : 'password'}
            value={form.dbPass}
            onChange={e => {
              set('dbPass', e.target.value);
              if (errors.dbPass) setErrors(prev => { const n = { ...prev }; delete n.dbPass; return n; });
            }}
            style={{ ...(errors.dbPass ? inpErr : inp), paddingRight: '2.5rem' }}
            placeholder="••••••••"
          />
          <button
            type="button"
            onClick={() => setShowPw(v => !v)}
            style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: DARK.textMuted, display: 'flex', padding: 0 }}
          >
            {showPw ? <EyeOff style={{ width: 15, height: 15 }} /> : <Eye style={{ width: 15, height: 15 }} />}
          </button>
        </div>
        {errors.dbPass && <p style={errTxt}>{errors.dbPass}</p>}
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.6875rem', color: DARK.textMuted }}>
          <Lock style={{ width: 10, height: 10, display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
          Connection credentials are encrypted with AES-256 before storage.
        </p>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
      <div>
        <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: DARK.textPrimary }}>Schema Auto-Detection</h3>
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.8125rem', color: DARK.textMuted }}>
          The CDC agent will connect to your hospital database and automatically discover all tables, columns, and relationships.
        </p>
      </div>

      {!detectedSchema.length && !detecting && !schemaError && (
        <button onClick={runDetection} style={btnPrimary}>
          <Wifi style={{ width: 14, height: 14 }} />
          Connect &amp; Detect Schema
        </button>
      )}

      {detecting && (
        <div style={{ background: DARK.blueBg, border: `1px solid ${DARK.blueBorder}`, borderRadius: '0.875rem', padding: '1.125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.875rem' }}>
            <Loader2 style={{ width: 18, height: 18, color: DARK.blue, animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: DARK.blue }}>Connecting to database…</span>
          </div>
          {['Testing connection', 'Listing tables', 'Reading columns', 'Detecting indexes'].map(m => (
            <div key={m} style={{ fontSize: '0.75rem', color: DARK.blue, fontFamily: 'monospace', padding: '0.15rem 0' }}>
              ● {m}
            </div>
          ))}
        </div>
      )}

      {schemaError && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <WizardAlert type="error" message={schemaError} />
          <button onClick={runDetection} style={btnOutline}>
            <Wifi style={{ width: 13, height: 13 }} />
            Retry Detection
          </button>
          <p style={{ margin: 0, fontSize: '0.75rem', color: DARK.textMuted }}>
            You can skip this step and proceed — schema can be configured later from your dashboard.
          </p>
        </div>
      )}

      {detectedSchema.length > 0 && !detecting && (
        <div style={{ background: DARK.greenBg, border: `1px solid ${DARK.greenBorder}`, borderRadius: '0.875rem', padding: '1.125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: DARK.green, fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.875rem' }}>
            <CheckCircle2 style={{ width: 15, height: 15 }} />
            Schema detected — {detectedSchema.length} table{detectedSchema.length !== 1 ? 's' : ''} found
          </div>
          {detectedSchema.map(t => (
            <div key={t.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.2)', borderRadius: '0.5rem', padding: '0.5rem 0.75rem', marginTop: '0.375rem' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '0.8125rem', fontWeight: 700, color: DARK.textPrimary }}>{t.name}</span>
              <span style={{ fontSize: '0.6875rem', color: DARK.textMuted }}>
                {t.cols > 0 ? `${t.cols} cols` : 'cols unknown'} · {t.rows} rows
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderStep4 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
      <div>
        <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: DARK.textPrimary }}>AI Mapping Suggestions</h3>
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.8125rem', color: DARK.textMuted }}>
          The AI engine analyses the detected schema and generates FHIR R4 field mapping suggestions automatically.
        </p>
      </div>

      {mappingLoading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem', background: DARK.blueBg, borderRadius: '0.875rem', border: `1px solid ${DARK.blueBorder}` }}>
          <Loader2 style={{ width: 18, height: 18, color: DARK.blue, animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '0.875rem', color: DARK.blue, fontWeight: 600 }}>Generating FHIR mapping suggestions…</span>
        </div>
      )}

      {mappingError && !mappingLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <WizardAlert type="warning" message={mappingError} />
          <button onClick={() => { setMappingFetched(false); fetchMapping(); }} style={btnOutline}>
            Retry AI Mapping
          </button>
        </div>
      )}

      {mappingRows.length > 0 && !mappingLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          {mappingRows.map(m => (
            <div key={m.src} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: DARK.rowBg, borderRadius: '0.75rem', padding: '0.625rem 0.75rem' }}>
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: DARK.textMuted, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.src}</span>
              <ArrowRight style={{ width: 11, height: 11, color: DARK.textMuted, flexShrink: 0 }} />
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: DARK.blue, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.fhir}</span>
              <span style={{
                fontSize: '0.6875rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '2rem', flexShrink: 0,
                background: m.conf >= 90 ? DARK.greenBg : DARK.amberBg,
                color:      m.conf >= 90 ? DARK.green   : DARK.amber,
              }}>{m.conf}%</span>
              <CheckCircle2 style={{ width: 13, height: 13, color: DARK.green, flexShrink: 0 }} />
            </div>
          ))}
        </div>
      )}

      {!mappingLoading && !mappingError && mappingRows.length === 0 && mappingFetched && (
        <WizardAlert type="info" message="No mapping suggestions were returned. You can proceed and configure mappings manually after onboarding." />
      )}
    </div>
  );

  const totalCols  = detectedSchema.reduce((s, t) => s + t.cols, 0);
  const tableCount = detectedSchema.length;

  const renderStep5 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
      <div>
        <h3 style={{ margin: 0, fontWeight: 700, fontSize: '1rem', color: DARK.textPrimary }}>Review &amp; Launch</h3>
        <p style={{ margin: '0.3rem 0 0', fontSize: '0.8125rem', color: DARK.textMuted }}>Confirm your details before creating the hospital tenant.</p>
      </div>

      <div style={{ background: DARK.rowBg, border: `1px solid ${DARK.border}`, borderRadius: '0.875rem', padding: '1.125rem', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
        {[
          { label: 'Hospital',      value: form.hospitalName || '—' },
          { label: 'Code',          value: form.hospitalCode ? form.hospitalCode.toUpperCase() : '—' },
          { label: 'City',          value: form.city || 'Not specified' },
          { label: 'Database',      value: `${form.dbType.toUpperCase()} @ ${form.dbHost || '—'}:${form.dbPort}` },
          { label: 'DB Name',       value: form.dbName || '—' },
          { label: 'Tables',        value: tableCount > 0 ? `${tableCount} table${tableCount !== 1 ? 's' : ''}, ${totalCols} columns detected` : 'Schema detection skipped' },
          { label: 'FHIR Mappings', value: mappingRows.length > 0 ? `${mappingRows.length} field${mappingRows.length !== 1 ? 's' : ''} mapped` : 'AI mapping skipped — configure manually after onboarding' },
        ].map(r => (
          <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8125rem', gap: '1rem' }}>
            <span style={{ color: DARK.textMuted, flexShrink: 0 }}>{r.label}</span>
            <span style={{ fontWeight: 600, color: DARK.textPrimary, textAlign: 'right' }}>{r.value}</span>
          </div>
        ))}
      </div>

      <div style={{ background: DARK.greenBg, border: `1px solid ${DARK.greenBorder}`, borderRadius: '0.875rem', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {[
          'Row-Level Security (RLS) will be enabled for this tenant',
          'AES-256 encryption applied to all PHI fields',
          'CDC agent will start monitoring on the next sync cycle',
          'Tenant partition created in central FHIR database',
        ].map(item => (
          <div key={item} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: DARK.green }}>
            <CheckCircle2 style={{ width: 12, height: 12, flexShrink: 0 }} />{item}
          </div>
        ))}
      </div>

      {submitError && <WizardAlert type="error" message={submitError} />}
    </div>
  );

  const isLastStep = step === WIZARD_STEPS.length;

  // ── Page shell ────────────────────────────────────────────────────────────

  return (
    <div style={{ minHeight: '100vh', background: DARK.bg, fontFamily: "'Inter', system-ui, sans-serif", position: 'relative', overflowX: 'hidden' }}>

      {/* Background gradient blobs */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '-20%', left: '-10%', width: 600, height: 600, background: 'radial-gradient(circle, rgba(59,130,246,0.12) 0%, transparent 70%)', borderRadius: '50%' }} />
        <div style={{ position: 'absolute', bottom: '-15%', right: '-10%', width: 500, height: 500, background: 'radial-gradient(circle, rgba(99,102,241,0.10) 0%, transparent 70%)', borderRadius: '50%' }} />
      </div>

      {/* Navbar */}
      <nav style={{ position: 'fixed', top: 0, left: 0, right: 0, zIndex: 50, background: 'rgba(8,12,24,0.88)', backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', borderBottom: '1px solid rgba(255,255,255,0.06)', boxShadow: '0 4px 24px rgba(0,0,0,0.4)' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 1.5rem', height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
            <div style={{ width: 32, height: 32, borderRadius: '0.5rem', background: 'linear-gradient(135deg,#3b82f6,#6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Shield style={{ width: 16, height: 16, color: '#fff' }} />
            </div>
            <span style={{ fontSize: '1rem', fontWeight: 800, color: DARK.textPrimary, letterSpacing: '-0.02em' }}>CareLock</span>
          </div>

          {/* Back to home */}
          <button
            onClick={() => navigate(PUBLIC_ROUTES.HOME)}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'none', border: 'none', cursor: 'pointer', color: DARK.textSub, fontSize: '0.875rem', fontWeight: 500 }}
          >
            <ArrowLeft style={{ width: 15, height: 15 }} />
            Back to home
          </button>
        </div>
      </nav>

      {/* Page content */}
      <div style={{ position: 'relative', zIndex: 1, paddingTop: '6rem', paddingBottom: '4rem', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '6rem 1rem 4rem' }}>

        {/* Hero text */}
        {!done && (
          <div style={{ textAlign: 'center', marginBottom: '2.5rem', maxWidth: 540 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.375rem 0.875rem', background: DARK.blueBg, border: `1px solid ${DARK.blueBorder}`, borderRadius: '2rem', fontSize: '0.75rem', fontWeight: 600, color: DARK.blue, marginBottom: '1rem' }}>
              <Zap style={{ width: 11, height: 11 }} />
              Hospital Onboarding
            </div>
            <h1 style={{ margin: 0, fontSize: 'clamp(1.75rem,4vw,2.25rem)', fontWeight: 800, color: DARK.textPrimary, lineHeight: 1.15, letterSpacing: '-0.03em' }}>
              Connect your hospital<br />
              <span style={{ background: 'linear-gradient(90deg,#3b82f6,#a78bfa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                to the CareLock network
              </span>
            </h1>
            <p style={{ margin: '1rem 0 0', fontSize: '1rem', color: DARK.textSub, lineHeight: 1.6 }}>
              Set up your hospital tenant, connect your database, and let AI handle the FHIR mapping — all in under 5 minutes.
            </p>
          </div>
        )}

        {/* Wizard card */}
        <div style={{
          width: '100%', maxWidth: 580,
          background: DARK.cardBg,
          border: `1px solid ${DARK.cardBorder}`,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderRadius: '1.5rem',
          boxShadow: '0 24px 64px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06)',
          overflow: 'hidden',
        }}>

          {done ? (
            <SuccessScreen
              hospitalName={form.hospitalName}
              onSignIn={() => navigate(PUBLIC_ROUTES.LOGIN)}
            />
          ) : (
            <>
              {/* Header */}
              <div style={{ padding: '1.5rem 1.75rem', borderBottom: `1px solid ${DARK.divider}`, display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
                <div style={{ width: 38, height: 38, borderRadius: '0.75rem', background: 'linear-gradient(135deg,rgba(59,130,246,0.2),rgba(99,102,241,0.2))', border: `1px solid ${DARK.blueBorder}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <Building2 style={{ width: 18, height: 18, color: DARK.blue }} />
                </div>
                <div>
                  <h2 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: DARK.textPrimary }}>Onboard New Hospital</h2>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.75rem', color: DARK.textMuted }}>
                    Step {step} of {WIZARD_STEPS.length} — {WIZARD_STEPS[step - 1].label}
                  </p>
                </div>
              </div>

              {/* Progress bar */}
              <div style={{ padding: '1rem 1.75rem', borderBottom: `1px solid ${DARK.divider}`, display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {WIZARD_STEPS.map(s => (
                  <div key={s.n} style={{ flex: 1 }}>
                    <div style={{ height: 4, borderRadius: 2, background: step >= s.n ? DARK.accent : 'rgba(255,255,255,0.08)', transition: 'background 0.3s' }} />
                  </div>
                ))}
              </div>

              {/* Step labels */}
              <div style={{ padding: '0.75rem 1.75rem', borderBottom: `1px solid ${DARK.divider}`, display: 'flex', gap: '0.5rem' }}>
                {WIZARD_STEPS.map(s => (
                  <div key={s.n} style={{ flex: 1, textAlign: 'center', fontSize: '0.6rem', fontWeight: step === s.n ? 700 : 400, color: step === s.n ? DARK.blue : (step > s.n ? DARK.green : DARK.textMuted), transition: 'color 0.3s', lineHeight: 1.2 }}>
                    {step > s.n ? '✓' : s.n}. {s.label}
                  </div>
                ))}
              </div>

              {/* Body */}
              <div style={{ padding: '1.75rem' }}>
                {step === 1 && renderStep1()}
                {step === 2 && renderStep2()}
                {step === 3 && renderStep3()}
                {step === 4 && renderStep4()}
                {step === 5 && renderStep5()}
              </div>

              {/* Footer */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.75rem', borderTop: `1px solid ${DARK.divider}`, gap: '0.75rem' }}>
                <button
                  onClick={() => step > 1 ? setStep(s => s - 1) : navigate(PUBLIC_ROUTES.HOME)}
                  disabled={submitting}
                  style={{ ...btnSecondary, opacity: submitting ? 0.4 : 1, cursor: submitting ? 'not-allowed' : 'pointer' }}
                >
                  {step === 1 ? (
                    <><ArrowLeft style={{ width: 13, height: 13 }} />Back to Home</>
                  ) : (
                    <><ArrowLeft style={{ width: 13, height: 13 }} />Back</>
                  )}
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {/* Step 3 skip */}
                  {step === 3 && !detectedSchema.length && (
                    <button
                      onClick={() => setStep(4)}
                      style={{ ...btnOutline, fontSize: '0.75rem', padding: '0.5rem 0.875rem' }}
                    >
                      Skip
                    </button>
                  )}

                  <button
                    onClick={isLastStep ? handleSubmit : handleNext}
                    disabled={submitting}
                    style={{ ...btnPrimary, minWidth: 140, justifyContent: 'center', opacity: submitting ? 0.7 : 1, cursor: submitting ? 'not-allowed' : 'pointer' }}
                  >
                    {submitting ? (
                      <><Loader2 style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />Launching…</>
                    ) : isLastStep ? (
                      <><CheckCircle2 style={{ width: 14, height: 14 }} />Launch Hospital</>
                    ) : (
                      <>Continue<ArrowRight style={{ width: 14, height: 14 }} /></>
                    )}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Trust badges */}
        {!done && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', marginTop: '2rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            {[
              { icon: Shield, text: 'HIPAA Compliant' },
              { icon: Lock, text: 'AES-256 Encrypted' },
              { icon: Zap, text: 'Real-time CDC Sync' },
            ].map(({ icon: Icon, text }) => (
              <div key={text} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: DARK.textMuted }}>
                <Icon style={{ width: 13, height: 13, color: DARK.textMuted }} />
                {text}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Keyframe for spinner */}
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default HospitalOnboardingPage;
