/**
 * ResearchPage — Dark glassmorphism, full ds-* design system.
 * Final Year Research Project documentation page.
 */
import React from 'react';
import {
  BookOpen, Zap, Shield, Brain, Database, ArrowRight,
  CheckCircle2, ChartColumn, CodeXml, TestTube, Cpu, Network, Globe,
} from 'lucide-react';

// ── Data ───────────────────────────────────────────────────────────────────────
interface TechRow   { layer: string; tech: string; bg: string; color: string; border: string; }
interface ArchNode  { label: string; sub: string; bg: string; color: string; border: string; icon: React.ReactNode; }
interface FutureCard { icon: React.ReactNode; title: string; desc: string; }

const TECH_STACK: TechRow[] = [
  { layer: 'Frontend',       tech: 'React 19 + TypeScript + Tailwind CSS + Recharts',        bg: 'rgba(59,130,246,0.10)',  color: 'var(--ds-accent-blue)',   border: 'rgba(59,130,246,0.25)'  },
  { layer: 'API',            tech: 'FastAPI + Pydantic + JWT authentication',                bg: 'rgba(99,102,241,0.10)',  color: '#818cf8',                 border: 'rgba(99,102,241,0.25)'  },
  { layer: 'ETL',            tech: 'Custom Python pipeline + autosync daemon',               bg: 'rgba(139,92,246,0.10)', color: 'var(--ds-accent-purple)', border: 'rgba(139,92,246,0.25)' },
  { layer: 'CDC',            tech: 'Custom adapters — PostgreSQL, MySQL, MSSQL, MongoDB',    bg: 'rgba(167,139,250,0.10)', color: '#c4b5fd',                 border: 'rgba(167,139,250,0.25)' },
  { layer: 'AI / RAG',       tech: 'ChromaDB + Ollama (LLaMA 3.2) + Google Gemini',         bg: 'rgba(16,185,129,0.10)', color: 'var(--ds-accent-green)',  border: 'rgba(16,185,129,0.25)' },
  { layer: 'Database',       tech: 'PostgreSQL 15 + FHIR R4 schema + Row-Level Security',   bg: 'rgba(20,184,166,0.10)', color: '#2dd4bf',                 border: 'rgba(20,184,166,0.25)' },
  { layer: 'Security',       tech: 'AES-256 + TLS 1.3 + MFA + RBAC + audit logging',        bg: 'rgba(245,158,11,0.10)', color: 'var(--ds-accent-orange)', border: 'rgba(245,158,11,0.25)' },
  { layer: 'Infrastructure', tech: 'Docker + docker-compose + Prometheus + Grafana',         bg: 'rgba(255,255,255,0.04)', color: 'var(--ds-text-muted)',   border: 'var(--ds-table-border)' },
];

const RESULTS = [
  { metric: 'Schema mapping accuracy', value: '>99%',          target: '99%'            },
  { metric: 'Sync performance',        value: '>10,000 rec/min', target: '10,000 rec/min' },
  { metric: 'RAG query accuracy',      value: '>85%',           target: '85%'            },
  { metric: 'System uptime',           value: '99.8%',          target: '99.5%'          },
  { metric: 'Encryption coverage',     value: '100%',           target: '100%'           },
  { metric: 'Onboarding time',         value: '<2 weeks',       target: '<2 weeks'       },
  { metric: 'Multi-tenant isolation',  value: '100%',           target: '100%'           },
  { metric: 'FHIR compliance',         value: 'R4 full',        target: 'R4'             },
];

const COMPARISON = [
  { feature: 'Schema mapping',     traditional: 'Manual XSLT / custom scripts',  carelock: 'AI-assisted (LLaMA + RAG)',         highlight: true  },
  { feature: 'Integration effort', traditional: 'Months per hospital',            carelock: '<2 weeks per hospital',             highlight: true  },
  { feature: 'Security isolation', traditional: 'Application-level (bypassable)', carelock: 'DB-level RLS (unbypassable)',       highlight: true  },
  { feature: 'Schema changes',     traditional: 'Required at source hospital',    carelock: 'None — non-invasive',              highlight: true  },
  { feature: 'Data standard',      traditional: 'Proprietary / HL7 v2',           carelock: 'FHIR R4 (international)',           highlight: false },
  { feature: 'Analytics',          traditional: 'Manual SQL / BI tools',          carelock: 'Natural language RAG queries',      highlight: false },
  { feature: 'DB support',         traditional: 'One specific vendor',            carelock: 'PostgreSQL, MySQL, MSSQL, MongoDB', highlight: false },
  { feature: 'Audit trail',        traditional: 'Application logs only',          carelock: 'HIPAA-compliant audit DB',         highlight: false },
];

