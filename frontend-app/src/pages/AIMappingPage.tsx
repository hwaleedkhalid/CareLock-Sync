/**
 * AIMappingPage — Dark glassmorphism, full ds-* design system.
 * AI Schema Mapping powered by llama3.2:3b (local Ollama, no API key).
 */
import React, { useState, useEffect, useCallback } from 'react';
import { ragApi } from '../shared/services/api';
import ErrorBanner from '../shared/ui/ErrorBanner';
import {
  Brain, Check, X, ChevronDown, ChevronUp, Loader2,
  AlertCircle, CheckCircle2, Plus, Trash2, Zap, Database,
  Info, WifiOff,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────
type MappingMethod  = 'retrieval' | 'rag';
type ReviewStatus   = 'pending' | 'approved' | 'rejected';

interface ColumnDef        { name: string; type: string; }
interface SimilarMapping   { source_field: string; target_path: string; similarity: number; }
interface MappingSuggestion {
  source_field: string; source_type: string; target_path: string;
  fhir_resource: string; confidence: number; transformation: string;
  reasoning?: string; similar_mappings?: SimilarMapping[];
  method?: MappingMethod; status: ReviewStatus;
}
interface BackendStats { total: number; high: number; medium: number; low: number; }
interface SchemaSuggestionResult {
  table_name: string; fhir_resource: string;
  mappings: MappingSuggestion[]; statistics: BackendStats; accuracy_pct: number;
}
interface RagStatus {
  status: 'operational' | 'unavailable';
  mapping_model: string; chat_model: string;
  mapping_available: boolean; total_mappings: number;
}
interface KnowledgeStats {
  mapping_model: string; chat_model: string;
  vector_store_mappings: number; knowledge_base_entries: number; resources_covered: string[];
}
interface SchemaDraft { tableName: string; fhirResource: string; columns: ColumnDef[]; }

// ── Constants ─────────────────────────────────────────────────────────────────
const FHIR_RESOURCES   = ['Patient', 'Encounter', 'Observation', 'MedicationRequest'];
const COLUMN_TYPES     = ['varchar', 'integer', 'date', 'datetime', 'boolean', 'decimal', 'text'];
const SCHEMA_CACHE_KEY = 'carelock_schema_draft';
const DEFAULT_COLUMNS: ColumnDef[] = [
  { name: 'patient_id',    type: 'integer' },
  { name: 'date_of_birth', type: 'date'    },
  { name: 'first_name',    type: 'varchar' },
  { name: 'last_name',     type: 'varchar' },
  { name: 'phone_number',  type: 'varchar' },
];

function loadSchemaDraft(): SchemaDraft | null {
  try { const r = localStorage.getItem(SCHEMA_CACHE_KEY); return r ? JSON.parse(r) : null; }
  catch { return null; }
}
function saveSchemaDraft(d: SchemaDraft) {
  try { localStorage.setItem(SCHEMA_CACHE_KEY, JSON.stringify(d)); } catch { /* ignore */ }
}

// ── Design helpers ────────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: 'var(--ds-card-bg)',
  backdropFilter: 'var(--ds-card-blur)',
  WebkitBackdropFilter: 'var(--ds-card-blur)' as any,
  border: '1px solid var(--ds-card-border)',
  borderRadius: '1rem',
  boxShadow: 'var(--ds-card-shadow)',
};

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--ds-surface)', border: '1px solid var(--ds-border)',
  borderRadius: '0.5rem', padding: '0.5rem 0.75rem', fontSize: '0.8125rem',
  color: 'var(--ds-text-primary)', fontFamily: 'inherit', outline: 'none',
  boxSizing: 'border-box', transition: 'border-color 0.2s, box-shadow 0.2s',
};

// ── Sub-components ────────────────────────────────────────────────────────────
const ConfidenceBadge: React.FC<{ value: number }> = ({ value }) => {
  const pct = Math.round(value * 100);
  const bg    = pct >= 90 ? 'var(--ds-status-active-bg)'  : pct >= 75 ? 'var(--ds-status-pending-bg)'  : 'var(--ds-status-error-bg)';
  const color = pct >= 90 ? 'var(--ds-status-active-text)' : pct >= 75 ? 'var(--ds-status-pending-text)' : 'var(--ds-status-error-text)';
  const border = pct >= 90 ? 'rgba(16,185,129,0.3)' : pct >= 75 ? 'rgba(245,158,11,0.3)' : 'rgba(239,68,68,0.3)';
  return (
    <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: bg, color, border: `1px solid ${border}`, fontVariantNumeric: 'tabular-nums' }}>
      {pct}%
    </span>
  );
};

