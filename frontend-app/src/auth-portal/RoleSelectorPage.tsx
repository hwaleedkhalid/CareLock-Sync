/**
 * auth-portal/RoleSelectorPage.tsx
 * Role selector page — glassmorphism dark UI.
 * Navigates to /auth/login?role=&email= with the selected role pre-filled.
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, Crown, Building2, Stethoscope, ChartColumn,
  ArrowLeft, ArrowRight, Lock,
} from 'lucide-react';
import { PUBLIC_ROUTES } from '../shared/constants/routes';
import type { UserRole } from '../shared/types';

// ── Role card data ─────────────────────────────────────────────────────────────
interface RoleCard {
  role: UserRole;
  label: string;
  description: string;
  icon: React.ReactNode;
  demoEmail: string;
  demoPass: string;
  badge?: string;
  /* Visual theming */
  accentColor: string;          // solid hex/rgb for icon glow
  gradientFrom: string;         // card gradient top-left
  gradientTo: string;           // card gradient bottom-right
  glowColor: string;            // hover outer glow
  borderHover: string;          // hover border
  iconBg: string;               // icon badge bg
  cardClass: string;            // CSS class for role-card modifier
}

const ROLES: RoleCard[] = [
  {
    role: 'admin',
    label: 'Super Admin',
    description: 'Full platform access — manage hospitals, review AI mappings, security audit, global monitoring.',
    icon: <Crown style={{ width: 26, height: 26, color: '#f59e0b' }} />,
    demoEmail: 'admin@carelock.com',
    demoPass: 'admin123',
    badge: 'Evaluator',
    accentColor: '#f59e0b',
    gradientFrom: 'rgba(245,158,11,0.10)',
    gradientTo: 'rgba(245,158,11,0.02)',
    glowColor: 'rgba(245,158,11,0.25)',
    borderHover: 'rgba(245,158,11,0.40)',
    iconBg: 'rgba(245,158,11,0.15)',
    cardClass: 'admin-card',
  },
  {
    role: 'hospital',
    label: 'Hospital Admin',
    description: 'Manage your hospital tenant — patients, sync monitoring, CDC agent control, FHIR mappings.',
    icon: <Building2 style={{ width: 26, height: 26, color: '#3b82f6' }} />,
    demoEmail: 'hospital-a@carelock.com',
    demoPass: 'hospital123',
    accentColor: '#3b82f6',
    gradientFrom: 'rgba(59,130,246,0.10)',
    gradientTo: 'rgba(59,130,246,0.02)',
    glowColor: 'rgba(59,130,246,0.25)',
    borderHover: 'rgba(59,130,246,0.40)',
    iconBg: 'rgba(59,130,246,0.15)',
    cardClass: 'hospital-card',
  },
  {
    role: 'doctor',
    label: 'Doctor',
    description: 'View assigned patients, encounter history, FHIR records and medication overview.',
    icon: <Stethoscope style={{ width: 26, height: 26, color: '#10b981' }} />,
    demoEmail: 'doctor@carelock.com',
    demoPass: 'doctor123',
    accentColor: '#10b981',
    gradientFrom: 'rgba(16,185,129,0.10)',
    gradientTo: 'rgba(16,185,129,0.02)',
    glowColor: 'rgba(16,185,129,0.25)',
    borderHover: 'rgba(16,185,129,0.40)',
    iconBg: 'rgba(16,185,129,0.15)',
    cardClass: 'doctor-card',
  },
  {
    role: 'analyst',
    label: 'Analyst',
    description: 'Population health analytics, FHIR data trends, AI-powered reporting, hospital performance.',
    icon: <ChartColumn style={{ width: 26, height: 26, color: '#8b5cf6' }} />,
    demoEmail: 'analyst@carelock.com',
    demoPass: 'analyst123',
    accentColor: '#8b5cf6',
    gradientFrom: 'rgba(139,92,246,0.12)',
    gradientTo: 'rgba(139,92,246,0.02)',
    glowColor: 'rgba(139,92,246,0.30)',
    borderHover: 'rgba(139,92,246,0.45)',
    iconBg: 'rgba(139,92,246,0.18)',
    cardClass: 'analyst-card',
  },
];

