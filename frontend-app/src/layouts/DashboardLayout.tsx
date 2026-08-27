/** layouts/DashboardLayout.tsx — Dark glassmorphism, replaces old light layout. */
import React, { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../shared/context/AuthContext';
import {
  LayoutDashboard, Users, FileText, Brain, ChartColumn,
  Activity, Settings, LogOut, Menu, X, Play,
  Shield, FlaskConical, BookOpen, TrendingUp, MessageSquare,
} from 'lucide-react';
import ThemeToggle from '../shared/ui/ThemeToggle';
import MetricsBadgeSummary from '../shared/ui/MetricsBadgeSummary';

interface Props { children: ReactNode }

const NAV_SECTIONS = [
  { label: 'Overview', items: [
    { path: '/demo',      icon: Play,           label: 'Live demo',           highlight: true },
    { path: '/executive', icon: TrendingUp,      label: 'Executive dashboard' },
    { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  ]},
  { label: 'Healthcare data', items: [
    { path: '/patients',   icon: Users,    label: 'Patients' },
    { path: '/encounters', icon: FileText, label: 'Encounters' },
  ]},
  { label: 'AI tools', items: [
    { path: '/ai-mapping', icon: Brain,         label: 'AI mapping' },
    { path: '/chat',       icon: MessageSquare, label: 'AI chatbot' },
  ]},
  { label: 'System', items: [
    { path: '/monitoring',       icon: Activity,     label: 'Monitoring' },
    { path: '/security',         icon: Shield,       label: 'Security' },
    { path: '/simulation',       icon: FlaskConical, label: 'Simulation lab' },
    { path: '/data-quality',     icon: ChartColumn,  label: 'Data quality' },
    { path: '/tenant-settings',  icon: Settings,     label: 'Tenant settings' },
  ]},
  { label: 'Project', items: [
    { path: '/research', icon: BookOpen, label: 'Research & innovation' },
  ]},
];

const DashboardLayout: React.FC<Props> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const mq = window.matchMedia('(max-width:1023px)');
    const h = (e: MediaQueryList | MediaQueryListEvent) => { setIsMobile(e.matches); if (e.matches) setSidebarOpen(false); };
    h(mq); mq.addEventListener('change', h as (e: MediaQueryListEvent) => void);
    return () => mq.removeEventListener('change', h as (e: MediaQueryListEvent) => void);
  }, []);

  const handleLogout = () => { logout(); navigate('/login'); };
  const initials = user?.display_name ? user.display_name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() : 'AD';

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--ds-bg)', overflow: 'hidden', fontFamily: "'Inter',sans-serif" }}>
      {/* Sidebar */}
      {(!isMobile || sidebarOpen) && (
        <>
          {isMobile && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)', zIndex: 40 }} onClick={() => setSidebarOpen(false)} />
          )}
          <aside className="ds-sidebar ds-scroll" style={{ ...(isMobile ? { position: 'fixed', left: 0, top: 0, bottom: 0, zIndex: 50 } : { position: 'relative' }), width: 228, minWidth: 228, flexShrink: 0, display: 'flex', flexDirection: 'column', overflowY: 'auto', overflowX: 'hidden' }}>
            {/* Logo */}
            <div style={{ padding: '1.25rem 1rem', borderBottom: '1px solid var(--ds-sidebar-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
              <div>
                <div style={{ fontSize: '0.9375rem', fontWeight: 800, color: '#818cf8', lineHeight: 1 }}>CareLock Sync</div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', marginTop: 2 }}>Healthcare Data Platform</div>
              </div>
              {isMobile && (
                <button onClick={() => setSidebarOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ds-text-muted)', display: 'flex', alignItems: 'center' }}>
                  <X style={{ width: 16, height: 16 }} />
                </button>
              )}
            </div>
            {/* User pill */}
            <div style={{ padding: '0.75rem 0.75rem 0', flexShrink: 0 }}>
              <div style={{ padding: '0.75rem', background: 'rgba(129,140,248,0.10)', border: '1px solid rgba(129,140,248,0.20)', borderRadius: '0.875rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg,#6366f1,#818cf8)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, flexShrink: 0 }}>{initials}</div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.display_name ?? 'Admin'}</div>
                    <div style={{ fontSize: '0.6875rem', color: '#818cf8', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.hospital_name ?? 'CareLock Platform'}</div>
                  </div>
                </div>
              </div>
            </div>
            {/* Nav */}
            <nav style={{ flex: 1, padding: '0.5rem 0.625rem', overflowY: 'auto' }}>
              {NAV_SECTIONS.map(section => (
                <div key={section.label} style={{ marginBottom: '1rem' }}>
                  <div className="ds-nav-section-label">{section.label}</div>
                  {section.items.map(item => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.path;
                    return (
                      <Link key={item.path} to={item.path} className={`ds-nav-link${isActive ? ' active' : ''}`} style={(item as any).highlight && !isActive ? { color: '#818cf8', background: 'rgba(129,140,248,0.08)', borderColor: 'rgba(129,140,248,0.25)' } : undefined}>
                        <Icon style={{ width: 15, height: 15 }} />
                        <span style={{ flex: 1 }}>{item.label}</span>
                        {(item as any).highlight && <span style={{ fontSize: '0.625rem', fontWeight: 800, padding: '0.15rem 0.4rem', borderRadius: '0.375rem', background: 'rgba(99,102,241,0.25)', color: '#818cf8' }}>Demo</span>}
                      </Link>
                    );
                  })}
                </div>
              ))}
            </nav>
            {/* Logout */}
            <div style={{ padding: '0.625rem', borderTop: '1px solid var(--ds-sidebar-border)', flexShrink: 0 }}>
              <button onClick={handleLogout} className="ds-nav-link" style={{ border: 'none', background: 'none', width: '100%', color: '#f87171' }}>
                <LogOut style={{ width: 15, height: 15 }} /><span>Logout</span>
              </button>
            </div>
          </aside>
        </>
      )}

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <header className="ds-navbar" style={{ height: 56, display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0 1.25rem', flexShrink: 0, position: 'sticky', top: 0, zIndex: 30 }}>
          <button onClick={() => setSidebarOpen(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ds-text-muted)', padding: '0.375rem', borderRadius: '0.5rem', display: 'flex', alignItems: 'center' }}>
            <Menu style={{ width: 18, height: 18 }} />
          </button>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <MetricsBadgeSummary />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--ds-text-muted)', fontSize: '0.75rem' }}>
            <span className="ds-live-dot" />
            <span style={{ color: '#34d399', fontWeight: 600, fontSize: '0.6875rem' }}>Sync active</span>
          </div>
          <span style={{ fontSize: '0.6875rem', color: 'var(--ds-text-muted)', borderLeft: '1px solid var(--ds-border)', paddingLeft: '0.75rem' }}>
            {new Date().toLocaleDateString('en-PK', { weekday: 'short', day: 'numeric', month: 'short' })}
          </span>
          <ThemeToggle />
        </header>
        <main className="ds-scroll" style={{ flex: 1, overflowY: 'auto', padding: '1.5rem' }}>
          {children}
        </main>
      </div>
    </div>
  );
};

export default DashboardLayout;
