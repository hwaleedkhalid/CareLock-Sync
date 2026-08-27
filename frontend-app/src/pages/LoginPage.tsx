/**
 * pages/LoginPage.tsx — legacy login page stub, kept for reference.
 * Active login is handled by src/auth-portal/ (LoginPage + role selector).
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Shield } from 'lucide-react';

const LoginPage: React.FC = () => {
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error]                 = useState('');
  const [loading]               = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    navigate(`/auth/login?email=${encodeURIComponent(email)}`);
  };

  const inp: React.CSSProperties = {
    width: '100%', background: 'rgba(13,20,42,0.55)', border: '1px solid rgba(139,92,246,0.22)',
    borderRadius: '0.625rem', padding: '0.75rem 1rem', fontSize: '0.9375rem',
    color: '#e2e8f0', outline: 'none', boxSizing: 'border-box', fontFamily: 'inherit',
    transition: 'border-color 0.2s, box-shadow 0.2s',
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem', background: 'linear-gradient(135deg, #080c18 0%, #0d1028 50%, #12052a 100%)' }}>
      <div style={{ width: '100%', maxWidth: 420, background: 'rgba(13,20,42,0.72)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)' as any, border: '1px solid rgba(139,92,246,0.18)', borderRadius: '1.25rem', boxShadow: '0 25px 50px rgba(0,0,0,0.5)', padding: '2.5rem 2rem' }}>

        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ width: 48, height: 48, borderRadius: '0.875rem', background: 'linear-gradient(135deg,#8b5cf6,#3b82f6)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem' }}>
            <Shield style={{ width: 22, height: 22, color: '#fff' }} />
          </div>
          <h1 style={{ margin: 0, fontSize: '1.375rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.03em' }}>CareLock Sync</h1>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: 'rgba(148,163,184,0.7)' }}>Hospital Database Synchronization</p>
        </div>

        {/* Error */}
        {error && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '0.625rem', padding: '0.75rem', marginBottom: '1.25rem', fontSize: '0.875rem', color: '#fca5a5' }}>
            <AlertCircle style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.125rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: 'rgba(148,163,184,0.85)', marginBottom: '0.375rem' }}>Email address</label>
            <input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="admin@hospital.com" required style={inp}
              onFocus={e => { e.target.style.borderColor = 'rgba(139,92,246,0.6)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.15)'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(139,92,246,0.22)'; e.target.style.boxShadow = 'none'; }} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, color: 'rgba(148,163,184,0.85)', marginBottom: '0.375rem' }}>Password</label>
            <input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" required style={inp}
              onFocus={e => { e.target.style.borderColor = 'rgba(139,92,246,0.6)'; e.target.style.boxShadow = '0 0 0 3px rgba(139,92,246,0.15)'; }}
              onBlur={e => { e.target.style.borderColor = 'rgba(139,92,246,0.22)'; e.target.style.boxShadow = 'none'; }} />
          </div>
          <button type="submit" disabled={loading}
            style={{ width: '100%', padding: '0.75rem', background: 'linear-gradient(135deg,#8b5cf6,#3b82f6)', color: '#fff', border: 'none', borderRadius: '0.625rem', fontSize: '0.9375rem', fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit', opacity: loading ? 0.5 : 1, transition: 'opacity 0.2s', marginTop: '0.25rem' }}>
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: '0.8125rem', color: 'rgba(148,163,184,0.45)', marginTop: '1.5rem' }}>
          Secure healthcare data synchronization platform
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