// ── Component ──────────────────────────────────────────────────────────────────
const RoleSelectorPage: React.FC = () => {
  const navigate = useNavigate();
  const [hovered, setHovered] = useState<UserRole | null>(null);

  console.log('[ROLE_SELECTOR_PAGE] Component mounted/rendered');

  const handleSelect = (role: UserRole, email: string) => {
    const loginUrl = `${PUBLIC_ROUTES.LOGIN}?role=${role}&email=${encodeURIComponent(email)}`;
    console.log('[ROLE_SELECTOR] Role selected, navigating to:', loginUrl, { role, email });
    navigate(loginUrl);
  };

  /* ── Shared inline styles ── */
  const S = {
    page: {
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column' as const,
      position: 'relative' as const,
      zIndex: 1,
    } as React.CSSProperties,

    header: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '1.25rem 2rem',
      borderBottom: '1px solid rgba(255,255,255,0.05)',
    } as React.CSSProperties,

    logoRow: {
      display: 'flex',
      alignItems: 'center',
      gap: '0.625rem',
    } as React.CSSProperties,

    logoIcon: {
      width: 38,
      height: 38,
      borderRadius: '0.75rem',
      background: 'linear-gradient(135deg, #7c3aed 0%, #6366f1 50%, #3b82f6 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 4px 16px rgba(139,92,246,0.40)',
    } as React.CSSProperties,

    logoText: {
      fontSize: '1.0625rem',
      fontWeight: 700,
      color: 'var(--text-primary)',
      letterSpacing: '-0.01em',
    } as React.CSSProperties,

    backBtn: {
      display: 'flex',
      alignItems: 'center',
      gap: '0.375rem',
      fontSize: '0.8125rem',
      color: 'var(--text-muted)',
      background: 'none',
      border: 'none',
      cursor: 'pointer',
      fontFamily: "'Inter', sans-serif",
      transition: 'color 0.2s ease',
      padding: '0.375rem 0.75rem',
      borderRadius: '0.5rem',
    } as React.CSSProperties,

    main: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'center',
      justifyContent: 'center',
      padding: '3rem 1.5rem',
    } as React.CSSProperties,

    headingWrap: {
      textAlign: 'center' as const,
      marginBottom: '2.5rem',
    } as React.CSSProperties,

    eyebrow: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.4rem',
      fontSize: '0.75rem',
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase' as const,
      color: '#8b5cf6',
      background: 'rgba(139,92,246,0.12)',
      border: '1px solid rgba(139,92,246,0.25)',
      borderRadius: '2rem',
      padding: '0.3rem 0.875rem',
      marginBottom: '1rem',
    } as React.CSSProperties,

    h1: {
      fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
      fontWeight: 800,
      color: 'var(--text-primary)',
      margin: '0 0 0.75rem',
      letterSpacing: '-0.025em',
      lineHeight: 1.15,
    } as React.CSSProperties,

    subtitle: {
      fontSize: '0.9375rem',
      color: 'var(--text-secondary)',
      maxWidth: 480,
      margin: '0 auto',
      lineHeight: 1.6,
    } as React.CSSProperties,

    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
      gap: '1.125rem',
      width: '100%',
      maxWidth: 1040,
    } as React.CSSProperties,

    card: (r: RoleCard, isHovered: boolean) => ({
      padding: '1.625rem',
      background: isHovered
        ? `linear-gradient(135deg, ${r.gradientFrom}, ${r.gradientTo})`
        : 'rgba(255,255,255,0.035)',
      border: `1px solid ${isHovered ? r.borderHover : 'rgba(255,255,255,0.08)'}`,
      borderRadius: '1.375rem',
      cursor: 'pointer',
      textAlign: 'left' as const,
      transition: 'all 0.30s cubic-bezier(0.22, 1, 0.36, 1)',
      boxShadow: isHovered
        ? `0 20px 50px rgba(0,0,0,0.55), 0 0 35px ${r.glowColor}`
        : '0 4px 24px rgba(0,0,0,0.35)',
      transform: isHovered ? 'translateY(-5px) scale(1.018)' : 'translateY(0) scale(1)',
      backdropFilter: 'blur(24px)',
      WebkitBackdropFilter: 'blur(24px)',
      position: 'relative' as const,
      overflow: 'hidden' as const,
    } as React.CSSProperties),

    cardShimmer: (isHovered: boolean) => ({
      position: 'absolute' as const,
      top: 0,
      left: 0,
      right: 0,
      height: '1px',
      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)',
      opacity: isHovered ? 1 : 0,
      transition: 'opacity 0.35s ease',
    } as React.CSSProperties),

    badge: (r: RoleCard) => ({
      position: 'absolute' as const,
      top: '1rem',
      right: '1rem',
      fontSize: '0.6875rem',
      fontWeight: 700,
      letterSpacing: '0.04em',
      color: r.accentColor,
      background: `${r.iconBg}`,
      border: `1px solid ${r.borderHover}`,
      borderRadius: '2rem',
      padding: '0.2rem 0.6rem',
    } as React.CSSProperties),

    iconBadge: (r: RoleCard, isHovered: boolean) => ({
      width: 54,
      height: 54,
      borderRadius: '1rem',
      background: r.iconBg,
      border: `1px solid ${isHovered ? r.borderHover : 'rgba(255,255,255,0.06)'}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      marginBottom: '1.125rem',
      boxShadow: isHovered ? `0 0 20px ${r.glowColor}` : 'none',
      transition: 'box-shadow 0.30s ease, border-color 0.30s ease',
    } as React.CSSProperties),

    cardTitle: {
      fontSize: '1.0625rem',
      fontWeight: 700,
      color: 'var(--text-primary)',
      margin: '0 0 0.5rem',
      letterSpacing: '-0.01em',
    } as React.CSSProperties,

    cardDesc: {
      fontSize: '0.8125rem',
      color: 'var(--text-secondary)',
      lineHeight: 1.6,
      margin: '0 0 1.25rem',
    } as React.CSSProperties,

    divider: {
      height: '1px',
      background: 'rgba(255,255,255,0.06)',
      margin: '0 0 0.875rem',
    } as React.CSSProperties,

    credLabel: {
      fontSize: '0.6875rem',
      color: 'var(--text-muted)',
      fontWeight: 500,
      letterSpacing: '0.04em',
      textTransform: 'uppercase' as const,
      marginBottom: '0.3rem',
    } as React.CSSProperties,

    credEmail: {
      fontSize: '0.75rem',
      fontFamily: "'Courier New', monospace",
      color: 'var(--text-secondary)',
    } as React.CSSProperties,

    credPass: {
      fontSize: '0.75rem',
      fontFamily: "'Courier New', monospace",
      color: 'var(--text-muted)',
    } as React.CSSProperties,

    cta: (r: RoleCard, isHovered: boolean) => ({
      display: 'flex',
      alignItems: 'center',
      gap: '0.375rem',
      marginTop: '1rem',
      fontSize: '0.8125rem',
      fontWeight: 600,
      color: isHovered ? r.accentColor : 'var(--text-muted)',
      transition: 'color 0.25s ease, gap 0.25s ease',
    } as React.CSSProperties),

    footer: {
      padding: '1.25rem',
      textAlign: 'center' as const,
      borderTop: '1px solid rgba(255,255,255,0.05)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.4rem',
    } as React.CSSProperties,
  };

  return (
    <div className="auth-bg">
      <div style={S.page}>

        {/* ── Header ── */}
        <header style={S.header} className="animate-entry">
          <div style={S.logoRow}>
            <div style={S.logoIcon}>
              <Shield style={{ width: 18, height: 18, color: '#fff' }} />
            </div>
            <span style={S.logoText}>CareLock Sync</span>
          </div>
          <button
            id="back-to-home"
            style={S.backBtn}
            onClick={() => { console.log('[ROLE_SELECTOR] Back button clicked, navigating to:', PUBLIC_ROUTES.HOME); navigate(PUBLIC_ROUTES.HOME); }}
            onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)')}
            onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
          >
            <ArrowLeft style={{ width: 14, height: 14 }} />
            Back to home
          </button>
        </header>

        {/* ── Main ── */}
        <main style={S.main}>

          {/* Heading */}
          <div style={S.headingWrap} className="animate-entry animate-entry-delay-1">
            <div style={S.eyebrow}>
              <Shield style={{ width: 11, height: 11 }} />
              Secure Role-Based Access
            </div>
            <h1 style={S.h1}>Who are you signing in as?</h1>
            <p style={S.subtitle}>
              Select your role to enter the appropriate dashboard.
              Demo credentials are pre-filled automatically.
            </p>
          </div>

          {/* Role cards grid */}
          <div style={S.grid}>
            {ROLES.map((r, i) => {
              const isHov = hovered === r.role;
              return (
                <button
                  key={r.role}
                  id={`role-select-${r.role}`}
                  onClick={() => handleSelect(r.role, r.demoEmail)}
                  onMouseEnter={() => setHovered(r.role)}
                  onMouseLeave={() => setHovered(null)}
                  style={S.card(r, isHov)}
                  className={`animate-entry animate-entry-delay-${i + 2}`}
                >
                  {/* Top shimmer line */}
                  <div style={S.cardShimmer(isHov)} />

                  {/* Badge */}
                  {r.badge && <span style={S.badge(r)}>{r.badge}</span>}

                  {/* Icon */}
                  <div style={S.iconBadge(r, isHov)}>
                    {r.icon}
                  </div>

                  {/* Title + description */}
                  <h3 style={S.cardTitle}>{r.label}</h3>
                  <p style={S.cardDesc}>{r.description}</p>

                  {/* Demo credentials */}
                  <div style={S.divider} />
                  <div style={S.credLabel}>Demo credentials</div>
                  <div style={S.credEmail}>{r.demoEmail}</div>
                  <div style={S.credPass}>{r.demoPass}</div>

                  {/* CTA arrow */}
                  <div style={S.cta(r, isHov)}>
                    Sign in as {r.label}
                    <ArrowRight style={{ width: 13, height: 13, transition: 'transform 0.25s ease', transform: isHov ? 'translateX(3px)' : 'translateX(0)' }} />
                  </div>
                </button>
              );
            })}
          </div>
        </main>

        {/* ── Footer ── */}
        <footer style={S.footer}>
          <Lock style={{ width: 11, height: 11, color: 'var(--text-muted)' }} />
          <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
            256-bit TLS encryption · HIPAA-compliant · All sessions are logged and audited
          </span>
        </footer>

      </div>
    </div>
  );
};

export default RoleSelectorPage;
