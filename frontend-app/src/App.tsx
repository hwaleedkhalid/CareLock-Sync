/**
 * App.tsx — CareLock Sync Modular Frontend Router
 *
 * Flow:
 *   / (public site)  →  /auth/role (role selector)  →  /auth/login  →  /{role}/dashboard
 *
 * Route structure:
 *   Public:           /                    (marketing homepage)
 *   Auth:             /auth/role           (role selector)
 *                     /auth/login          (login with role pre-fill)
 *   Admin:            /admin/*             (Super Admin dashboard)
 *   Hospital:         /hospital/*          (Hospital Admin dashboard)
 *   Doctor:           /doctor/*            (Doctor dashboard)
 *   Analyst:          /analyst/*           (Analyst dashboard)
 *   Legacy:           /demo                (interactive demo — kept for backwards compat)
 */
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './shared/context/AuthContext';
import { ThemeProvider } from './shared/context/ThemeContext';
import { BackendStatusProvider, BackendStatusBanner } from './shared/context/BackendStatusContext';
import GlobalErrorBoundary from './shared/components/GlobalErrorBoundary';
import type { UserRole } from './shared/types';

// ── Public site ───────────────────────────────────────────────────────────────
import HomePage from './public-site/pages/HomePage';

// ── Auth portal ───────────────────────────────────────────────────────────────
import RoleSelectorPage from './auth-portal/RoleSelectorPage';
import LoginPage        from './auth-portal/LoginPage';

// ── Admin dashboard ───────────────────────────────────────────────────────────
import AdminLayout           from './dashboards/admin/AdminLayout';
import AdminDashboard        from './dashboards/admin/pages/AdminDashboard';
import TenantManagementPage  from './dashboards/admin/pages/TenantManagementPage';
import AdminSecurityPage     from './dashboards/admin/pages/SecurityCenterPage';
import SyncAnalyticsPage     from './dashboards/admin/pages/SyncAnalyticsPage';
import AdminMappingPage      from './dashboards/admin/pages/MappingReviewPage';
import AdminBenchmarkPage    from './dashboards/admin/pages/BenchmarkCenterPage';

// ── Hospital dashboard ────────────────────────────────────────────────────────
import HospitalLayout        from './dashboards/hospital/HospitalLayout';
import HospitalDashboard     from './dashboards/hospital/pages/HospitalDashboard';
import DataSourcesPage       from './dashboards/hospital/pages/DataSourcesPage';
import HospitalSyncPage      from './dashboards/hospital/pages/SyncReportPage';
import HospitalMappingPage   from './dashboards/hospital/pages/MappingReviewPage';
import HospitalPatientsPage  from './dashboards/hospital/pages/PatientsPage';
import HospitalEncounters    from './dashboards/hospital/pages/EncountersPage';

// ── Doctor dashboard ──────────────────────────────────────────────────────────
import DoctorLayout          from './dashboards/doctor/DoctorLayout';
import DoctorDashboard       from './dashboards/doctor/pages/DoctorDashboard';
import DoctorPatientsPage    from './dashboards/doctor/pages/PatientsPage';
import DoctorPatientDetail   from './dashboards/doctor/pages/PatientDetailPage';
import DoctorEncounters      from './dashboards/doctor/pages/EncountersPage';
import DoctorChatPage        from './dashboards/doctor/pages/ChatPage';

// ── Analyst dashboard ─────────────────────────────────────────────────────────
import AnalystLayout         from './dashboards/analyst/AnalystLayout';
import AnalystDashboard      from './dashboards/analyst/pages/AnalystDashboard';
import AnalystDataQuality    from './dashboards/analyst/pages/DataQualityPage';
import AnalystResearch       from './dashboards/analyst/pages/ResearchPage';
import AnalystChat           from './dashboards/analyst/pages/ChatPage';

// ── Legacy demo ───────────────────────────────────────────────────────────────
import SystemDemoPage            from './pages/SystemDemoPage';

// ── Public onboarding ─────────────────────────────────────────────────────────
import HospitalOnboardingPage    from './pages/HospitalOnboardingPage';

import './index.css';

// ── Route guards ──────────────────────────────────────────────────────────────

/** Redirect to the right dashboard once logged in */
const ROLE_HOME: Record<UserRole, string> = {
  admin:    '/admin/dashboard',
  hospital: '/hospital/dashboard',
  doctor:   '/doctor/dashboard',
  analyst:  '/analyst/dashboard',
};

