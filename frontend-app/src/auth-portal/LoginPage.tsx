/**
 * auth-portal/LoginPage.tsx
 * Role-aware login page — glassmorphism dark UI.
 * Reads ?role=&email= from URL (set by RoleSelectorPage).
 * Supports real backend JWT login AND local demo-mode fallback.
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import {
  Shield, AlertCircle, Eye, EyeOff, ArrowLeft,
  Zap, Clock, Crown, Building2, Stethoscope, ChartColumn,
  Lock, Mail,
} from 'lucide-react';
import { useAuth } from '../shared/context/AuthContext';
import { ROLE_DASHBOARD_ROUTES } from '../shared/constants/routes';
import type { UserRole, AuthUser } from '../shared/types';

// ── Demo accounts (no backend required) ───────────────────────────────────────
const DEMO_ACCOUNTS: Record<
  string,
  { password: string; role: UserRole; display_name: string; hospital_name: string; tenant_id: number | null }
> = {
  'admin@carelock.com':       { password: 'admin123',    role: 'admin',    display_name: 'Super Admin',      hospital_name: 'CareLock Platform',    tenant_id: null },
  'hospital-a@carelock.com':  { password: 'hospital123', role: 'hospital', display_name: 'Hospital A Admin', hospital_name: 'City General Hospital', tenant_id: 1    },
  'doctor@carelock.com':      { password: 'doctor123',   role: 'doctor',   display_name: 'Dr. Ahmed Khan',   hospital_name: 'City General Hospital', tenant_id: 1    },
  'analyst@carelock.com':     { password: 'analyst123',  role: 'analyst',  display_name: 'Sarah Malik',       hospital_name: 'CareLock Analytics',   tenant_id: null },
};

const ROLE_META: Record<UserRole, {
  label: string;
  gradientFrom: string;
  gradientTo: string;
  glowColor: string;
  borderColor: string;
  icon: React.ReactNode;
}> = {
  admin:    {
    label: 'Super Admin',
    gradientFrom: 'rgba(245,158,11,0.15)',
    gradientTo: 'rgba(245,158,11,0.05)',
    glowColor: 'rgba(245,158,11,0.35)',
    borderColor: 'rgba(245,158,11,0.35)',
    icon: <Crown style={{ width: 14, height: 14 }} />,
  },
  hospital: {
    label: 'Hospital Admin',
    gradientFrom: 'rgba(59,130,246,0.15)',
    gradientTo: 'rgba(59,130,246,0.05)',
    glowColor: 'rgba(59,130,246,0.35)',
    borderColor: 'rgba(59,130,246,0.35)',
    icon: <Building2 style={{ width: 14, height: 14 }} />,
  },
  doctor:   {
    label: 'Doctor',
    gradientFrom: 'rgba(16,185,129,0.15)',
    gradientTo: 'rgba(16,185,129,0.05)',
    glowColor: 'rgba(16,185,129,0.35)',
    borderColor: 'rgba(16,185,129,0.35)',
    icon: <Stethoscope style={{ width: 14, height: 14 }} />,
  },
  analyst:  {
    label: 'Analyst',
    gradientFrom: 'rgba(139,92,246,0.18)',
    gradientTo: 'rgba(139,92,246,0.06)',
    glowColor: 'rgba(139,92,246,0.40)',
    borderColor: 'rgba(139,92,246,0.40)',
    icon: <ChartColumn style={{ width: 14, height: 14 }} />,
  },
};

const DEMO_ROLE_ICONS: Record<UserRole, React.ReactNode> = {
  admin:    <Crown    style={{ width: 13, height: 13 }} />,
  hospital: <Building2 style={{ width: 13, height: 13 }} />,
  doctor:   <Stethoscope style={{ width: 13, height: 13 }} />,
  analyst:  <ChartColumn style={{ width: 13, height: 13 }} />,
};

// Use centralized route constants (fixes admin route: was /admin/dashboard, now /admin/system-health)
const ROLE_REDIRECT = ROLE_DASHBOARD_ROUTES;

// ── Component ──────────────────────────────────────────────────────────────────
const LoginPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();

  console.log('[LOGIN_PAGE] Component mounted/rendered');

  const preRole  = (searchParams.get('role')  ?? '') as UserRole | '';
  const preEmail =  searchParams.get('email') ?? '';

  const [email,          setEmail]          = useState(preEmail);
  const [password,       setPassword]       = useState('');
  const [showPw,         setShowPw]         = useState(false);
  const [error,          setError]          = useState('');
  const [loading,        setLoading]        = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [focusedField,   setFocusedField]   = useState<'email' | 'password' | null>(null);

  // Detect redirect from an expired session
  useEffect(() => {
    if (sessionStorage.getItem('carelock_session_expired') === '1') {
      setSessionExpired(true);
      sessionStorage.removeItem('carelock_session_expired');
    }
  }, []);

  // Auto-fill demo password when email matches a known demo account
  useEffect(() => {
    if (email && DEMO_ACCOUNTS[email]) {
      setPassword(DEMO_ACCOUNTS[email].password);
    }
  }, [email]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_URL || ''}/api/v1/auth/login`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        },
      );

      if (res.ok) {
        const data = await res.json();
        const user: AuthUser = {
          email:         data.email         ?? email,
          display_name:  data.display_name  ?? email.split('@')[0],
          role:          (data.role         ?? preRole ?? 'admin') as UserRole,
          access_token:  data.access_token  ?? '',
          tenant_id:     data.tenant_id     ?? null,
          hospital_name: data.hospital_name ?? 'CareLock Platform',
          logged_in_at:  data.logged_in_at  ?? new Date().toISOString(),
        };
        login(user);
        const redirectRoute = ROLE_REDIRECT[user.role];
        console.log('[LOGIN] Backend auth successful', { role: user.role, redirectRoute });
        navigate(redirectRoute);
        return;
      }
    } catch {
      // Backend unavailable — fall through to demo mode
    }

    // Demo-mode fallback
    const demo = DEMO_ACCOUNTS[email.toLowerCase()];
    if (demo && demo.password === password) {
      const user: AuthUser = {
        email,
        display_name:  demo.display_name,
        role:          demo.role,
        access_token:  `demo-token-${demo.role}`,
        tenant_id:     demo.tenant_id,
        hospital_name: demo.hospital_name,
        logged_in_at:  new Date().toISOString(),
      };
      login(user);
      const redirectRoute = ROLE_REDIRECT[demo.role];
      console.log('[LOGIN] Demo mode auth successful', { role: demo.role, redirectRoute });
      navigate(redirectRoute);
    } else {
      console.log('[LOGIN] Invalid credentials', { email });
      setError('Invalid credentials. Click a demo account below to auto-fill.');
    }

    setLoading(false);
  };

  const roleMeta = (preRole && ROLE_META[preRole]) ? ROLE_META[preRole] : null;

  /* ── Styles (inline for scoped isolation from Tailwind) ── */
  const S = {
    page: {
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.5rem',
      position: 'relative' as const,
      zIndex: 1,
    } as React.CSSProperties,

    wrap: {
      width: '100%',
      maxWidth: 448,
      display: 'flex',
      flexDirection: 'column' as const,
      gap: '1.25rem',
    } as React.CSSProperties,

    logo: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.625rem',
      marginBottom: '0.25rem',
    } as React.CSSProperties,

    logoIcon: {
      width: 44,
      height: 44,
      borderRadius: '0.875rem',
      background: 'linear-gradient(135deg, #7c3aed 0%, #6366f1 50%, #3b82f6 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 4px 20px rgba(139,92,246,0.45)',
    } as React.CSSProperties,

    logoText: {
      fontSize: '1.25rem',
      fontWeight: 700,
      color: 'var(--text-primary)',
      letterSpacing: '-0.01em',
    } as React.CSSProperties,

    heading: {
      textAlign: 'center' as const,
      marginTop: '0.5rem',
    } as React.CSSProperties,

    h1: {
      fontSize: '1.75rem',
      fontWeight: 800,
      color: 'var(--text-primary)',
      margin: 0,
      letterSpacing: '-0.02em',
      lineHeight: 1.2,
    } as React.CSSProperties,

    subtitle: {
      fontSize: '0.9rem',
      color: 'var(--text-secondary)',
      marginTop: '0.375rem',
      fontWeight: 400,
    } as React.CSSProperties,

    roleBadge: (meta: typeof roleMeta) => ({
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      padding: '0.625rem 1rem',
      borderRadius: '0.875rem',
      background: `linear-gradient(135deg, ${meta?.gradientFrom}, ${meta?.gradientTo})`,
      border: `1px solid ${meta?.borderColor}`,
      boxShadow: `0 0 20px ${meta?.glowColor}`,
    } as React.CSSProperties),

    card: {
      padding: '2rem',
    } as React.CSSProperties,

    label: {
      display: 'block',
      fontSize: '0.8125rem',
      fontWeight: 600,
      color: 'var(--text-secondary)',
      marginBottom: '0.5rem',
      letterSpacing: '0.01em',
    } as React.CSSProperties,

    inputWrap: {
      position: 'relative' as const,
    } as React.CSSProperties,

    inputIcon: (active: boolean) => ({
      position: 'absolute' as const,
      left: '0.875rem',
      top: '50%',
      transform: 'translateY(-50%)',
      color: active ? '#8b5cf6' : 'var(--text-muted)',
      transition: 'color 0.25s ease',
      pointerEvents: 'none' as const,
      display: 'flex',
    } as React.CSSProperties),

    input: (focused: boolean) => ({
      width: '100%',
      paddingLeft: '2.75rem',
      paddingRight: '1rem',
      paddingTop: '0.75rem',
      paddingBottom: '0.75rem',
      background: focused ? 'rgba(255,255,255,0.08)' : 'var(--input-bg)',
      border: `1px solid ${focused ? '#8b5cf6' : 'var(--input-border)'}`,
      borderRadius: '0.75rem',
      color: 'var(--input-text)',
      fontSize: '0.875rem',
      fontFamily: "'Inter', sans-serif",
      outline: 'none',
      boxShadow: focused ? '0 0 0 3px rgba(139,92,246,0.22), 0 0 20px rgba(139,92,246,0.10)' : 'none',
      transition: 'border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease',
    } as React.CSSProperties),

    inputPwRight: (focused: boolean) => ({
      ...S.input(focused),
      paddingRight: '2.75rem',
    } as React.CSSProperties),

    eyeBtn: {
      position: 'absolute' as const,
      right: '0.875rem',
      top: '50%',
      transform: 'translateY(-50%)',
      background: 'none',
      border: 'none',
      padding: 0,
      color: 'var(--text-muted)',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      transition: 'color 0.2s ease',
    } as React.CSSProperties,

    submitBtn: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.5rem',
      marginTop: '0.5rem',
    } as React.CSSProperties,

    demoGrid: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: '0.625rem',
    } as React.CSSProperties,

    demoBtn: {
      padding: '0.625rem 0.75rem',
    } as React.CSSProperties,

    backLink: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.375rem',
      fontSize: '0.8125rem',
      color: 'var(--text-muted)',
      textDecoration: 'none',
      transition: 'color 0.2s ease',
      justifyContent: 'center',
    } as React.CSSProperties,

    securityNote: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.4rem',
      marginTop: '0.5rem',
    } as React.CSSProperties,
  };

  return (
    <div className="auth-bg">
      <div style={S.page}>
        <div style={S.wrap}>

          {/* ── Logo ── */}
          <div className="animate-entry" style={{ textAlign: 'center' }}>
            <div style={S.logo}>
              <div style={S.logoIcon}>
                <Shield style={{ width: 22, height: 22, color: '#fff' }} />
              </div>
              <span style={S.logoText}>CareLock Sync</span>
            </div>
            <div style={S.heading}>
              <h1 style={S.h1}>Welcome back</h1>
              <p style={S.subtitle}>Sign in to your secure dashboard</p>
            </div>
          </div>

          {/* ── Role badge ── */}
          {roleMeta && (
            <div className="animate-entry animate-entry-delay-1" style={S.roleBadge(roleMeta)}>
              <Zap style={{ width: 15, height: 15, color: '#fff', opacity: 0.9 }} />
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#fff', opacity: 0.9, flex: 1 }}>
                Signing in as&nbsp;<strong>{roleMeta.label}</strong>
              </span>
              <Link
                to="/auth/role"
                style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.55)', textDecoration: 'none', transition: 'color 0.2s ease' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.55)')}
              >
                Change
              </Link>
            </div>
          )}

          {/* ── Main card ── */}
          <div className="glass-card animate-entry animate-entry-delay-2" style={S.card}>

            {/* Session-expired banner */}
            {sessionExpired && (
              <div className="auth-alert auth-alert-warning">
                <Clock style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
                <span>Your session has expired. Please sign in again.</span>
              </div>
            )}

            {/* Error banner */}
            {error && (
              <div className="auth-alert auth-alert-error">
                <AlertCircle style={{ width: 15, height: 15, flexShrink: 0, marginTop: 1 }} />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>

              {/* Email */}
              <div>
                <label style={S.label}>Email address</label>
                <div style={S.inputWrap}>
                  <span style={S.inputIcon(focusedField === 'email')}>
                    <Mail style={{ width: 15, height: 15 }} />
                  </span>
                  <input
                    id="login-email"
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    onFocus={() => setFocusedField('email')}
                    onBlur={() => setFocusedField(null)}
                    required
                    placeholder="you@carelock.com"
                    style={S.input(focusedField === 'email')}
                  />
                </div>
              </div>

              {/* Password */}
              <div>
                <label style={S.label}>Password</label>
                <div style={S.inputWrap}>
                  <span style={S.inputIcon(focusedField === 'password')}>
                    <Lock style={{ width: 15, height: 15 }} />
                  </span>
                  <input
                    id="login-password"
                    type={showPw ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    onFocus={() => setFocusedField('password')}
                    onBlur={() => setFocusedField(null)}
                    required
                    placeholder="••••••••"
                    style={S.inputPwRight(focusedField === 'password')}
                  />
                  <button
                    type="button"
                    id="toggle-password-visibility"
                    onClick={() => setShowPw(v => !v)}
                    style={S.eyeBtn}
                    onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)')}
                    onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
                  >
                    {showPw
                      ? <EyeOff style={{ width: 15, height: 15 }} />
                      : <Eye    style={{ width: 15, height: 15 }} />}
                  </button>
                </div>
              </div>

              {/* Submit */}
              <button
                id="login-submit"
                type="submit"
                disabled={loading}
                className="auth-btn-primary"
              >
                <span style={S.submitBtn}>
                  {loading ? (
                    <>
                      <span className="auth-spinner" />
                      Signing in…
                    </>
                  ) : (
                    <>
                      <Shield style={{ width: 16, height: 16 }} />
                      Sign In Securely
                    </>
                  )}
                </span>
              </button>
            </form>

            {/* Demo quick-fill */}
            <div className="auth-divider"><span>Quick Demo Access</span></div>
            <div style={S.demoGrid}>
              {Object.entries(DEMO_ACCOUNTS).map(([mail, acc]) => {
                const meta = ROLE_META[acc.role];
                return (
                  <button
                    key={mail}
                    id={`demo-${acc.role}`}
                    type="button"
                    onClick={() => { setEmail(mail); setPassword(acc.password); }}
                    className="auth-btn-ghost"
                    style={S.demoBtn}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.2rem' }}>
                      <span style={{ color: meta.borderColor }}>{DEMO_ROLE_ICONS[acc.role]}</span>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {acc.display_name}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'monospace', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {mail}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* ── Footer ── */}
          <div className="animate-entry animate-entry-delay-3" style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            <Link
              to="/"
              style={S.backLink}
              onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-secondary)')}
              onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'var(--text-muted)')}
            >
              <ArrowLeft style={{ width: 13, height: 13 }} />
              Back to home
            </Link>
            <div style={S.securityNote}>
              <Lock style={{ width: 11, height: 11, color: 'var(--text-muted)' }} />
              <span style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                256-bit TLS encryption · HIPAA-compliant
              </span>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
};

export default LoginPage;
