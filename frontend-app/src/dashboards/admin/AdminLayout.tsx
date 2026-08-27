/**
 * dashboards/admin/AdminLayout.tsx
 * Dark glassmorphism sidebar layout — FIXED:
 *  - Sidebar uses useRef + direct style mutation (no CSS media query hack)
 *  - Hamburger: toggles collapsed on desktop, toggles mobileOpen on mobile
 *  - All colors from --ds-* CSS variables (theme-aware)
 */
import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Shield, Crown, LayoutDashboard, Building2, Lock,
  Brain, Activity, Zap,
  LogOut, Menu, X,
} from 'lucide-react';
import { useAuth } from '../../shared/context/AuthContext';
import ThemeToggle from '../../shared/ui/ThemeToggle';

interface NavItem { to: string; label: string; icon: React.ReactNode; badge?: string }
interface NavSection { title: string; items: NavItem[] }

const NAV: NavSection[] = [
  { title: 'Overview', items: [
    { to: '/admin/system-health',  label: 'System Health',   icon: <LayoutDashboard style={{ width: 15, height: 15 }} /> },
    { to: '/admin/sync-analytics', label: 'Sync Analytics',  icon: <Activity        style={{ width: 15, height: 15 }} /> },
  ]},
  { title: 'Tenant Management', items: [
    { to: '/admin/tenants', label: 'Hospital Registry', icon: <Building2 style={{ width: 15, height: 15 }} /> },
  ]},
  { title: 'AI & Mapping', items: [
    { to: '/admin/mapping', label: 'Mapping Review', icon: <Brain style={{ width: 15, height: 15 }} />, badge: 'AI' },
  ]},
  { title: 'Security & Compliance', items: [
    { to: '/admin/security', label: 'RLS Enforcement & Audit', icon: <Lock style={{ width: 15, height: 15 }} /> },
  ]},
  { title: 'Operations', items: [
    { to: '/admin/benchmark', label: 'Benchmark Center', icon: <Zap style={{ width: 15, height: 15 }} /> },
  ]},
];