/** Allow both authenticated and unauthenticated users to access public pages */
/** This enables demo mode users to switch roles without getting locked into a dashboard */
const PublicOnlyRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <>{children}</>;
};

/** Require authentication, redirect to role selector if not logged in */
const ProtectedRoute: React.FC<{ children: React.ReactNode; requiredRole?: UserRole }> = ({ children, requiredRole }) => {
  // CRITICAL: Hooks MUST be called unconditionally at the top
  const { isAuthenticated, user } = useAuth();

  // All conditional logic AFTER hooks to prevent "too many hooks" error
  if (!isAuthenticated) {
    return <Navigate to="/auth/role" replace />;
  }

  if (requiredRole && user?.role !== requiredRole) {
    // Wrong role — send to their own dashboard
    return <Navigate to={user ? ROLE_HOME[user.role] : '/auth/role'} replace />;
  }

  return <>{children}</>;
};

// ── Route tree ────────────────────────────────────────────────────────────────
function AppRoutes() {
  return (
    <Routes>
      {/* ── Public ── */}
      <Route path="/" element={<HomePage />} />
      <Route path="/onboarding" element={<HospitalOnboardingPage />} />

      {/* ── Auth portal ── */}
      <Route path="/auth/role"  element={<PublicOnlyRoute><RoleSelectorPage /></PublicOnlyRoute>} />
      <Route path="/auth/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />

      {/* ── Admin dashboard ── */}
      <Route path="/admin" element={<ProtectedRoute requiredRole="admin"><AdminLayout /></ProtectedRoute>}>
        <Route index                element={<Navigate to="system-health" replace />} />
        <Route path="system-health" element={<AdminDashboard />} />
        <Route path="sync-analytics" element={<SyncAnalyticsPage />} />
        <Route path="tenants"       element={<TenantManagementPage />} />
        <Route path="mapping"       element={<AdminMappingPage />} />
        <Route path="security"      element={<AdminSecurityPage />} />
        <Route path="benchmark"     element={<AdminBenchmarkPage />} />
      </Route>

      {/* ── Hospital dashboard ── */}
      <Route path="/hospital" element={<ProtectedRoute requiredRole="hospital"><HospitalLayout /></ProtectedRoute>}>
        <Route index                element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard"     element={<HospitalDashboard />} />
        <Route path="data-sources"  element={<DataSourcesPage />} />
        <Route path="sync-report"   element={<HospitalSyncPage />} />
        <Route path="mapping"       element={<HospitalMappingPage />} />
        <Route path="patients"      element={<HospitalPatientsPage />} />
        <Route path="encounters"    element={<HospitalEncounters />} />
        <Route path="monitoring"    element={<HospitalSyncPage />} />
      </Route>

      {/* ── Doctor dashboard ── */}
      <Route path="/doctor" element={<ProtectedRoute requiredRole="doctor"><DoctorLayout /></ProtectedRoute>}>
        <Route index                element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard"     element={<DoctorDashboard />} />
        <Route path="patients"      element={<DoctorPatientsPage />} />
        <Route path="patients/:id"  element={<DoctorPatientDetail />} />
        <Route path="encounters"    element={<DoctorEncounters />} />
        <Route path="chat"          element={<DoctorChatPage />} />
      </Route>

      {/* ── Analyst dashboard ── */}
      <Route path="/analyst" element={<ProtectedRoute requiredRole="analyst"><AnalystLayout /></ProtectedRoute>}>
        <Route index                element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard"     element={<AnalystDashboard />} />
        <Route path="data-quality"  element={<AnalystDataQuality />} />
        <Route path="research"      element={<AnalystResearch />} />
        <Route path="chat"          element={<AnalystChat />} />
      </Route>

      {/* ── Legacy / backwards-compat ── */}
      <Route path="/demo"     element={<ProtectedRoute><SystemDemoPage /></ProtectedRoute>} />
      <Route path="/login"    element={<Navigate to="/auth/login" replace />} />

      {/* ── Catch-all ── */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <GlobalErrorBoundary onLogout={() => {
      // Clear auth state on logout
      const event = new CustomEvent('auth-expired');
      window.dispatchEvent(event);
    }}>
      <ThemeProvider>
        <AuthProvider>
          <BackendStatusProvider>
            <BrowserRouter>
              <BackendStatusBanner />
              <AppRoutes />
            </BrowserRouter>
          </BackendStatusProvider>
        </AuthProvider>
      </ThemeProvider>
    </GlobalErrorBoundary>
  );
}

export default App;
