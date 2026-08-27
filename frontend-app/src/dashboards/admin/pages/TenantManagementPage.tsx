import React, { useState, useMemo, useEffect, useCallback } from 'react';
import {
  Building2, PlusCircle, CheckCircle2, Users, Activity,
  ChevronRight, X, Wifi, Lock, ArrowRight, Eye, EyeOff,
  AlertCircle, Loader2,
} from 'lucide-react';
import { useApiData } from '../../../shared/hooks';
import { mapTenants } from '../../../shared/utils/mappers';
import { apiClient } from '../../../shared/services/apiClient';
import type { ApiError } from '../../../shared/services/apiClient';
import type { TenantInfo } from '../../../shared/types';
import ErrorBanner from '../../../shared/ui/ErrorBanner';

// ── Local UI types ───────────────────────────────────────────────────────────

interface Tenant {
  id: number; name: string; code: string; city: string; dbType: string;
  status: 'active' | 'pending' | 'error' | 'syncing';
  patients: number; syncRate: number; lastSync: string;
  onboardedAt: string; rlsEnabled: boolean; cdcActive: boolean;
}

interface SchemaTable { name: string; cols: number; rows: string }

interface MappingRow { src: string; fhir: string; conf: number }

// ── Wizard form state ────────────────────────────────────────────────────────

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

// ── Constants ────────────────────────────────────────────────────────────────

const STATUS_CHIP: Record<Tenant['status'], { bg: string; color: string; border: string }> = {
  active:  { bg: 'var(--ds-status-active-bg)',   color: 'var(--ds-status-active-text)',   border: 'rgba(16,185,129,0.25)' },
  syncing: { bg: 'var(--ds-status-syncing-bg)',  color: 'var(--ds-status-syncing-text)',  border: 'rgba(59,130,246,0.25)' },
  error:   { bg: 'var(--ds-status-error-bg)',    color: 'var(--ds-status-error-text)',    border: 'rgba(239,68,68,0.25)' },
  pending: { bg: 'var(--ds-status-pending-bg)',  color: 'var(--ds-status-pending-text)',  border: 'rgba(245,158,11,0.25)' },
};

const WIZARD_STEPS = [
  { n: 1, label: 'Hospital Info' },
  { n: 2, label: 'DB Connection' },
  { n: 3, label: 'Schema Detection' },
  { n: 4, label: 'AI Mapping' },
  { n: 5, label: 'Review & Launch' },
];

// ── Shared inline styles ─────────────────────────────────────────────────────

const inp: React.CSSProperties = {
  width: '100%', padding: '0.5rem 0.75rem',
  background: 'var(--ds-surface)', border: '1px solid var(--ds-border)',
  borderRadius: '0.625rem', fontSize: '0.8125rem',
  color: 'var(--ds-text-primary)', outline: 'none',
  boxSizing: 'border-box', fontFamily: 'inherit',
};
const inpErr: React.CSSProperties = { ...inp, border: '1px solid #ef4444' };
const lbl: React.CSSProperties = {
  display: 'block', fontSize: '0.75rem', fontWeight: 600,
  color: 'var(--ds-text-secondary)', marginBottom: '0.25rem',
};
const errTxt: React.CSSProperties = {
  fontSize: '0.6875rem', color: '#ef4444', marginTop: '0.25rem',
};

// ── Wizard helpers ───────────────────────────────────────────────────────────

function normaliseSchemaResponse(raw: unknown): SchemaTable[] {
  if (!raw || typeof raw !== 'object') return [];
  const r = raw as Record<string, unknown>;

  // Shape A: { tables: { tableName: { columns: [...], row_count: N } } }
  if (r.tables && typeof r.tables === 'object') {
    return Object.entries(r.tables as Record<string, any>).map(([name, info]) => ({
      name,
      cols: Array.isArray(info?.columns) ? info.columns.length : (info?.column_count ?? 0),
      rows: info?.row_count != null ? Number(info.row_count).toLocaleString() : '—',
    }));
  }

  // Shape B: { tableName: { columns: [...] } }
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

// ── Inline error/info banners used inside the wizard ────────────────────────

const WizardAlert: React.FC<{ type: 'error' | 'warning' | 'info'; message: string }> = ({ type, message }) => {
  const colours = {
    error:   { bg: 'rgba(239,68,68,0.1)',    border: 'rgba(239,68,68,0.3)',    color: '#ef4444' },
    warning: { bg: 'rgba(245,158,11,0.1)',   border: 'rgba(245,158,11,0.3)',   color: '#f59e0b' },
    info:    { bg: 'rgba(59,130,246,0.1)',   border: 'rgba(59,130,246,0.3)',   color: '#60a5fa' },
  }[type];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.625rem', padding: '0.75rem', borderRadius: '0.75rem', background: colours.bg, border: `1px solid ${colours.border}` }}>
      <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, marginTop: 1, color: colours.color }} />
      <span style={{ fontSize: '0.8125rem', color: colours.color, lineHeight: 1.45 }}>{message}</span>
    </div>
  );
};

