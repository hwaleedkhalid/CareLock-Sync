/**
 * dashboards/hospital/HospitalLayout.tsx — Dark glassmorphism, matches AdminLayout.
 */
import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Building2, LayoutDashboard, Database, FileText, Users,
  Activity, Brain, Settings, LogOut, Menu, Lock, X,
} from 'lucide-react';
import { useAuth } from '../../shared/context/AuthContext';
import ThemeToggle from '../../shared/ui/ThemeToggle';

const NAV = [
  {
    title: 'Overview', items: [
      { to: '/hospital/dashboard', label: 'Dashboard', icon: <LayoutDashboard style={{ width: 15, height: 15 }} /> },
      { to: '/hospital/monitoring', label: 'Sync Monitor', icon: <Activity style={{ width: 15, height: 15 }} /> },
    ]
  },
  {
    title: 'Data', items: [
      { to: '/hospital/data-sources', label: 'Data Sources', icon: <Database style={{ width: 15, height: 15 }} /> },
      { to: '/hospital/sync-report', label: 'Sync Reports', icon: <FileText style={{ width: 15, height: 15 }} /> },
    ]
  },
  {
    title: 'Patients', items: [
      { to: '/hospital/patients', label: 'Patient List', icon: <Users style={{ width: 15, height: 15 }} /> },
      { to: '/hospital/encounters', label: 'Encounters', icon: <Activity style={{ width: 15, height: 15 }} /> },
    ]
  },
  {
    title: 'Mapping', items: [
      { to: '/hospital/mapping', label: 'AI Mapping', icon: <Brain style={{ width: 15, height: 15 }} />, badge: 'AI' },
    ]
  },
];

const ACCENT = { grad: 'linear-gradient(135deg,#2563eb,#3b82f6)', glow: 'rgba(59,130,246,0.40)', color: '#60a5fa', pillBg: 'rgba(59,130,246,0.10)', pillBorder: 'rgba(59,130,246,0.20)' };