// ── Sidebar inner content (shared by desktop + mobile drawer) ─────────────────
interface SidebarProps { user: any; collapsed: boolean; onLogout: () => void }
const SidebarContent: React.FC<SidebarProps> = ({ user, collapsed, onLogout }) => (
  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

    {/* Logo */}
    <div style={{ padding: collapsed ? '1.25rem 0' : '1.25rem 1rem', borderBottom: '1px solid var(--ds-sidebar-border)', display: 'flex', alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', gap: '0.625rem', flexShrink: 0 }}>
      <div style={{ width: 34, height: 34, borderRadius: '0.625rem', background: 'linear-gradient(135deg,#f59e0b,#f97316)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: '0 4px 12px rgba(245,158,11,0.35)' }}>
        <Crown style={{ width: 16, height: 16, color: '#fff' }} />
      </div>
      {!collapsed && (
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--ds-text-primary)', lineHeight: 1.2 }}>CareLock Sync</div>
          <div style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#f59e0b' }}>Super Admin</div>
        </div>
      )}
    </div>

    {/* User pill */}
    {!collapsed && user && (
      <div style={{ margin: '0.75rem 0.625rem 0', padding: '0.75rem', background: 'rgba(245,158,11,0.10)', border: '1px solid rgba(245,158,11,0.20)', borderRadius: '0.875rem', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{ width: 30, height: 30, borderRadius: '50%', background: 'linear-gradient(135deg,#f59e0b,#f97316)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, flexShrink: 0 }}>
            {user.display_name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ds-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.display_name}</div>
            <div style={{ fontSize: '0.6875rem', color: '#f59e0b', fontWeight: 600 }}>Super Admin</div>
          </div>
        </div>
      </div>
    )}

    {/* Nav */}
    <nav className="ds-scroll" style={{ flex: 1, padding: '0.75rem 0.625rem', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {NAV.map(section => (
        <div key={section.title}>
          {!collapsed && <div className="ds-nav-section-label">{section.title}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {section.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                title={collapsed ? item.label : undefined}
                className={({ isActive }) => `ds-nav-link${isActive ? ' active' : ''}`}
                style={collapsed ? { justifyContent: 'center', padding: '0.5rem 0' } : undefined}
              >
                {item.icon}
                {!collapsed && <span style={{ flex: 1 }}>{item.label}</span>}
                {!collapsed && item.badge && (
                  <span style={{ fontSize: '0.625rem', fontWeight: 800, padding: '0.15rem 0.4rem', borderRadius: '0.375rem', background: 'rgba(139,92,246,0.25)', color: '#a78bfa', letterSpacing: '0.03em' }}>
                    {item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>

    {/* Bottom actions */}
    <div style={{ padding: '0.625rem', borderTop: '1px solid var(--ds-sidebar-border)', display: 'flex', flexDirection: 'column', gap: '1px', flexShrink: 0 }}>
      <button
        onClick={onLogout}
        title={collapsed ? 'Sign out' : undefined}
        className="ds-nav-link"
        style={{ border: 'none', background: 'none', width: '100%', color: '#f87171', ...(collapsed ? { justifyContent: 'center', padding: '0.5rem 0' } : {}) }}
      >
        <LogOut style={{ width: 15, height: 15 }} />
        {!collapsed && <span>Sign out</span>}
      </button>
    </div>
  </div>
);

// ── Main layout ────────────────────────────────────────────────────────────────
const AdminLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  // Track screen size to determine hamburger behaviour
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)');
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
    handler(mq);
    mq.addEventListener('change', handler as (e: MediaQueryListEvent) => void);
    return () => mq.removeEventListener('change', handler as (e: MediaQueryListEvent) => void);
  }, []);

  const handleHamburger = () => {
    if (isMobile) {
      setMobileOpen(v => !v);
    } else {
      setCollapsed(v => !v);
    }
  };

  const handleLogout = () => { logout(); navigate('/'); };
  const initials = user?.display_name?.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() ?? 'SA';

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--ds-bg)', overflow: 'hidden', fontFamily: "'Inter', sans-serif" }}>

      {/* ── Desktop sidebar ── */}
      {!isMobile && (
        <aside
          className="ds-sidebar ds-scroll"
          style={{
            width: collapsed ? 60 : 228,
            minWidth: collapsed ? 60 : 228,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            transition: 'width 0.3s cubic-bezier(0.4,0,0.2,1), min-width 0.3s cubic-bezier(0.4,0,0.2,1)',
            overflowY: 'auto',
            overflowX: 'hidden',
          }}
        >
          <SidebarContent user={user} collapsed={collapsed} onLogout={handleLogout} />
        </aside>
      )}

      {/* ── Mobile drawer overlay ── */}
      {isMobile && mobileOpen && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50 }}>
          {/* Backdrop */}
          <div
            style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)' }}
            onClick={() => setMobileOpen(false)}
          />
          {/* Drawer */}
          <aside
            className="ds-sidebar ds-scroll"
            style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 228, zIndex: 51, display: 'flex', flexDirection: 'column', overflowY: 'auto', overflowX: 'hidden' }}
          >
            <SidebarContent user={user} collapsed={false} onLogout={() => { handleLogout(); setMobileOpen(false); }} />
          </aside>
          {/* Close button */}
          <button
            onClick={() => setMobileOpen(false)}
            style={{ position: 'absolute', top: '0.875rem', left: 240, zIndex: 52, background: 'rgba(255,255,255,0.10)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: '50%', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#fff' }}
          >
            <X style={{ width: 13, height: 13 }} />
          </button>
        </div>
      )}

      {/* ── Main content area ── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>

        {/* Top navbar */}
        <header
          className="ds-navbar"
          style={{ height: 56, display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0 1.25rem', flexShrink: 0 }}
        >
          {/* Hamburger */}
          <button
            onClick={handleHamburger}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ds-text-muted)', padding: '0.375rem', borderRadius: '0.5rem', display: 'flex', alignItems: 'center', transition: 'color 0.2s' }}
            onMouseEnter={e => ((e.currentTarget as HTMLElement).style.color = 'var(--ds-text-primary)')}
            onMouseLeave={e => ((e.currentTarget as HTMLElement).style.color = 'var(--ds-text-muted)')}
            aria-label="Toggle sidebar"
          >
            <Menu style={{ width: 18, height: 18 }} />
          </button>

          {/* Breadcrumb */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <Shield style={{ width: 14, height: 14, color: '#f59e0b' }} />
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--ds-text-secondary)' }}>Admin Portal</span>
          </div>

          <div style={{ flex: 1 }} />

          {/* Live badge */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.25)', borderRadius: '2rem', padding: '0.25rem 0.75rem' }}>
            <span className="ds-live-dot" />
            <span style={{ fontSize: '0.6875rem', fontWeight: 700, color: '#34d399' }}>Live</span>
          </div>

          {/* Theme toggle */}
          <ThemeToggle />

          {/* Avatar */}
          <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg,#f59e0b,#f97316)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '0.6875rem', fontWeight: 800, boxShadow: '0 2px 8px rgba(245,158,11,0.40)', cursor: 'pointer', flexShrink: 0 }}>
            {initials}
          </div>
        </header>

        {/* Page content */}
        <main
          className="ds-scroll"
          style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', background: 'var(--ds-bg)' }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;

