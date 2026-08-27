/**
 * AuthGuard.tsx — Authentication Guard Wrapper
 *
 * Prevents component rendering and API calls until:
 * 1. Authentication context is fully initialized
 * 2. User has valid access_token
 * 3. All required auth state is ready
 *
 * CRITICAL: Prevents 403/401 errors by blocking early API calls
 */

import React from 'react';
import { useAuth } from '../context/AuthContext';

interface AuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

/**
 * AuthGuard Component
 *
 * Ensures authentication is ready before rendering protected content.
 * Returns loading state or error message if not authenticated.
 *
 * CRITICAL: Prevents API calls and component rendering until:
 * - User is authenticated
 * - Access token is available
 * - Auth context is fully initialized
 */
export const AuthGuard: React.FC<AuthGuardProps> = ({ children, fallback }) => {
  // useAuth hook will throw if AuthProvider is not wrapping this component
  // So we wrap in try-catch for graceful handling
  let authContext;
  try {
    authContext = useAuth();
  } catch {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--ds-text-muted)' }}>
        ⚠️ Authentication context not available. Ensure AuthProvider wraps the app.
      </div>
    );
  }

  const { isAuthenticated, user } = authContext;

  // Still initializing auth state
  if (!isAuthenticated || !user?.access_token) {
    return fallback || (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: 'var(--ds-bg-primary)',
        fontFamily: "'Inter', sans-serif",
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            color: 'var(--ds-text-muted)',
            marginBottom: '0.5rem',
          }}>
            🔐 Authenticating
          </div>
          <div style={{
            fontSize: '0.75rem',
            color: 'var(--ds-text-muted)',
            marginTop: '0.25rem',
          }}>
            Please wait while we verify your credentials...
          </div>
        </div>
      </div>
    );
  }

  // Auth ready — render protected content
  return <>{children}</>;
};

export default AuthGuard;