interface SidebarProps { user: any; collapsed: boolean; onLogout: () => void }
const SidebarContent: React.FC<SidebarProps> = ({ user, collapsed, onLogout }) => (
  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
    <div style={{ padding: collapsed ? '1.25rem 0' : '1.25rem 1rem', borderBottom: '1px solid var(--ds-sidebar-border)', display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', gap: '0.625rem', flexShrink: 0 }}>
      <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: ACCENT.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: `0 4px 12px ${ACCENT.glow}` }}>
        <Building2 style={{ width: 16, height: 16, color: '#fff' }} />
      </div>
      {!collapsed && <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', lineHeight: 1.2 }}>{user?.hospital_name ?? 'Hospital Admin'}</div>
        <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: ACCENT.color }}>Hospital Portal</div>
      </div>}
    </div>
    {!collapsed && user && (
      <div style={{ margin: '0.75rem 0.625rem 0', padding: '0.75rem', background: ACCENT.pillBg, border: `1px solid ${ACCENT.pillBorder}`, borderRadius: '0.875rem', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', background: ACCENT.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, flexShrink: 0 }}>
            {user.display_name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.display_name}</div>
            <div style={{ fontSize: '0.6875rem', color: ACCENT.color, fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Lock style={{ width: 9, height: 9 }} /> Tenant #{user.tenant_id}
            </div>
          </div>
        </div>
      </div>
    )}
    <nav className="ds-scroll" style={{ flex: 1, padding: '0.75rem 0.625rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {NAV.map(section => (
        <div key={section.title}>
          {!collapsed && <div className="ds-nav-section-label">{section.title}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {section.items.map((item: any) => (
              <NavLink key={item.to} to={item.to} title={collapsed ? item.label : undefined}
                className={({ isActive }) => `ds-nav-link${isActive ? ' active' : ''}`}
                style={collapsed ? { justifyContent: 'center', padding: '0.5rem 0' } : undefined}>
                {item.icon}
                {!collapsed && <span style={{ flex: 1 }}>{item.label}</span>}
                {!collapsed && item.badge && <span style={{ fontSize: '0.625rem', fontWeight: 800, padding: '0.15rem 0.4rem', borderRadius: '0.375rem', background: `${ACCENT.color}33`, color: ACCENT.color }}>{item.badge}</span>}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
    <div style={{ padding: '0.625rem', borderTop: '1px solid var(--ds-sidebar-border)', display: 'flex', flexDirection: 'column', gap: '1px', flexShrink: 0 }}>
      <NavLink to="/hospital/settings" title={collapsed ? 'Settings' : undefined} className={({ isActive }) => `ds-nav-link${isActive ? ' active' : ''}`} style={collapsed ? { justifyContent: 'center', padding: '0.5rem 0' } : undefined}>
        <Settings style={{ width: 15, height: 15 }} />{!collapsed && <span>Settings</span>}
      </NavLink>
      <button onClick={onLogout} className="ds-nav-link" title={collapsed ? 'Sign out' : undefined} style={{ border: 'none', background: 'none', width: '100%', color: '#f87171', ...(collapsed ? { justifyContent: 'center', padding: '0.5rem 0' } : {}) }}>
        <LogOut style={{ width: 15, height: 15 }} />{!collapsed && <span>Sign out</span>}
      </button>
    </div>
  </div>
);

const HospitalLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width:1023px)');
    const h = (e: MediaQueryList | MediaQueryListEvent) => setIsMobile(e.matches);
    h(mq); mq.addEventListener('change', h as (e: MediaQueryListEvent) => void);
    return () => mq.removeEventListener('change', h as (e: MediaQueryListEvent) => void);
  }, []);

  const handleLogout = () => { logout(); navigate('/'); };
  const initials = user?.display_name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() ?? 'HA';

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--ds-bg)', overflow: 'hidden', fontFamily: "'Inter',sans-serif" }}>
      {!isMobile && (
        <aside className="ds-sidebar ds-scroll" style={{ width: collapsed ? 60 : 228, minWidth: collapsed ? 60 : 228, flexShrink: 0, display: 'flex', flexDirection: 'column', transition: 'width 0.3s,min-width 0.3s', overflowY: 'auto', overflowX: 'hidden' }}>
          <SidebarContent user={user} collapsed={collapsed} onLogout={handleLogout} />
        </aside>
      )}
      {isMobile && mobileOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50 }}>
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)' }} onClick={() => setMobileOpen(false)} />
          <aside className="ds-sidebar ds-scroll" style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 228, zIndex: 51, display: 'flex', flexDirection: 'column', overflowY: 'auto', overflowX: 'hidden' }}>
            <SidebarContent user={user} collapsed={false} onLogout={() => { handleLogout(); setMobileOpen(false); }} />
          </aside>
          <button onClick={() => setMobileOpen(false)} style={{ position: 'absolute', top: '0.875rem', left: 240, zIndex: 52, background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '50%', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff' }}>
            <X style={{ width: 13, height: 13 }} />
          </button>
        </div>
      )}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        <header className="ds-navbar" style={{ height: 56, display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0 1.25rem', flexShrink: 0 }}>
          <button onClick={() => isMobile ? setMobileOpen(v => !v) : setCollapsed(v => !v)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ds-text-muted)', padding: '0.375rem', borderRadius: '0.5rem', display: 'flex', alignItems: 'center' }} aria-label="Toggle sidebar">
            <Menu style={{ width: 18, height: 18 }} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <Building2 style={{ width: 14, height: 14, color: ACCENT.color }} />
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>{user?.hospital_name ?? 'Hospital Portal'}</span>
          </div>
          <div style={{ flex: 1 }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '2rem', padding: '0.25rem 0.75rem' }}>
            <span className="ds-live-dot" />
            <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#34d399' }}>CDC Active</span>
          </div>
          <ThemeToggle />
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: ACCENT.grad, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, boxShadow: `0 2px 8px ${ACCENT.glow}`, flexShrink: 0 }}>
            {initials}
          </div>
        </header>
        <main className="ds-scroll" style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', background: 'var(--ds-bg)' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default HospitalLayout;
