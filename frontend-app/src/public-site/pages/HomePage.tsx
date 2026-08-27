/**
 * public-site/pages/HomePage.tsx
 * Dark glassmorphism public marketing page — matches the dashboard design system.
 * All colours come from inline styles using the same dark/glass palette as login page.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, Brain, Database, Activity, ArrowRight,
  ChevronDown, Globe, Lock, Zap, Menu, X,
  Layers, CheckCircle2,
} from 'lucide-react';
import { PUBLIC_ROUTES, NAV_BUTTONS } from '../../shared/constants/routes';

// ── Shared style helpers ────────────────────────────────────────────────────
const glassCard: React.CSSProperties = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.09)',
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
  borderRadius: '1.25rem',
  boxShadow: '0 8px 32px rgba(0,0,0,0.40), inset 0 1px 0 rgba(255,255,255,0.06)',
};

const sectionHeadStyle: React.CSSProperties = {
  textAlign: 'center',
  marginBottom: '3.5rem',
};

const sectionTitle: React.CSSProperties = {
  fontSize: 'clamp(1.75rem,4vw,2.5rem)',
  fontWeight: 800,
  color: 'rgba(255,255,255,0.93)',
  margin: 0,
  letterSpacing: '-0.03em',
  lineHeight: 1.15,
};

const sectionSub: React.CSSProperties = {
  fontSize: '1.0625rem',
  color: 'rgba(255,255,255,0.45)',
  marginTop: '0.75rem',
  lineHeight: 1.6,
};

// ── Navbar ──────────────────────────────────────────────────────────────────
const Navbar: React.FC = () => {
  const [scrolled, setScrolled]   = useState(false);
  const [menuOpen, setMenuOpen]   = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 24);
    window.addEventListener('scroll', h);
    return () => window.removeEventListener('scroll', h);
  }, []);

  const navStyle: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 50,
    transition: 'background 0.35s, box-shadow 0.35s, border-color 0.35s',
    background: scrolled ? 'rgba(8,12,24,0.88)' : 'transparent',
    backdropFilter: scrolled ? 'blur(20px)' : 'none',
    WebkitBackdropFilter: scrolled ? 'blur(20px)' : 'none',
    borderBottom: scrolled ? '1px solid rgba(255,255,255,0.06)' : '1px solid transparent',
    boxShadow: scrolled ? '0 4px 24px rgba(0,0,0,0.40)' : 'none',
  };

  const linkStyle: React.CSSProperties = {
    fontSize: '0.875rem',
    fontWeight: 500,
    color: 'rgba(255,255,255,0.60)',
    textDecoration: 'none',
    transition: 'color 0.2s',
    cursor: 'pointer',
  };

  return (
    <nav style={navStyle}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 1.5rem', height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div style={{ width: 36, height: 36, borderRadius: '0.75rem', background: 'linear-gradient(135deg,#7c3aed,#6366f1,#3b82f6)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 16px rgba(139,92,246,0.45)', flexShrink: 0 }}>
            <Shield style={{ width: 18, height: 18, color: '#fff' }} />
          </div>
          <span style={{ fontSize: '1.0625rem', fontWeight: 800, color: 'rgba(255,255,255,0.93)', letterSpacing: '-0.01em' }}>CareLock Sync</span>
        </div>

        {/* Desktop links */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }} className="hidden-mobile">
          {[['Features','#features'],['How It Works','#how-it-works'],['Architecture','#architecture'],['About','#about']].map(([label, href]) => (
            <a key={label} href={href} style={linkStyle}
              onMouseEnter={e => ((e.target as HTMLElement).style.color = 'rgba(255,255,255,0.93)')}
              onMouseLeave={e => ((e.target as HTMLElement).style.color = 'rgba(255,255,255,0.60)')}>
              {label}
            </a>
          ))}
        </div>

        {/* Desktop CTA */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }} className="hidden-mobile">
          <button type="button" onClick={() => { console.log('[NAV] Navigating to:', PUBLIC_ROUTES.LOGIN); navigate(PUBLIC_ROUTES.LOGIN); }} style={{ fontSize: '0.875rem', fontWeight: 600, color: 'rgba(255,255,255,0.60)', background: 'none', border: 'none', cursor: 'pointer', padding: '0.5rem 0.75rem', borderRadius: '0.625rem', transition: 'color 0.2s' }}
            onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.93)')}
            onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.60)')}>
            Sign In
          </button>
          <button type="button" onClick={() => { console.log('[NAV] Navigating to:', NAV_BUTTONS.DEMO_START); navigate(NAV_BUTTONS.DEMO_START); }} style={{ fontSize: '0.875rem', fontWeight: 700, background: 'linear-gradient(135deg,#7c3aed,#6366f1)', color: '#fff', border: 'none', padding: '0.5625rem 1.25rem', borderRadius: '0.75rem', cursor: 'pointer', boxShadow: '0 4px 16px rgba(124,58,237,0.40)', transition: 'transform 0.2s, box-shadow 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.transform = 'translateY(-1px)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 6px 24px rgba(124,58,237,0.55)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 16px rgba(124,58,237,0.40)'; }}>
            Get Started
          </button>
        </div>

        {/* Mobile hamburger */}
        <button onClick={() => setMenuOpen(!menuOpen)} style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', borderRadius: '0.625rem', width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: 'rgba(255,255,255,0.70)' }} className="show-mobile">
          {menuOpen ? <X style={{ width: 16, height: 16 }} /> : <Menu style={{ width: 16, height: 16 }} />}
        </button>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div style={{ background: 'rgba(8,12,24,0.95)', backdropFilter: 'blur(24px)', borderTop: '1px solid rgba(255,255,255,0.06)', padding: '1rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {[['Features','#features'],['How It Works','#how-it-works'],['Architecture','#architecture'],['About','#about']].map(([label, href]) => (
            <a key={label} href={href} style={{ fontSize: '0.9375rem', fontWeight: 500, color: 'rgba(255,255,255,0.70)', textDecoration: 'none' }} onClick={() => setMenuOpen(false)}>{label}</a>
          ))}
          <button type="button" onClick={() => { console.log('[NAV_MOBILE] Navigating to:', NAV_BUTTONS.DEMO_START); navigate(NAV_BUTTONS.DEMO_START); setMenuOpen(false); }} style={{ marginTop: '0.5rem', background: 'linear-gradient(135deg,#7c3aed,#6366f1)', color: '#fff', border: 'none', padding: '0.75rem', borderRadius: '0.75rem', fontWeight: 700, fontSize: '0.9375rem', cursor: 'pointer' }}>
            Get Started
          </button>
        </div>
      )}

      <style>{`
        @media(max-width:768px){.hidden-mobile{display:none!important}.show-mobile{display:flex!important}}
        @media(min-width:769px){.show-mobile{display:none!important}.hidden-mobile{display:flex!important}}
      `}</style>
    </nav>
  );
};