const ARCH_NODES: ArchNode[] = [
  { label: 'Hospital DB',     sub: 'Any schema',       bg: 'rgba(139,92,246,0.15)', color: 'var(--ds-accent-purple)', border: 'rgba(139,92,246,0.35)', icon: <Database style={{ width: 12, height: 12 }} /> },
  { label: 'CDC Adapter',     sub: 'Change capture',   bg: 'rgba(59,130,246,0.15)', color: 'var(--ds-accent-blue)',   border: 'rgba(59,130,246,0.35)', icon: <Zap     style={{ width: 12, height: 12 }} /> },
  { label: 'AI Mapper',       sub: 'LLaMA + ChromaDB', bg: 'rgba(99,102,241,0.15)', color: '#818cf8',                 border: 'rgba(99,102,241,0.35)', icon: <Brain   style={{ width: 12, height: 12 }} /> },
  { label: 'ETL Pipeline',    sub: 'Transform + load', bg: 'rgba(167,139,250,0.15)', color: '#c4b5fd',               border: 'rgba(167,139,250,0.35)', icon: <Cpu    style={{ width: 12, height: 12 }} /> },
  { label: 'FHIR Central DB', sub: 'FHIR R4 + RLS',   bg: 'rgba(20,184,166,0.15)', color: '#2dd4bf',                 border: 'rgba(20,184,166,0.35)', icon: <Shield  style={{ width: 12, height: 12 }} /> },
  { label: 'RAG Chatbot',     sub: 'AI queries',       bg: 'rgba(16,185,129,0.15)', color: 'var(--ds-accent-green)', border: 'rgba(16,185,129,0.35)', icon: <Network style={{ width: 12, height: 12 }} /> },
];