const AccuracyBar: React.FC<{ pct: number }> = ({ pct }) => {
  const r = Math.round(pct);
  const color = r >= 80 ? 'var(--ds-accent-green)' : r >= 50 ? 'var(--ds-accent-orange)' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
      <span style={{ width: 80, textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>{r}% accuracy</span>
      <div style={{ width: 96, height: 5, background: 'var(--ds-table-border)', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.min(r, 100)}%`, background: color, borderRadius: 999, transition: 'width 0.7s ease' }} />
      </div>
    </div>
  );
};

const MethodBadge: React.FC<{ method?: MappingMethod }> = ({ method }) => {
  if (!method) return null;
  const isRetrieval = method === 'retrieval';
  return (
    <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: isRetrieval ? 'rgba(59,130,246,0.12)' : 'rgba(139,92,246,0.12)', color: isRetrieval ? 'var(--ds-accent-blue)' : 'var(--ds-accent-purple)', border: `1px solid ${isRetrieval ? 'rgba(59,130,246,0.25)' : 'rgba(139,92,246,0.25)'}` }}>
      {isRetrieval ? '⚡ retrieval' : '🤖 llama3.2:3b'}
    </span>
  );
};

const OllamaStatusBanner: React.FC<{ status: RagStatus | null; loading: boolean }> = ({ status, loading }) => {
  if (loading) return null;
  if (!status) return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--ds-status-pending-bg)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '0.75rem', padding: '0.75rem 1rem', fontSize: '0.8125rem', color: 'var(--ds-status-pending-text)' }}>
      <WifiOff style={{ width: 14, height: 14, flexShrink: 0 }} />
      Cannot reach backend. Start FastAPI on <code style={{ background: 'rgba(245,158,11,0.15)', borderRadius: '0.25rem', padding: '0 0.25rem', fontFamily: 'monospace' }}>localhost:8000</code>.
    </div>
  );
  if (status.status !== 'operational') return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', background: 'var(--ds-status-pending-bg)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '0.75rem', padding: '0.75rem 1rem', fontSize: '0.8125rem', color: 'var(--ds-status-pending-text)' }}>
      <AlertCircle style={{ width: 14, height: 14, flexShrink: 0, marginTop: 2 }} />
      <div>
        <p style={{ margin: 0, fontWeight: 700 }}>Ollama is offline — AI mapping unavailable</p>
        <p style={{ margin: '0.25rem 0 0.375rem' }}>Run <code style={{ fontFamily: 'monospace', background: 'rgba(245,158,11,0.15)', borderRadius: 3, padding: '0 4px' }}>ollama serve</code> then pull the models:</p>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <code style={{ background: 'rgba(245,158,11,0.15)', borderRadius: 3, padding: '2px 8px', fontFamily: 'monospace', fontSize: '0.75rem' }}>ollama pull llama3.2:3b</code>
          <code style={{ background: 'rgba(245,158,11,0.15)', borderRadius: 3, padding: '2px 8px', fontFamily: 'monospace', fontSize: '0.75rem' }}>ollama pull phi3</code>
        </div>
      </div>
    </div>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--ds-status-active-bg)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '0.75rem', padding: '0.625rem 1rem', fontSize: '0.8125rem', color: 'var(--ds-status-active-text)', flexWrap: 'wrap' }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--ds-accent-green)', flexShrink: 0, animation: 'pulse 2s infinite' }} />
      <strong>Ollama operational</strong>
      <span style={{ opacity: 0.5 }}>·</span>
      <span>Mapping: <strong>{status.mapping_model}</strong></span>
      <span style={{ opacity: 0.5 }}>·</span>
      <span>Chat: <strong>{status.chat_model}</strong></span>
      <span style={{ opacity: 0.5 }}>·</span>
      <span><strong>{status.total_mappings}</strong> vectors in ChromaDB</span>
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────
const AIMappingPage: React.FC = () => {
  const cached = loadSchemaDraft();

  const [tableName, setTableName]           = useState(cached?.tableName    ?? 'patients');
  const [fhirResource, setFhirResource]     = useState(cached?.fhirResource ?? 'Patient');
  const [columns, setColumns]               = useState<ColumnDef[]>(cached?.columns ?? DEFAULT_COLUMNS);
  const [result, setResult]                 = useState<SchemaSuggestionResult | null>(null);
  const [loading, setLoading]               = useState(false);
  const [saving, setSaving]                 = useState(false);
  const [savedCount, setSavedCount]         = useState<number | null>(null);
  const [error, setError]                   = useState('');
  const [expandedRow, setExpandedRow]       = useState<string | null>(null);
  const [ragStatus, setRagStatus]           = useState<RagStatus | null>(null);
  const [statusLoading, setStatusLoading]   = useState(true);
  const [knowledgeStats, setKnowledgeStats] = useState<KnowledgeStats | null>(null);

  useEffect(() => {
    ragApi.status()
      .then((s) => setRagStatus(s as RagStatus))
      .catch((err) => {
        console.warn('[AIMappingPage] RAG status check failed:', err);
        setRagStatus(null);
      })
      .finally(() => setStatusLoading(false));
    ragApi.knowledgeStats()
      .then((s) => setKnowledgeStats(s as KnowledgeStats))
      .catch((err) => {
        console.warn('[AIMappingPage] Failed to load knowledge stats:', err);
      });
  }, []);

  useEffect(() => { saveSchemaDraft({ tableName, fhirResource, columns }); }, [tableName, fhirResource, columns]);

  const addColumn    = () => setColumns((p) => [...p, { name: '', type: 'varchar' }]);
  const removeColumn = (i: number) => setColumns((p) => p.filter((_, idx) => idx !== i));
  const updateColumn = (i: number, field: keyof ColumnDef, value: string) =>
    setColumns((p) => p.map((c, idx) => (idx === i ? { ...c, [field]: value } : c)));

  const runSuggestion = useCallback(async () => {
    if (loading) return;
    setLoading(true); setError(''); setResult(null); setSavedCount(null); setExpandedRow(null);
    try {
      const validCols = columns.filter((c) => c.name.trim());
      const data = await ragApi.suggestSchema(tableName, validCols, fhirResource);
      const mappings: MappingSuggestion[] = (data.mappings ?? []).map(
        (m: Omit<MappingSuggestion, 'status'>) => ({ ...m, status: 'pending' as ReviewStatus }),
      );
      setResult({ table_name: data.table_name, fhir_resource: data.fhir_resource, mappings, statistics: data.statistics ?? { total: mappings.length, high: 0, medium: 0, low: 0 }, accuracy_pct: data.accuracy_pct ?? 0 });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Failed to get suggestions. Is Ollama running? Try: ollama serve');
    } finally { setLoading(false); }
  }, [loading, tableName, fhirResource, columns]);

  const toggleStatus = (field: string, next: ReviewStatus) => {
    if (!result) return;
    setResult({ ...result, mappings: result.mappings.map((m) => m.source_field === field ? { ...m, status: m.status === next ? 'pending' : next } : m) });
  };
  const approveAll = () => {
    if (!result) return;
    setResult({ ...result, mappings: result.mappings.map((m) => ({ ...m, status: 'approved' })) });
  };

  const saveMappings = useCallback(async () => {
    if (!result || saving) return;
    const confirmedFields = result.mappings.filter((m) => m.status === 'approved').map((m) => m.source_field);
    if (confirmedFields.length === 0) { setError('Approve at least one mapping before saving.'); return; }
    setSaving(true); setError('');
    try {
      const rawMappings = result.mappings.map(({ status: _s, ...rest }) => rest);
      const res = await ragApi.confirmBatch(rawMappings, confirmedFields);
      setSavedCount(res.total_saved);
      setResult({ ...result, mappings: result.mappings.map((m) => m.status === 'approved' ? { ...m, status: 'pending' } : m) });
      // Refresh RAG status after save (non-critical, log any failures)
      ragApi.status()
        .then((s) => setRagStatus(s as RagStatus))
        .catch((err) => {
          console.warn('[AIMappingPage] Failed to refresh RAG status after save:', err);
        });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Failed to save. Admin role required to write to the knowledge base.');
    } finally { setSaving(false); }
  }, [result, saving]);

  const approved = result?.mappings.filter((m) => m.status === 'approved').length ?? 0;
  const rejected = result?.mappings.filter((m) => m.status === 'rejected').length ?? 0;
  const pending  = result?.mappings.filter((m) => m.status === 'pending').length  ?? 0;
  const isOllamaReady = ragStatus?.status === 'operational';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', fontFamily: "'Inter',sans-serif", maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div className="ds-animate" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Brain style={{ width: 20, height: 20, color: 'var(--ds-accent-blue)' }} /> AI Schema Mapping
          </h1>
          {/* <p style={{ margin: '0.25rem 0 0', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>
            Submit a hospital table schema → get FHIR field suggestions powered by{' '}
            <span style={{ color: 'var(--ds-accent-purple)', fontWeight: 600 }}>llama3.2:3b</span>
          </p> */}
        </div>
        {knowledgeStats && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', ...card, padding: '0.5rem 1rem', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
              <Database style={{ width: 12, height: 12, color: 'var(--ds-accent-blue)' }} />
              <span><strong style={{ color: 'var(--ds-text-primary)' }}>{knowledgeStats.knowledge_base_entries}</strong> KB entries</span>
            </div>
            <div style={{ width: 1, height: 16, background: 'var(--ds-table-border)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
              <Brain style={{ width: 12, height: 12, color: 'var(--ds-accent-purple)' }} />
              <span><strong style={{ color: 'var(--ds-text-primary)' }}>{knowledgeStats.vector_store_mappings}</strong> vectors</span>
            </div>
            <div style={{ width: 1, height: 16, background: 'var(--ds-table-border)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
              <Info style={{ width: 12, height: 12 }} />
              <span>{knowledgeStats.resources_covered.join(', ')}</span>
            </div>
          </div>
        )}
      </div>

      {/* Ollama status */}
      <div className="ds-animate ds-animate-d1">
        <OllamaStatusBanner status={ragStatus} loading={statusLoading} />
      </div>

      {/* Step 1: Schema input */}
      <div className="ds-animate ds-animate-d1" style={{ ...card, padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>1. Define your hospital table schema</h2>
          {cached && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
              <CheckCircle2 style={{ width: 12, height: 12, color: 'var(--ds-accent-green)' }} /> Restored from last session
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.875rem', marginBottom: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', marginBottom: '0.375rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Table name</label>
            <input value={tableName} onChange={(e) => setTableName(e.target.value)} placeholder="e.g. patients" style={{ ...inputStyle, fontFamily: 'monospace' }}
              onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.18)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; e.target.style.boxShadow = 'none'; }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', marginBottom: '0.375rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Target FHIR resource</label>
            <select value={fhirResource} onChange={(e) => setFhirResource(e.target.value)} style={{ ...inputStyle }}
              onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.18)'; }}
              onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; e.target.style.boxShadow = 'none'; }}>
              {FHIR_RESOURCES.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
        </div>

        {/* Column editor */}
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <label style={{ fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Columns <span style={{ fontWeight: 400 }}>({columns.length})</span>
            </label>
            <button onClick={addColumn} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--ds-accent-blue)', background: 'none', border: 'none', cursor: 'pointer', fontFamily: 'inherit' }}>
              <Plus style={{ width: 12, height: 12 }} /> Add column
            </button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {columns.map((col, i) => (
              <div key={i} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input value={col.name} onChange={(e) => updateColumn(i, 'name', e.target.value)} placeholder="column_name"
                  style={{ ...inputStyle, flex: 1, fontFamily: 'monospace' }}
                  onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.18)'; }}
                  onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; e.target.style.boxShadow = 'none'; }} />
                <select value={col.type} onChange={(e) => updateColumn(i, 'type', e.target.value)}
                  style={{ ...inputStyle, width: 120, flex: 'none' }}
                  onFocus={e => { e.target.style.borderColor = 'var(--ds-accent-purple)'; }}
                  onBlur={e => { e.target.style.borderColor = 'var(--ds-border)'; }}>
                  {COLUMN_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
                <button onClick={() => removeColumn(i)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ds-text-muted)', padding: '0.25rem', display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
                  onMouseOver={e => (e.currentTarget.style.color = '#ef4444')}
                  onMouseOut={e => (e.currentTarget.style.color = 'var(--ds-text-muted)')}>
                  <Trash2 style={{ width: 14, height: 14 }} />
                </button>
              </div>
            ))}
          </div>
        </div>

        <button
          onClick={runSuggestion}
          disabled={loading || !isOllamaReady || !tableName.trim() || columns.filter(c => c.name.trim()).length === 0}
          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.625rem 1rem', background: 'linear-gradient(135deg,var(--ds-accent-blue),var(--ds-accent-purple))', color: '#fff', border: 'none', borderRadius: '0.625rem', fontSize: '0.8125rem', fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', opacity: (loading || !isOllamaReady || !tableName.trim() || columns.filter(c => c.name.trim()).length === 0) ? 0.45 : 1, transition: 'opacity 0.2s' }}
        >
          {loading
            ? <><Loader2 style={{ width: 14, height: 14, animation: 'spin 0.8s linear infinite' }} /> Analysing with llama3.2:3b — this may take 15–30 s…</>
            : <><Zap style={{ width: 14, height: 14 }} /> Get AI Mapping Suggestions</>
          }
        </button>
        {!isOllamaReady && !statusLoading && (
          <p style={{ textAlign: 'center', fontSize: '0.6875rem', color: 'var(--ds-status-pending-text)', marginTop: '0.5rem' }}>
            Button disabled — Ollama must be running first
          </p>
        )}
      </div>

      {/* Error banner */}
      {error && <ErrorBanner message="Failed to generate mapping suggestions" detail={error} onRetry={runSuggestion} />}

      {/* Save confirmation */}
      {savedCount !== null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--ds-status-active-bg)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '0.75rem', padding: '0.875rem 1rem', fontSize: '0.8125rem', color: 'var(--ds-status-active-text)' }}>
          <CheckCircle2 style={{ width: 14, height: 14, flexShrink: 0 }} />
          Saved <strong>{savedCount}</strong> mapping{savedCount !== 1 ? 's' : ''} to ChromaDB. Approved selections have been reset.
        </div>
      )}

      {/* Step 2: Review results */}
      {result && (
        <div className="ds-animate" style={{ ...card, overflow: 'hidden' }}>
          {/* Result header */}
          <div style={{ padding: '1rem 1.25rem', background: 'var(--ds-table-head-bg)', borderBottom: '1px solid var(--ds-table-border)' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>
                  2. Review suggestions — <span style={{ fontFamily: 'monospace', color: 'var(--ds-accent-blue)' }}>{result.table_name}</span>{' → '}<span style={{ color: 'var(--ds-text-secondary)' }}>{result.fhir_resource}</span>
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>
                    <span>{result.statistics.total} fields</span>
                    <span style={{ color: 'var(--ds-accent-green)', fontWeight: 600 }}>· {result.statistics.high} high</span>
                    <span style={{ color: 'var(--ds-accent-orange)', fontWeight: 600 }}>· {result.statistics.medium} medium</span>
                    <span style={{ color: 'var(--ds-status-error-text)', fontWeight: 600 }}>· {result.statistics.low} low</span>
                  </div>
                  <AccuracyBar pct={result.accuracy_pct} />
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexShrink: 0, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', gap: '0.375rem' }}>
                  <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-active-bg)', color: 'var(--ds-status-active-text)', border: '1px solid rgba(16,185,129,0.25)' }}>{approved} approved</span>
                  <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-pending-bg)', color: 'var(--ds-status-pending-text)', border: '1px solid rgba(245,158,11,0.25)' }}>{pending} pending</span>
                  <span style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'var(--ds-status-error-bg)', color: 'var(--ds-status-error-text)', border: '1px solid rgba(239,68,68,0.25)' }}>{rejected} rejected</span>
                </div>
                <button onClick={approveAll} style={{ fontSize: '0.75rem', color: 'var(--ds-accent-green)', background: 'var(--ds-status-active-bg)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: '0.5rem', padding: '0.3rem 0.75rem', cursor: 'pointer', fontFamily: 'inherit' }}>Approve all</button>
                <button onClick={saveMappings} disabled={saving || approved === 0}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', background: 'linear-gradient(135deg,var(--ds-accent-blue),var(--ds-accent-purple))', color: '#fff', border: 'none', borderRadius: '0.5rem', padding: '0.3rem 0.75rem', cursor: 'pointer', fontFamily: 'inherit', opacity: (saving || approved === 0) ? 0.45 : 1, transition: 'opacity 0.2s' }}>
                  {saving ? <><Loader2 style={{ width: 11, height: 11, animation: 'spin 0.8s linear infinite' }} /> Saving…</> : <><Check style={{ width: 11, height: 11 }} /> Save {approved > 0 ? approved : ''} approved</>}
                </button>
              </div>
            </div>
          </div>

          {/* Mapping rows */}
          <div>
            {result.mappings.map((m) => {
              const rowBg =
                m.status === 'approved' ? 'var(--ds-status-active-bg)' :
                m.status === 'rejected' ? 'var(--ds-status-error-bg)'  : 'transparent';
              return (
                <div key={m.source_field} style={{ background: rowBg, borderBottom: '1px solid var(--ds-table-border)', transition: 'background 0.2s' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', padding: '0.75rem 1.25rem' }}>
                    <div style={{ width: 160, flexShrink: 0 }}>
                      <p style={{ margin: 0, fontSize: '0.8125rem', fontFamily: 'monospace', fontWeight: 700, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.source_field}</p>
                      <p style={{ margin: 0, fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{m.source_type}</p>
                    </div>
                    <span style={{ color: 'var(--ds-table-border)', fontSize: '0.875rem', flexShrink: 0 }}>→</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <p style={{ margin: 0, fontSize: '0.8125rem', fontFamily: 'monospace', color: 'var(--ds-accent-blue)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.target_path}</p>
                      <p style={{ margin: 0, fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>{m.fhir_resource} · {m.transformation}</p>
                    </div>
                    <MethodBadge method={m.method} />
                    <ConfidenceBadge value={m.confidence} />
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', flexShrink: 0 }}>
                      <button onClick={() => toggleStatus(m.source_field, 'approved')} title="Approve"
                        style={{ width: 30, height: 30, borderRadius: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', border: m.status === 'approved' ? 'none' : '1px solid var(--ds-table-border)', background: m.status === 'approved' ? 'var(--ds-accent-green)' : 'transparent', color: m.status === 'approved' ? '#fff' : 'var(--ds-text-muted)', transition: 'all 0.2s' }}>
                        <Check style={{ width: 13, height: 13 }} />
                      </button>
                      <button onClick={() => toggleStatus(m.source_field, 'rejected')} title="Reject"
                        style={{ width: 30, height: 30, borderRadius: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', border: m.status === 'rejected' ? 'none' : '1px solid var(--ds-table-border)', background: m.status === 'rejected' ? '#ef4444' : 'transparent', color: m.status === 'rejected' ? '#fff' : 'var(--ds-text-muted)', transition: 'all 0.2s' }}>
                        <X style={{ width: 13, height: 13 }} />
                      </button>
                      {(m.similar_mappings?.length || m.reasoning) && (
                        <button onClick={() => setExpandedRow(expandedRow === m.source_field ? null : m.source_field)}
                          style={{ width: 30, height: 30, borderRadius: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', border: '1px solid var(--ds-table-border)', background: 'transparent', color: 'var(--ds-text-muted)', transition: 'all 0.2s' }}>
                          {expandedRow === m.source_field ? <ChevronUp style={{ width: 13, height: 13 }} /> : <ChevronDown style={{ width: 13, height: 13 }} />}
                        </button>
                      )}
                    </div>
                  </div>

                  {expandedRow === m.source_field && (
                    <div style={{ padding: '0.5rem 1.25rem 1rem', marginLeft: 172, display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
                      <div style={{ background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.5rem', padding: '0.625rem 0.875rem' }}>
                        <p style={{ margin: '0 0 0.25rem', fontSize: '0.6875rem', fontWeight: 600, color: 'var(--ds-text-muted)' }}>
                          {m.method === 'retrieval' ? '⚡ Vector store match reasoning' : '🤖 llama3.2:3b reasoning'}
                        </p>
                        <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-secondary)', lineHeight: 1.5 }}>
                          {m.reasoning ?? 'No explanation available for this mapping.'}
                        </p>
                      </div>
                      {m.similar_mappings && m.similar_mappings.length > 0 && (
                        <div>
                          <p style={{ margin: '0 0 0.375rem', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>Top similar mappings from ChromaDB:</p>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                            {m.similar_mappings.slice(0, 3).map((s, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '0.75rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.375rem', padding: '0.25rem 0.75rem' }}>
                                <span style={{ fontFamily: 'monospace', color: 'var(--ds-text-muted)', width: 120, flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.source_field}</span>
                                <span style={{ color: 'var(--ds-table-border)' }}>→</span>
                                <span style={{ fontFamily: 'monospace', color: 'var(--ds-accent-blue)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.target_path}</span>
                                <span style={{ color: 'var(--ds-text-muted)', flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{Math.round(s.similarity * 100)}% similar</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default AIMappingPage;