// ── Hero ────────────────────────────────────────────────────────────────────
const Hero: React.FC = () => {
  const navigate = useNavigate();

  return (
    <section style={{ paddingTop: '9rem', paddingBottom: '6rem', paddingLeft: '1.5rem', paddingRight: '1.5rem', position: 'relative', overflow: 'hidden' }}>
      {/* Animated radial orbs */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: '-10%', left: '-5%', width: '55%', height: '65%', background: 'radial-gradient(circle, rgba(99,66,236,0.22) 0%, transparent 70%)', filter: 'blur(40px)' }} />
        <div style={{ position: 'absolute', bottom: '-15%', right: '-10%', width: '50%', height: '60%', background: 'radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%)', filter: 'blur(40px)' }} />
        <div style={{ position: 'absolute', top: '30%', right: '20%', width: '30%', height: '40%', background: 'radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%)', filter: 'blur(30px)' }} />
      </div>

      {/* Fine grid overlay */}
      <div style={{ position: 'absolute', inset: 0, backgroundImage: 'linear-gradient(rgba(255,255,255,0.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.025) 1px,transparent 1px)', backgroundSize: '55px 55px', pointerEvents: 'none' }} />

      <div style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center', position: 'relative', zIndex: 1 }}>

        {/* Badge */}
        {/* <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.28)', color: '#c084fc', fontSize: '0.75rem', fontWeight: 700, padding: '0.375rem 1rem', borderRadius: '2rem', marginBottom: '1.75rem', letterSpacing: '0.03em' }}>
          <Zap style={{ width: 13, height: 13 }} />
          AI-POWERED HEALTHCARE DATA PLATFORM
        </div> */}

        {/* Headline */}
        <h1 style={{ fontSize: 'clamp(2.5rem,7vw,4.25rem)', fontWeight: 900, color: 'rgba(255,255,255,0.95)', margin: '0 0 1.25rem', letterSpacing: '-0.04em', lineHeight: 1.1 }}>
          Secure, Intelligent<br />
          <span style={{ background: 'linear-gradient(135deg,#a78bfa,#818cf8,#60a5fa)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
            Hospital Data Sync
          </span>
        </h1>

        <p style={{ fontSize: '1.125rem', color: 'rgba(255,255,255,0.50)', lineHeight: 1.7, marginBottom: '2.5rem', maxWidth: 640, margin: '0 auto 2.5rem' }}>
          Connect any hospital database to a unified FHIR R4 standard with AI-assisted schema
          mapping, real-time CDC, and bank-grade multi-tenant isolation.
        </p>

        {/* CTAs */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: '1rem', marginBottom: '4rem' }}>
          <button type="button" onClick={() => { console.log('[HERO] Start Demo clicked, navigating to:', NAV_BUTTONS.DEMO_START); navigate(NAV_BUTTONS.DEMO_START); }} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'linear-gradient(135deg,#7c3aed,#6366f1,#3b82f6)', color: '#fff', border: 'none', padding: '0.875rem 1.875rem', borderRadius: '0.875rem', fontSize: '0.9375rem', fontWeight: 700, cursor: 'pointer', boxShadow: '0 4px 24px rgba(124,58,237,0.45)', transition: 'transform 0.2s, box-shadow 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 8px 32px rgba(124,58,237,0.60)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 24px rgba(124,58,237,0.45)'; }}>
            Start Demo <ArrowRight style={{ width: 16, height: 16 }} />
          </button>
          <a href="#how-it-works" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9375rem', fontWeight: 600, color: 'rgba(255,255,255,0.55)', textDecoration: 'none', padding: '0.875rem 1.25rem', borderRadius: '0.875rem', border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.04)', transition: 'color 0.2s, background 0.2s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.85)'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.08)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.55)'; (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)'; }}>
            How it works <ChevronDown style={{ width: 15, height: 15 }} />
          </a>
        </div>

        {/* Stats grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: '1rem', maxWidth: 760, margin: '0 auto' }}>
          {[
            { v: '99.4%', l: 'AI Mapping Accuracy', color: '#a78bfa' },
            { v: '<12ms', l: 'API Response Time',    color: '#60a5fa' },
            { v: '100%',  l: 'Tenant Isolation',     color: '#34d399' },
            { v: '5+',    l: 'DB Engines Supported', color: '#fbbf24' },
          ].map(s => (
            <div key={s.l} style={{ ...glassCard, padding: '1.25rem 1rem', textAlign: 'center' }}>
              <div style={{ fontSize: '1.875rem', fontWeight: 900, color: s.color, letterSpacing: '-0.03em', lineHeight: 1 }}>{s.v}</div>
              <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.40)', marginTop: '0.375rem', fontWeight: 500 }}>{s.l}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ── Features ─────────────────────────────────────────────────────────────────
const Features: React.FC = () => {
  const features = [
    { icon: <Brain style={{ width: 22, height: 22 }} />,    gradStart: '#7c3aed', gradEnd: '#a855f7', title: 'AI-Assisted FHIR Mapping',   desc: 'LLaMA 3.2 + Gemini dual-model RAG suggests field mappings with 99.4% accuracy. Explainable AI shows reasoning for every decision.' },
    { icon: <Zap style={{ width: 22, height: 22 }} />,      gradStart: '#d97706', gradEnd: '#f59e0b', title: 'Real-Time CDC',               desc: 'Client-side agent monitors hospital DBs for changes and pushes to the central FHIR repository in near real-time — no polling lag.' },
    { icon: <Shield style={{ width: 22, height: 22 }} />,   gradStart: '#059669', gradEnd: '#10b981', title: 'PostgreSQL RLS Isolation',    desc: "Row-Level Security enforced at database engine level. Hospital B cannot access Hospital A's data — even with direct SQL queries." },
    { icon: <Database style={{ width: 22, height: 22 }} />, gradStart: '#2563eb', gradEnd: '#3b82f6', title: 'Multi-DB Support',            desc: 'PostgreSQL, MySQL, SQL Server, MongoDB, Oracle — all supported via adapter pattern. No schema changes at the source hospital.' },
    { icon: <Globe style={{ width: 22, height: 22 }} />,    gradStart: '#0891b2', gradEnd: '#06b6d4', title: 'FHIR R4 Compliance',          desc: 'All data standardised to HL7 FHIR R4 — Patient, Encounter, Observation, MedicationRequest. Interoperable with any FHIR consumer.' },
    { icon: <Activity style={{ width: 22, height: 22 }} />, gradStart: '#dc2626', gradEnd: '#f87171', title: 'Live Monitoring',             desc: 'Prometheus + Grafana observability, sync health dashboards, ETL job tracking, and real-time alerting for failures.' },
    { icon: <Lock style={{ width: 22, height: 22 }} />,     gradStart: '#7c3aed', gradEnd: '#6366f1', title: 'AES-256 + TLS 1.3',          desc: 'All PHI encrypted at rest with AES-256-GCM. All traffic encrypted in transit with TLS 1.3. Tamper-resistant audit trail.' },
    { icon: <Layers style={{ width: 22, height: 22 }} />,   gradStart: '#d97706', gradEnd: '#f59e0b', title: 'Multi-Tenant Architecture',   desc: 'PostgreSQL partitioned by tenant. Onboard unlimited hospitals with automatic partition creation and isolated data access.' },
  ];

  return (
    <section id="features" style={{ padding: '6rem 1.5rem', position: 'relative' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        <div style={sectionHeadStyle}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.25)', color: '#60a5fa', fontSize: '0.6875rem', fontWeight: 800, padding: '0.3rem 0.875rem', borderRadius: '2rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '1rem' }}>
            CAPABILITIES
          </div>
          <h2 style={sectionTitle}>Everything a hospital network needs</h2>
          <p style={sectionSub}>Built on enterprise architecture principles — not just a student project.</p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(260px,1fr))', gap: '1.25rem' }}>
          {features.map(f => (
            <div key={f.title} style={{ ...glassCard, padding: '1.5rem', transition: 'transform 0.25s, box-shadow 0.25s, border-color 0.25s', cursor: 'default' }}
              onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.transform = 'translateY(-4px)'; el.style.boxShadow = '0 20px 48px rgba(0,0,0,0.50), 0 0 0 1px rgba(139,92,246,0.20), inset 0 1px 0 rgba(255,255,255,0.10)'; el.style.borderColor = 'rgba(139,92,246,0.22)'; }}
              onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.transform = 'translateY(0)'; el.style.boxShadow = '0 8px 32px rgba(0,0,0,0.40),inset 0 1px 0 rgba(255,255,255,0.06)'; el.style.borderColor = 'rgba(255,255,255,0.09)'; }}>
              <div style={{ width: 48, height: 48, borderRadius: '0.875rem', background: `linear-gradient(135deg,${f.gradStart},${f.gradEnd})`, display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem', color: '#fff', boxShadow: `0 4px 16px ${f.gradStart}55` }}>
                {f.icon}
              </div>
              <h3 style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'rgba(255,255,255,0.90)', marginBottom: '0.5rem', margin: '0 0 0.5rem' }}>{f.title}</h3>
              <p style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.42)', lineHeight: 1.65, margin: 0 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ── How It Works ─────────────────────────────────────────────────────────────
const HowItWorks: React.FC = () => {
  const steps = [
    { n: '01', title: 'Connect Hospital DB',     desc: 'Install our lightweight CDC agent on the hospital machine. It detects changes in any DB engine and pushes them securely to CareLock central.',  color: '#a78bfa' },
    { n: '02', title: 'AI Mapping Suggestions',  desc: 'LLaMA 3.2 analyses the hospital schema and suggests FHIR R4 field mappings with confidence scores. Admin reviews and approves in one click.',  color: '#60a5fa' },
    { n: '03', title: 'FHIR Transformation',     desc: 'Approved mappings run through the ETL pipeline. Each record is transformed, validated against FHIR R4 schema, and encrypted before storage.',  color: '#34d399' },
    { n: '04', title: 'Tenant-Isolated Storage', desc: 'Transformed records land in the central FHIR DB inside an isolated tenant partition. Row-Level Security prevents any cross-hospital data access.', color: '#fbbf24' },
    { n: '05', title: 'AI Analytics & Queries',  desc: 'Authorised users can run natural language queries across FHIR data via the RAG chatbot. Powered by ChromaDB + Gemini for accurate, cited answers.',  color: '#c084fc' },
  ];

  return (
    <section id="how-it-works" style={{ padding: '6rem 1.5rem', position: 'relative' }}>
      {/* Subtle divider glow */}
      <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: '60%', height: 1, background: 'linear-gradient(90deg,transparent,rgba(139,92,246,0.30),transparent)' }} />

      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <div style={sectionHeadStyle}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', color: '#c084fc', fontSize: '0.6875rem', fontWeight: 800, padding: '0.3rem 0.875rem', borderRadius: '2rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '1rem' }}>
            HOW IT WORKS
          </div>
          <h2 style={sectionTitle}>Five steps from raw data to secure analytics</h2>
          <p style={sectionSub}>A proven pipeline — production-ready from day one.</p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {steps.map((step, i) => (
            <div key={step.n} style={{ display: 'flex', alignItems: 'flex-start', gap: '1.25rem', ...glassCard, padding: '1.375rem 1.5rem', transition: 'transform 0.25s, border-color 0.25s' }}
              onMouseEnter={e => { const el = e.currentTarget as HTMLElement; el.style.transform = 'translateX(4px)'; el.style.borderColor = `${step.color}40`; }}
              onMouseLeave={e => { const el = e.currentTarget as HTMLElement; el.style.transform = 'translateX(0)'; el.style.borderColor = 'rgba(255,255,255,0.09)'; }}>
              {/* Number badge */}
              <div style={{ width: 44, height: 44, borderRadius: '0.75rem', background: `linear-gradient(135deg,${step.color}33,${step.color}15)`, border: `1px solid ${step.color}40`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8125rem', fontWeight: 800, color: step.color, flexShrink: 0 }}>
                {step.n}
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'rgba(255,255,255,0.90)', margin: '0 0 0.375rem' }}>{step.title}</h3>
                <p style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.42)', lineHeight: 1.65, margin: 0 }}>{step.desc}</p>
              </div>
              {i < steps.length - 1 && (
                <ArrowRight style={{ width: 15, height: 15, color: 'rgba(255,255,255,0.20)', flexShrink: 0, marginTop: 4 }} />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ── Architecture ─────────────────────────────────────────────────────────────
const Architecture: React.FC = () => {
  const nodes = [
    { label: 'Hospital DBs',    sub: 'Any schema',    gradStart: '#7c3aed', gradEnd: '#a855f7' },
    { label: 'CDC Agent',       sub: 'Client-side',   gradStart: '#2563eb', gradEnd: '#3b82f6' },
    { label: 'AI Mapper',       sub: 'LLaMA + RAG',   gradStart: '#6366f1', gradEnd: '#818cf8' },
    { label: 'ETL Pipeline',    sub: 'Transform',     gradStart: '#7c3aed', gradEnd: '#6366f1' },
    { label: 'FHIR Central DB', sub: 'FHIR R4 + RLS', gradStart: '#059669', gradEnd: '#10b981' },
    { label: 'Analytics API',   sub: 'RAG Chatbot',   gradStart: '#0891b2', gradEnd: '#06b6d4' },
  ];

  const techStack = [
    { label: 'FastAPI + Python', sub: 'Backend' },
    { label: 'PostgreSQL 15',    sub: 'Central DB + RLS' },
    { label: 'React 19 + TS',    sub: 'Frontend' },
    { label: 'LLaMA 3.2 / phi3', sub: 'AI Engine' },
    { label: 'Docker Compose',   sub: 'Infrastructure' },
    { label: 'ChromaDB',         sub: 'Vector Store' },
  ];

  return (
    <section id="architecture" style={{ padding: '6rem 1.5rem', position: 'relative' }}>
      <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: '60%', height: 1, background: 'linear-gradient(90deg,transparent,rgba(59,130,246,0.30),transparent)' }} />

      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={sectionHeadStyle}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)', color: '#34d399', fontSize: '0.6875rem', fontWeight: 800, padding: '0.3rem 0.875rem', borderRadius: '2rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '1rem' }}>
            ARCHITECTURE
          </div>
          <h2 style={sectionTitle}>System Architecture</h2>
          <p style={sectionSub}>Microservice-inspired, containerised, production-ready.</p>
        </div>

        {/* Pipeline */}
        <div style={{ ...glassCard, padding: '2rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: '0.75rem' }}>
            {nodes.map((n, i, arr) => (
              <React.Fragment key={n.label}>
                <div style={{ background: `linear-gradient(135deg,${n.gradStart}33,${n.gradEnd}18)`, border: `1px solid ${n.gradStart}40`, borderRadius: '0.875rem', padding: '0.875rem 1.25rem', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'rgba(255,255,255,0.88)' }}>{n.label}</div>
                  <div style={{ fontSize: '0.6875rem', color: 'rgba(255,255,255,0.40)', marginTop: '0.25rem' }}>{n.sub}</div>
                </div>
                {i < arr.length - 1 && <ArrowRight style={{ width: 16, height: 16, color: 'rgba(255,255,255,0.25)', flexShrink: 0 }} />}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Tech stack */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(160px,1fr))', gap: '0.875rem' }}>
          {techStack.map(t => (
            <div key={t.label} style={{ ...glassCard, padding: '0.875rem 1rem', display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
              <CheckCircle2 style={{ width: 14, height: 14, color: '#34d399', flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>{t.label}</div>
                <div style={{ fontSize: '0.6875rem', color: 'rgba(255,255,255,0.38)' }}>{t.sub}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

// ── About ─────────────────────────────────────────────────────────────────────
const About: React.FC = () => (
  <section id="about" style={{ padding: '6rem 1.5rem', position: 'relative' }}>
    <div style={{ position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)', width: '60%', height: 1, background: 'linear-gradient(90deg,transparent,rgba(139,92,246,0.30),transparent)' }} />
    {/* Purple glow behind section */}
    <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse 70% 60% at 50% 50%,rgba(99,66,236,0.12) 0%,transparent 70%)', pointerEvents: 'none' }} />

    <div style={{ maxWidth: 900, margin: '0 auto', textAlign: 'center', position: 'relative' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.25)', color: '#c084fc', fontSize: '0.6875rem', fontWeight: 800, padding: '0.3rem 0.875rem', borderRadius: '2rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '1.25rem' }}>
        ABOUT
      </div>
      <h2 style={{ ...sectionTitle, marginBottom: '1.25rem' }}>Final Year Research Project</h2>
      <p style={{ fontSize: '1.0625rem', color: 'rgba(255,255,255,0.45)', lineHeight: 1.75, marginBottom: '3rem', maxWidth: 700, margin: '0 auto 3rem' }}>
        CareLock Sync is a research-grade healthcare interoperability platform developed at
        Bahria University Lanore Campus. It addresses the critical challenge of siloed hospital data
        systems in Pakistan — making cross-hospital analytics and AI-driven insights possible
        without compromising patient data security.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: '1.25rem', maxWidth: 760, margin: '0 auto 2.5rem' }}>
        {[
          { name: 'Waleed Khalid',   role: ' ', color: '#a78bfa' },
          { name: 'Muhammad Mohsin', role: ' ',     color: '#60a5fa' },
          { name: 'Shahmeer Nadeem', role: ' ',         color: '#34d399' },
        ].map(m => (
          <div key={m.name} style={{ ...glassCard, padding: '1.5rem', textAlign: 'center' }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', background: `linear-gradient(135deg,${m.color}33,${m.color}15)`, border: `1px solid ${m.color}40`, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.875rem', fontSize: '1rem', fontWeight: 800, color: m.color }}>
              {m.name.split(' ').map(n => n[0]).join('')}
            </div>
            <div style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'rgba(255,255,255,0.88)', marginBottom: '0.375rem' }}>{m.name}</div>
            <div style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.40)' }}>{m.role}</div>
          </div>
        ))}
      </div>

      <p style={{ fontSize: '0.99rem', color: 'rgba(255,255,255,0.30)' }}>
        Supervised by Dr. Muhammad Saqib Sohail · Bahria University Lahore Campus · 2025–2026
      </p>
    </div>
  </section>
);

// ── Footer ─────────────────────────────────────────────────────────────────────
const Footer: React.FC = () => {
  const navigate = useNavigate();

  return (
    <footer style={{ borderTop: '1px solid rgba(255,255,255,0.06)', background: 'rgba(4,6,14,0.70)', backdropFilter: 'blur(20px)', padding: '2.5rem 1.5rem' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1.25rem' }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.625rem' }}>
          <div style={{ width: 30, height: 30, borderRadius: '0.625rem', background: 'linear-gradient(135deg,#7c3aed,#6366f1)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Shield style={{ width: 14, height: 14, color: '#fff' }} />
          </div>
          <span style={{ fontSize: '0.9375rem', fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>CareLock Sync</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          {[
            ['Login',        () => { console.log('[FOOTER] Login clicked, navigating to:', PUBLIC_ROUTES.LOGIN); navigate(PUBLIC_ROUTES.LOGIN); }],
            ['Features',     '#features'],
            ['How It Works', '#how-it-works'],
            ['About',        '#about'],
          ].map(([label, action]) => (
            typeof action === 'function'
              ? <button type="button" key={label as string} onClick={action as () => void} style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.38)', background: 'none', border: 'none', cursor: 'pointer', transition: 'color 0.2s' }}
                  onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.70)')}
                  onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.38)')}>{label as string}</button>
              : <a key={label as string} href={action as string} style={{ fontSize: '0.8125rem', color: 'rgba(255,255,255,0.38)', textDecoration: 'none', transition: 'color 0.2s' }}
                  onMouseEnter={e => ((e.target as HTMLElement).style.color = 'rgba(255,255,255,0.70)')}
                  onMouseLeave={e => ((e.target as HTMLElement).style.color = 'rgba(255,255,255,0.38)')}>{label as string}</a>
          ))}
        </div>

        <p style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.25)', margin: 0 }}>
          © 2026 CareLock Sync · BULC
        </p>
      </div>
    </footer>
  );
};

// ── Main page ──────────────────────────────────────────────────────────────────
const HomePage: React.FC = () => (
  <div style={{ minHeight: '100vh', fontFamily: "'Inter',-apple-system,sans-serif" }}>
    <Navbar />
    <Hero />
    <Features />
    <HowItWorks />
    <Architecture />
    <About />
    <Footer />
  </div>
);

export default HomePage;