// ── OnboardWizard ────────────────────────────────────────────────────────────

interface OnboardWizardProps {
  onClose: () => void;
  onTenantCreated: () => void;
}

const OnboardWizard: React.FC<OnboardWizardProps> = ({ onClose, onTenantCreated }) => {
  const [step, setStep] = useState(1);
  const [showPw, setShowPw] = useState(false);

  // ── Form data ──────────────────────────────────────────────────────────────
  const [form, setForm] = useState<WizardForm>({
    hospitalName: '', hospitalCode: '', city: '',
    dbType: 'postgresql', dbHost: '', dbPort: '5432',
    dbName: '', dbUser: '', dbPass: '',
  });
  const [errors, setErrors] = useState<WizardErrors>({});

  const set = (k: keyof WizardForm, v: string) =>
    setForm(f => ({
      ...f,
      [k]: v,
      ...(k === 'dbType' ? { dbPort: DEFAULT_PORTS[v as DBType] } : {}),
    }));

  // ── Step 3 — Schema Detection ──────────────────────────────────────────────
  const [detecting, setDetecting]         = useState(false);
  const [schemaRaw, setSchemaRaw]         = useState<unknown>(null);
  const [detectedSchema, setDetectedSchema] = useState<SchemaTable[]>([]);
  const [schemaError, setSchemaError]     = useState<string | null>(null);

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
      if (tables.length === 0) {
        setSchemaError('Schema endpoint returned no tables. Ensure the hospital DB is reachable and the connector is configured.');
      }
    } catch (err) {
      const e = err as ApiError;
      setSchemaError(e.userMessage ?? e.message ?? 'Schema detection failed. Check backend connectivity.');
    } finally {
      setDetecting(false);
    }
  }, []);

  // ── Step 4 — AI Mapping ────────────────────────────────────────────────────
  const [mappingLoading, setMappingLoading]     = useState(false);
  const [mappingRows, setMappingRows]           = useState<MappingRow[]>([]);
  const [mappingError, setMappingError]         = useState<string | null>(null);
  const [mappingFetched, setMappingFetched]     = useState(false);

  const fetchMapping = useCallback(async () => {
    if (mappingFetched) return;
    setMappingLoading(true);
    setMappingError(null);

    // Pick the first detected table, or fall back to a generic patient schema.
    const tableName = detectedSchema[0]?.name ?? 'patients';
    const columns = extractColumnsForTable(schemaRaw, tableName);
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
        table_name:    tableName,
        columns:       colsPayload,
        fhir_resource: 'Patient',
      });
      const rows = normaliseMappings(result);
      setMappingRows(rows);
      if (rows.length === 0) {
        setMappingError('AI mapping returned no suggestions. The RAG engine may still be initialising — you can proceed and map manually later.');
      }
    } catch (err) {
      const e = err as ApiError;
      setMappingError(
        e.userMessage ?? e.message ??
        'AI mapping service is unavailable. You can proceed and configure mappings later.',
      );
    } finally {
      setMappingLoading(false);
      setMappingFetched(true);
    }
  }, [detectedSchema, schemaRaw, mappingFetched]);

  // Automatically kick off mapping when step 4 becomes active.
  useEffect(() => {
    if (step === 4) {
      fetchMapping();
    }
  }, [step, fetchMapping]);

  // ── Step 5 — Submission ────────────────────────────────────────────────────
  const [submitting, setSubmitting]   = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // ── Validation ────────────────────────────────────────────────────────────

  const validateStep1 = (): boolean => {
    const e: WizardErrors = {};
    if (!form.hospitalName.trim())
      e.hospitalName = 'Hospital name is required';
    if (!form.hospitalCode.trim())
      e.hospitalCode = 'Hospital code is required';
    else if (form.hospitalCode.trim().length < 2)
      e.hospitalCode = 'Code must be at least 2 characters';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const validateStep2 = (): boolean => {
    const e: WizardErrors = {};
    if (!form.dbHost.trim())  e.dbHost = 'Host is required';
    if (!form.dbName.trim())  e.dbName = 'Database name is required';
    if (!form.dbUser.trim())  e.dbUser = 'Username is required';
    if (!form.dbPass.trim())  e.dbPass = 'Password is required';
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
    // Re-validate all required fields before final submission.
    const v1 = validateStep1();
    const v2 = validateStep2();
    if (!v1 || !v2) {
      setSubmitError('Some required fields are missing. Please go back and complete them.');
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      // ── Block submission when backend is offline ──────────────────────────
      const healthy = await apiClient.isBackendHealthy();
      if (!healthy) {
        setSubmitError(
          'Backend is currently unavailable. Submission is blocked to prevent data loss. ' +
          'Please wait for the service to recover and try again.',
        );
        return;
      }

      // ── Call the real API ─────────────────────────────────────────────────
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

      // Success — notify parent to refresh the list, then close.
      onTenantCreated();
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

  // ── Render helpers ────────────────────────────────────────────────────────

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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ margin: 0, fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ds-text-primary)' }}>Hospital Information</h3>
      <Field label="Hospital Name *" fieldKey="hospitalName" placeholder="e.g. City General Hospital" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        <Field label="Hospital Code *" fieldKey="hospitalCode" placeholder="CGH" maxLength={10}
               style={{ fontFamily: 'monospace' }} />
        <Field label="City" fieldKey="city" placeholder="Karachi" />
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ margin: 0, fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ds-text-primary)' }}>Database Connection</h3>
      <div>
        <label style={lbl}>Database Engine</label>
        <select
          value={form.dbType}
          onChange={e => set('dbType', e.target.value)}
          style={{ ...inp, background: 'var(--ds-surface)' }}
        >
          {(['postgresql', 'mysql', 'mongodb', 'sqlserver', 'oracle'] as DBType[]).map(t => (
            <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
          ))}
        </select>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0.75rem' }}>
        <Field label="Host *" fieldKey="dbHost" placeholder="localhost" />
        <Field label="Port" fieldKey="dbPort" placeholder="5432" style={{ fontFamily: 'monospace' }} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
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
            style={{ position: 'absolute', right: '0.625rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ds-text-muted)', display: 'flex' }}
          >
            {showPw ? <EyeOff style={{ width: 14, height: 14 }} /> : <Eye style={{ width: 14, height: 14 }} />}
          </button>
        </div>
        {errors.dbPass && <p style={errTxt}>{errors.dbPass}</p>}
        <p style={{ margin: '0.25rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
          Connection string is encrypted with AES-256 before storage.
        </p>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ margin: 0, fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ds-text-primary)' }}>Schema Auto-Detection</h3>
      <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
        The CDC agent will connect to the hospital database and automatically discover all tables, columns, and relationships.
      </p>

      {!detectedSchema.length && !detecting && !schemaError && (
        <button onClick={runDetection} className="ds-btn ds-btn-primary">
          <Wifi style={{ width: 13, height: 13 }} />Connect &amp; Detect Schema
        </button>
      )}

      {detecting && (
        <div style={{ background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.25)', borderRadius: '0.75rem', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
            <Loader2 style={{ width: 18, height: 18, color: '#60a5fa', animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#60a5fa' }}>Connecting to database…</span>
          </div>
          {['Testing connection', 'Listing tables', 'Reading columns', 'Detecting indexes'].map(m => (
            <div key={m} style={{ fontSize: '0.75rem', color: '#60a5fa', fontFamily: 'monospace', padding: '0.15rem 0' }}>
              ● {m}
            </div>
          ))}
        </div>
      )}

      {schemaError && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <WizardAlert type="error" message={schemaError} />
          <button onClick={runDetection} className="ds-btn">
            <Wifi style={{ width: 13, height: 13 }} />Retry Detection
          </button>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
            You can also skip this step and proceed — schema can be configured later.
          </p>
        </div>
      )}

      {detectedSchema.length > 0 && !detecting && (
        <div style={{ background: 'var(--ds-status-active-bg)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.75rem', padding: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--ds-status-active-text)', fontWeight: 700, fontSize: '0.875rem', marginBottom: '0.75rem' }}>
            <CheckCircle2 style={{ width: 15, height: 15 }} />
            Schema detected — {detectedSchema.length} table{detectedSchema.length !== 1 ? 's' : ''} found
          </div>
          {detectedSchema.map(t => (
            <div key={t.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--ds-card-bg)', borderRadius: '0.5rem', padding: '0.5rem 0.75rem', marginTop: '0.375rem' }}>
              <span style={{ fontFamily: 'monospace', fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{t.name}</span>
              <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
                {t.cols > 0 ? `${t.cols} cols` : 'cols unknown'} · {t.rows} rows
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderStep4 = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ margin: 0, fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ds-text-primary)' }}>AI Mapping Suggestions</h3>
      <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
        The AI engine analyses the detected schema and generates FHIR R4 field mapping suggestions.
      </p>

      {mappingLoading && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem', background: 'rgba(59,130,246,0.08)', borderRadius: '0.75rem', border: '1px solid rgba(59,130,246,0.2)' }}>
          <Loader2 style={{ width: 18, height: 18, color: '#60a5fa', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontSize: '0.875rem', color: '#60a5fa', fontWeight: 600 }}>Generating FHIR mapping suggestions…</span>
        </div>
      )}

      {mappingError && !mappingLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <WizardAlert type="warning" message={mappingError} />
          <button onClick={() => { setMappingFetched(false); fetchMapping(); }} className="ds-btn">
            Retry AI Mapping
          </button>
        </div>
      )}

      {mappingRows.length > 0 && !mappingLoading && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          {mappingRows.map(m => (
            <div key={m.src} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--ds-table-head-bg)', borderRadius: '0.75rem', padding: '0.625rem 0.75rem' }}>
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: 'var(--ds-text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.src}</span>
              <ArrowRight style={{ width: 11, height: 11, color: 'var(--ds-text-muted)', flexShrink: 0 }} />
              <span style={{ fontSize: '0.6875rem', fontFamily: 'monospace', color: '#60a5fa', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.fhir}</span>
              <span style={{
                fontSize: '0.6875rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '2rem', flexShrink: 0,
                background: m.conf >= 90 ? 'var(--ds-status-active-bg)' : 'var(--ds-status-pending-bg)',
                color:      m.conf >= 90 ? 'var(--ds-status-active-text)' : 'var(--ds-status-pending-text)',
              }}>{m.conf}%</span>
              <CheckCircle2 style={{ width: 13, height: 13, color: '#34d399', flexShrink: 0 }} />
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ margin: 0, fontWeight: 700, fontSize: '0.9375rem', color: 'var(--ds-text-primary)' }}>Review &amp; Launch</h3>
      <div style={{ background: 'var(--ds-table-head-bg)', borderRadius: '0.75rem', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
        {[
          { label: 'Hospital',     value: form.hospitalName || '—' },
          { label: 'Code',         value: form.hospitalCode ? form.hospitalCode.toUpperCase() : '—' },
          { label: 'City',         value: form.city || 'Not specified' },
          { label: 'Database',     value: `${form.dbType.toUpperCase()} @ ${form.dbHost || '—'}:${form.dbPort}` },
          { label: 'DB Name',      value: form.dbName || '—' },
          {
            label: 'Tables',
            value: tableCount > 0
              ? `${tableCount} table${tableCount !== 1 ? 's' : ''}, ${totalCols} columns detected`
              : 'Schema detection skipped',
          },
          {
            label: 'FHIR Mappings',
            value: mappingRows.length > 0
              ? `${mappingRows.length} field${mappingRows.length !== 1 ? 's' : ''} mapped`
              : 'AI mapping skipped — configure manually after onboarding',
          },
        ].map(r => (
          <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8125rem' }}>
            <span style={{ color: 'var(--ds-text-muted)' }}>{r.label}</span>
            <span style={{ fontWeight: 600, color: 'var(--ds-text-primary)', textAlign: 'right', maxWidth: '60%' }}>{r.value}</span>
          </div>
        ))}
      </div>

      <div style={{ background: 'var(--ds-status-active-bg)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '0.75rem', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {[
          'Row-Level Security (RLS) will be enabled for this tenant',
          'AES-256 encryption applied to all PHI fields',
          'CDC agent will start monitoring on the next sync cycle',
          'Tenant partition created in central FHIR database',
        ].map(item => (
          <div key={item} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-status-active-text)' }}>
            <CheckCircle2 style={{ width: 12, height: 12, flexShrink: 0 }} />{item}
          </div>
        ))}
      </div>

      {submitError && <WizardAlert type="error" message={submitError} />}
    </div>
  );

  // ── Wizard shell ──────────────────────────────────────────────────────────

  const isLastStep = step === WIZARD_STEPS.length;

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
      <div style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1.25rem', boxShadow: '0 24px 64px rgba(0,0,0,0.5)', width: '100%', maxWidth: 600, maxHeight: '90vh', overflowY: 'auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--ds-table-border)' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '0.9375rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Onboard New Hospital</h2>
            <p style={{ margin: '0.2rem 0 0', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>Step {step} of {WIZARD_STEPS.length} — {WIZARD_STEPS[step - 1].label}</p>
          </div>
          <button onClick={onClose} disabled={submitting} style={{ background: 'none', border: 'none', cursor: submitting ? 'not-allowed' : 'pointer', color: 'var(--ds-text-muted)', display: 'flex', opacity: submitting ? 0.4 : 1 }}>
            <X style={{ width: 18, height: 18 }} />
          </button>
        </div>

        {/* Progress bar */}
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--ds-table-border)', display: 'flex', gap: '0.5rem' }}>
          {WIZARD_STEPS.map(s => (
            <div key={s.n} style={{ flex: 1 }}>
              <div style={{ height: 4, borderRadius: 2, background: step >= s.n ? '#3b82f6' : 'var(--ds-table-head-bg)', transition: 'background 0.3s' }} />
            </div>
          ))}
        </div>

        {/* Body */}
        <div style={{ padding: '1.5rem' }}>
          {step === 1 && renderStep1()}
          {step === 2 && renderStep2()}
          {step === 3 && renderStep3()}
          {step === 4 && renderStep4()}
          {step === 5 && renderStep5()}
        </div>

        {/* Footer */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 1.5rem', borderTop: '1px solid var(--ds-table-border)', gap: '0.75rem' }}>
          <button
            onClick={() => step > 1 ? setStep(s => s - 1) : onClose()}
            disabled={submitting}
            className="ds-btn"
            style={{ opacity: submitting ? 0.4 : 1 }}
          >
            {step === 1 ? 'Cancel' : 'Back'}
          </button>

          <button
            onClick={isLastStep ? handleSubmit : handleNext}
            disabled={submitting}
            className="ds-btn ds-btn-primary"
            style={{ minWidth: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.375rem', opacity: submitting ? 0.7 : 1, cursor: submitting ? 'not-allowed' : 'pointer' }}
          >
            {submitting ? (
              <>
                <Loader2 style={{ width: 13, height: 13, animation: 'spin 1s linear infinite' }} />
                Launching…
              </>
            ) : isLastStep ? (
              <>
                <CheckCircle2 style={{ width: 13, height: 13 }} />
                Launch Hospital
              </>
            ) : (
              <>
                Continue
                <ArrowRight style={{ width: 13, height: 13 }} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

// ── TenantManagementPage ──────────────────────────────────────────────────────

const TenantManagementPage: React.FC = () => {
  const [showWizard, setShowWizard] = useState(false);
  const [selected, setSelected]     = useState<Tenant | null>(null);

  const tenantsData = useApiData<TenantInfo[]>('/api/v1/tenants');

  const tenants = useMemo(() => {
    if (!tenantsData.data || !Array.isArray(tenantsData.data)) return [];
    return mapTenants(tenantsData.data);
  }, [tenantsData.data]);

  const totalPatients = tenants.reduce((s, t) => s + t.patients, 0);
  const activeTenants = tenants.filter(t => t.status === 'active').length;
  const avgSyncRate   = tenants.length > 0
    ? Math.round(tenants.reduce((s, t) => s + t.syncRate, 0) / tenants.length * 10) / 10
    : 0;

  const KPI_ICONS = [
    { label: 'Total Tenants',   value: tenants.length.toString(),        icon: <Building2   style={{ width: 15, height: 15 }} />, color: '#2dd4bf', bg: 'rgba(20,184,166,0.18)' },
    { label: 'Active',          value: activeTenants.toString(),         icon: <CheckCircle2 style={{ width: 15, height: 15 }} />, color: '#34d399', bg: 'rgba(16,185,129,0.18)' },
    { label: 'Total Patients',  value: totalPatients.toLocaleString(),   icon: <Users        style={{ width: 15, height: 15 }} />, color: '#60a5fa', bg: 'rgba(59,130,246,0.18)' },
    { label: 'Avg Sync Rate',   value: `${avgSyncRate}%`,                icon: <Activity     style={{ width: 15, height: 15 }} />, color: '#c084fc', bg: 'rgba(192,132,252,0.18)' },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', fontFamily: "'Inter',sans-serif" }}>

      {showWizard && (
        <OnboardWizard
          onClose={() => setShowWizard(false)}
          onTenantCreated={() => {
            setShowWizard(false);
            tenantsData.refetch();
          }}
        />
      )}

      <div className="ds-animate" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em' }}>Hospital Tenants</h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
            {tenants.length} hospital{tenants.length !== 1 ? 's' : ''} onboarded · All with RLS isolation
          </p>
        </div>
        <button onClick={() => setShowWizard(true)} className="ds-btn ds-btn-primary">
          <PlusCircle style={{ width: 13, height: 13 }} />Onboard Hospital
        </button>
      </div>

      {tenantsData.error && (
        <ErrorBanner
          message="Failed to load hospitals"
          detail={tenantsData.error.userMessage || tenantsData.error.message || 'Failed to load hospitals'}
          onRetry={tenantsData.refetch}
        />
      )}

      <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(180px,1fr))', gap: '1rem' }}>
        {KPI_ICONS.map(k => (
          <div key={k.label} style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '1rem 1.25rem', display: 'flex', alignItems: 'center', gap: '0.875rem' }}>
            <div style={{ width: 38, height: 38, background: k.bg, borderRadius: '0.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, color: k.color }}>{k.icon}</div>
            <div>
              <div style={{ fontSize: '1.375rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', lineHeight: 1.1 }}>{k.value}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{k.label}</div>
            </div>
          </div>
        ))}
      </div>

      {tenantsData.loading && (
        <div className="ds-animate ds-animate-d2" style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)' }}>
          Loading hospitals…
        </div>
      )}

      {!tenantsData.loading && !tenantsData.error && tenants.length === 0 && (
        <div className="ds-animate ds-animate-d2" style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)' }}>
          No hospitals onboarded yet
        </div>
      )}

      {!tenantsData.loading && !tenantsData.error && tenants.length > 0 && (
        <div className="ds-animate ds-animate-d2" style={{ background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem', boxShadow: 'var(--ds-card-shadow)', overflow: 'hidden' }}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--ds-table-border)' }}>
            <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>All Onboarded Hospitals</h2>
          </div>
          {tenants.map(t => (
            <div
              key={t.id}
              onClick={() => setSelected(selected?.id === t.id ? null : t)}
              className="ds-table-row"
              style={{ padding: '1rem 1.25rem', cursor: 'pointer' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ width: 44, height: 44, background: 'linear-gradient(135deg,#3b82f6,#6366f1)', borderRadius: '0.875rem', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.625rem', fontWeight: 800, flexShrink: 0 }}>{t.code}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{t.name}</span>
                    <span style={{ fontSize: '0.625rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', border: `1px solid ${STATUS_CHIP[t.status].border}`, background: STATUS_CHIP[t.status].bg, color: STATUS_CHIP[t.status].color, textTransform: 'capitalize' }}>{t.status}</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', marginTop: '0.2rem' }}>{t.city} · {t.dbType} · {t.patients.toLocaleString()} patients</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexShrink: 0 }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{t.syncRate}%</div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>sync rate</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>{t.lastSync}</div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>last sync</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                    {t.rlsEnabled && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.625rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)' }}><Lock style={{ width: 9, height: 9 }} />RLS</span>}
                    {t.cdcActive && <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.625rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-syncing-bg)', color: 'var(--ds-status-syncing-text)', border: '1px solid rgba(59,130,246,0.25)' }}><Activity style={{ width: 9, height: 9 }} />CDC</span>}
                  </div>
                  <ChevronRight style={{ width: 14, height: 14, color: 'var(--ds-text-muted)', transform: selected?.id === t.id ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
                </div>
              </div>
              {selected?.id === t.id && (
                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--ds-table-border)', display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(140px,1fr))', gap: '0.75rem' }}>
                  {[
                    { label: 'Hospital Code', value: t.code },
                    { label: 'Onboarded',     value: t.onboardedAt },
                    { label: 'DB Engine',     value: t.dbType },
                    { label: 'Tenant ID',     value: `#${t.id}` },
                  ].map(d => (
                    <div key={d.label} style={{ background: 'var(--ds-table-head-bg)', borderRadius: '0.75rem', padding: '0.75rem' }}>
                      <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginBottom: '0.25rem' }}>{d.label}</div>
                      <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{d.value}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TenantManagementPage;