const FUTURE_WORK: FutureCard[] = [
  { icon: <Brain   style={{ width: 14, height: 14, color: 'var(--ds-accent-purple)' }} />, title: 'Federated learning',           desc: 'Train shared diagnostic models across hospital data without centralising raw records.'                        },
  { icon: <Zap     style={{ width: 14, height: 14, color: 'var(--ds-accent-blue)'   }} />, title: 'Real-time streaming analytics', desc: 'Stream FHIR events to a live dashboard for ICU occupancy and outbreak early warning.'                       },
  { icon: <Globe   style={{ width: 14, height: 14, color: '#2dd4bf'                 }} />, title: 'HL7 v2 integration',            desc: 'Support legacy HL7 v2 message feeds alongside SQL-based CDC for older hospital systems.'                  },
  { icon: <Shield  style={{ width: 14, height: 14, color: 'var(--ds-accent-green)'  }} />, title: 'PDPA compliance module',        desc: 'Extend audit logging with Pakistan Personal Data Protection Act compliance reporting.'                      },
  { icon: <TestTube style={{ width: 14, height: 14, color: 'var(--ds-accent-orange)'}} />, title: 'Clinical NLP pipeline',         desc: 'Extract structured FHIR resources from unstructured clinical notes using medical NLP models.'                },
  { icon: <Network style={{ width: 14, height: 14, color: '#818cf8'                 }} />, title: 'Multi-region deployment',       desc: 'Deploy FHIR partitions across regions for disaster recovery and data sovereignty compliance.'               },
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

// ── Main ───────────────────────────────────────────────────────────────────────
const ResearchPage: React.FC = () => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', fontFamily: "'Inter',sans-serif", maxWidth: 900, margin: '0 auto' }}>

    {/* Header */}
    <div className="ds-animate">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--ds-accent-blue)', fontWeight: 700, marginBottom: '0.5rem' }}>
        <BookOpen style={{ width: 14, height: 14 }} /> Final Year Project · Bahria University Lahore Campus
      </div>
      <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--ds-text-primary)', letterSpacing: '-0.03em', lineHeight: 1.1 }}>CareLock Sync</h1>
      <p style={{ margin: '0.375rem 0 0', fontSize: '1rem', color: 'var(--ds-text-muted)', fontWeight: 400 }}>Secure, AI-Assisted, Multi-Tenant Hospital Database Synchronisation using FHIR R4</p>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.625rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)', flexWrap: 'wrap' }}>
        <span>Waleed Khalid</span><span style={{ opacity: 0.3 }}>·</span>
        <span>Muhammad Mohsin</span><span style={{ opacity: 0.3 }}>·</span>
        <span>Shahmeer Nadeem</span><span style={{ opacity: 0.3 }}>·</span>
        <span style={{ color: 'var(--ds-accent-blue)', fontWeight: 700 }}>Supervisor: Dr. Muhammad Saqib Sohail</span>
      </div>
    </div>

    {/* Problem + Solution */}
    <div className="ds-animate ds-animate-d1" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
      <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '1rem', padding: '1.125rem' }}>
        <h2 style={{ margin: '0 0 0.625rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ width: 18, height: 18, borderRadius: '50%', background: '#ef4444', color: '#fff', fontSize: '0.6875rem', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>!</span>
          Problem statement
        </h2>
        <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-secondary)', lineHeight: 1.6 }}>
          Pakistani hospitals operate on siloed, heterogeneous databases — each with different schemas, naming conventions, and vendors. Patient data cannot be shared across institutions, making cross-hospital analytics and AI-driven insights impossible. Existing integration tools require full schema migration (costly, disruptive) or lack the database-level isolation required for HIPAA/PDPA compliance.
        </p>
      </div>
      <div style={{ background: 'rgba(59,130,246,0.08)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: '1rem', padding: '1.125rem' }}>
        <h2 style={{ margin: '0 0 0.625rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Zap style={{ width: 14, height: 14, color: 'var(--ds-accent-blue)' }} /> Our solution
        </h2>
        <p style={{ margin: '0 0 0.625rem', fontSize: '0.75rem', color: 'var(--ds-text-secondary)', lineHeight: 1.6 }}>
          A non-invasive middleware that connects to any hospital DB, uses AI to translate data into FHIR R4, and syncs it to a shared repository — while enforcing PostgreSQL Row-Level Security so no hospital can ever access another's data.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.375rem' }}>
          {['Non-invasive', 'FHIR R4', 'AI mapping', 'RLS isolation', 'CDC + ETL', 'RAG queries'].map(f => (
            <span key={f} style={{ fontSize: '0.6875rem', fontWeight: 700, padding: '0.2rem 0.5rem', borderRadius: '2rem', background: 'rgba(59,130,246,0.12)', color: 'var(--ds-accent-blue)', border: '1px solid rgba(59,130,246,0.25)' }}>{f}</span>
          ))}
        </div>
      </div>
    </div>

    {/* System Architecture */}
    <div className="ds-animate ds-animate-d2">
      <h2 style={{ margin: '0 0 0.875rem', fontSize: '1rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Database style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} /> System architecture
      </h2>
      <div style={{ ...card, padding: '1.25rem' }}>
        {/* Hospital inputs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.875rem', flexWrap: 'wrap' }}>
          {['Hospital A (PostgreSQL)', 'Hospital B (MSSQL)', 'Hospital C (Legacy)'].map((h, i) => (
            <React.Fragment key={h}>
              <div style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.3)', borderRadius: '0.625rem', padding: '0.375rem 0.75rem', fontSize: '0.75rem', fontWeight: 600, color: 'var(--ds-accent-purple)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, background: i === 0 ? 'var(--ds-accent-blue)' : i === 1 ? 'var(--ds-accent-purple)' : 'var(--ds-accent-orange)' }} />
                {h}
              </div>
              {i < 2 && <span style={{ color: 'var(--ds-text-muted)', fontWeight: 700 }}>+</span>}
            </React.Fragment>
          ))}
          <ArrowRight style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} />
        </div>

        {/* Pipeline flow */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          {ARCH_NODES.map((node, i, arr) => (
            <React.Fragment key={node.label}>
              <div style={{ background: node.bg, border: `1.5px solid ${node.border}`, borderRadius: '0.75rem', padding: '0.5rem 0.875rem', textAlign: 'center', flexShrink: 0, color: node.color }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.375rem', marginBottom: '0.125rem' }}>
                  {node.icon}
                  <span style={{ fontSize: '0.75rem', fontWeight: 700 }}>{node.label}</span>
                </div>
                <div style={{ fontSize: '0.6875rem', opacity: 0.7 }}>{node.sub}</div>
              </div>
              {i < arr.length - 1 && <ArrowRight style={{ width: 12, height: 12, color: 'var(--ds-text-muted)', flexShrink: 0 }} />}
            </React.Fragment>
          ))}
        </div>
        <p style={{ margin: '0.875rem 0 0', fontSize: '0.6875rem', color: 'var(--ds-text-muted)', lineHeight: 1.5 }}>
          Each stage is containerised via Docker — hospitals onboard incrementally without system downtime. All data flow is encrypted (TLS 1.3 in transit, AES-256 at rest).
        </p>
      </div>
    </div>

    {/* AI Innovation */}
    <div className="ds-animate ds-animate-d3">
      <h2 style={{ margin: '0 0 0.875rem', fontSize: '1rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Brain style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} /> AI innovation — dual-model RAG
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        {/* Ollama */}
        <div style={{ ...card, padding: '1.125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '0.625rem' }}>
            <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Brain style={{ width: 14, height: 14, color: '#818cf8' }} />
            </div>
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Ollama / LLaMA 3.2 — local</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>Schema mapping · offline · privacy-preserving</div>
            </div>
          </div>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-secondary)', lineHeight: 1.55 }}>Runs on-premises — zero patient data leaves the hospital network. Used for FHIR field mapping with ChromaDB vector similarity search over 800+ historical mappings.</p>
        </div>
        {/* Gemini */}
        <div style={{ ...card, padding: '1.125rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem', marginBottom: '0.625rem' }}>
            <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Zap style={{ width: 14, height: 14, color: 'var(--ds-accent-green)' }} />
            </div>
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Google Gemini — cloud</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>Complex reasoning · population health queries</div>
            </div>
          </div>
          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--ds-text-secondary)', lineHeight: 1.55 }}>Used for executive-level analytics requiring deep reasoning. Only anonymised aggregate data is sent — no PII. Falls back to LLaMA automatically if offline.</p>
        </div>
      </div>

      {/* RAG pipeline */}
      <div style={{ ...card, padding: '1rem 1.25rem' }}>
        <h3 style={{ margin: '0 0 0.625rem', fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>RAG query pipeline</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', flexWrap: 'wrap' }}>
          {['Natural language input', 'Embedding generation', 'ChromaDB similarity search (top-5)', 'FHIR context retrieved', 'LLM grounded answer', 'Source citations'].map((s, i, arr) => (
            <React.Fragment key={s}>
              <span style={{ fontSize: '0.6875rem', fontWeight: 600, padding: '0.3rem 0.625rem', borderRadius: '0.5rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-card-border)', color: 'var(--ds-text-secondary)' }}>{s}</span>
              {i < arr.length - 1 && <ArrowRight style={{ width: 10, height: 10, color: 'var(--ds-text-muted)' }} />}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>

    {/* Comparison table */}
    <div>
      <h2 style={{ margin: '0 0 0.875rem', fontSize: '1rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <ChartColumn style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} /> CareLock vs traditional integration
      </h2>
      <div style={{ ...card, overflow: 'hidden' }}>
        <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 2fr', gap: '0.5rem', padding: '0.625rem 1.25rem' }}>
          <span>Feature</span><span>Traditional approach</span><span style={{ color: 'var(--ds-accent-blue)' }}>CareLock Sync</span>
        </div>
        {COMPARISON.map(row => (
          <div key={row.feature} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 2fr', gap: '0.5rem', alignItems: 'center', padding: '0.625rem 1.25rem', background: row.highlight ? 'rgba(59,130,246,0.04)' : 'transparent' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-secondary)' }}>{row.feature}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{row.traditional}</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              {row.highlight && <CheckCircle2 style={{ width: 12, height: 12, color: 'var(--ds-accent-green)', flexShrink: 0 }} />}
              <span style={{ fontSize: '0.75rem', fontWeight: row.highlight ? 700 : 400, color: row.highlight ? 'var(--ds-accent-blue)' : 'var(--ds-text-secondary)' }}>{row.carelock}</span>
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* Tech stack */}
    <div>
      <h2 style={{ margin: '0 0 0.875rem', fontSize: '1rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <CodeXml style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} /> Technology stack
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.625rem' }}>
        {TECH_STACK.map(t => (
          <div key={t.layer} style={{ background: t.bg, border: `1px solid ${t.border}`, borderRadius: '0.75rem', padding: '0.625rem 0.875rem' }}>
            <div style={{ fontSize: '0.6875rem', fontWeight: 700, color: t.color, marginBottom: '0.125rem' }}>{t.layer}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{t.tech}</div>
          </div>
        ))}
      </div>
    </div>

    {/* Results table */}
    <div>
      <h2 style={{ margin: '0 0 0.875rem', fontSize: '1rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <ChartColumn style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} /> Performance results — all targets met
      </h2>
      <div style={{ ...card, overflow: 'hidden' }}>
        <div className="ds-table-head" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 40px', gap: '0.5rem', padding: '0.625rem 1.25rem' }}>
          <span>Metric</span><span>Target</span><span style={{ color: 'var(--ds-accent-green)' }}>Achieved</span><span />
        </div>
        {RESULTS.map(r => (
          <div key={r.metric} className="ds-table-row" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 40px', gap: '0.5rem', alignItems: 'center', padding: '0.625rem 1.25rem' }}>
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-primary)' }}>{r.metric}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)' }}>{r.target}</span>
            <span style={{ fontSize: '0.875rem', fontWeight: 800, color: 'var(--ds-accent-green)' }}>{r.value}</span>
            <CheckCircle2 style={{ width: 14, height: 14, color: 'var(--ds-accent-green)' }} />
          </div>
        ))}
      </div>
    </div>

    {/* Future work */}
    <div>
      <h2 style={{ margin: '0 0 0.875rem', fontSize: '1rem', fontWeight: 700, color: 'var(--ds-text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <TestTube style={{ width: 14, height: 14, color: 'var(--ds-text-muted)' }} /> Future work &amp; research directions
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
        {FUTURE_WORK.map(f => (
          <div key={f.title} style={{ ...card, padding: '0.875rem 1rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <div style={{ width: 32, height: 32, borderRadius: '0.5rem', background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>{f.icon}</div>
            <div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)', marginBottom: '0.25rem' }}>{f.title}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--ds-text-muted)', lineHeight: 1.5 }}>{f.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>

    {/* Research team */}
    <div style={{ ...card, padding: '1.25rem' }}>
      <h2 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>Research team</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '0.75rem' }}>
        {[
          { name: 'Waleed Khalid',   role: 'Security · CDC · Frontend', initials: 'WK' },
          { name: 'Muhammad Mohsin', role: 'ETL · Database · Infra',     initials: 'MM' },
          { name: 'Shahmeer Nadeem', role: 'AI / RAG · Schema Mapping',  initials: 'SN' },
        ].map((m, i) => {
          const gradients = [
            'linear-gradient(135deg,#3b82f6,#6366f1)',
            'linear-gradient(135deg,#8b5cf6,#6366f1)',
            'linear-gradient(135deg,#10b981,#3b82f6)',
          ];
          return (
            <div key={m.name} style={{ background: 'var(--ds-surface)', border: '1px solid var(--ds-table-border)', borderRadius: '0.75rem', padding: '1rem', textAlign: 'center' }}>
              <div style={{ width: 44, height: 44, borderRadius: '50%', background: gradients[i], display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: '0.875rem', margin: '0 auto 0.625rem' }}>{m.initials}</div>
              <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--ds-text-primary)' }}>{m.name}</div>
              <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: '0.125rem' }}>{m.role}</div>
            </div>
          );
        })}
      </div>
      <p style={{ margin: '0.875rem 0 0', textAlign: 'center', fontSize: '0.6875rem', color: 'var(--ds-text-muted)' }}>
        Supervised by Dr. Muhammad Saqib Sohail · Bahria University Lahore Campus · 2025–2026
      </p>
    </div>
  </div>
);

export default ResearchPage;
