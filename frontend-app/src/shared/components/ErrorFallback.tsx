/**
 * ErrorFallback.tsx — Graceful Error UI Component
 *
 * Displays contextual error messages for:
 * - 403 Forbidden (Access Denied)
 * - 401 Unauthorized (Session Expired)
 * - Network errors
 * - Generic API errors
 *
 * CRITICAL: Never shows blank screen — always provides actionable feedback
 */

import React from 'react';
import { RefreshCw, AlertTriangle, LogOut } from 'lucide-react';
import type { ApiError } from '../services/apiClient';

interface ErrorFallbackProps {
  error: ApiError | Error | null;
  retry?: () => void;
  logout?: () => void;
  message?: string;
  detail?: string;
}

export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  retry,
  logout,
  message,
  detail,
}) => {
  // Determine error type and message
  let errorTitle = message || 'Error Loading Dashboard';
  let errorDetail = detail || 'An unexpected error occurred.';
  let errorType = 'generic';
  let actions: Array<{ label: string; action: () => void; variant?: 'primary' | 'secondary' }> = [];

  if (error && 'status' in error) {
    const apiError = error as ApiError;

    if (apiError.status === 403) {
      errorType = 'forbidden';
      errorTitle = '🔒 Access Denied';
      errorDetail = 'You do not have permission to view this dashboard.';
      if (logout) {
        actions.push({ label: 'Sign Out', action: logout });
      }
    } else if (apiError.status === 401) {
      errorType = 'unauthorized';
      errorTitle = '⏱️ Session Expired';
      errorDetail = 'Your authentication session has expired. Please sign in again.';
      if (logout) {
        actions.push({ label: 'Sign In Again', action: logout, variant: 'primary' });
      }
    } else if (apiError.status === 0 || apiError.type === 'NETWORK_ERROR') {
      errorType = 'network';
      errorTitle = '🌐 Connection Error';
      errorDetail = 'Unable to connect to the server. Check your network and try again.';
      if (retry) {
        actions.push({ label: 'Retry', action: retry, variant: 'primary' });
      }
    } else {
      errorDetail = apiError.userMessage || apiError.message || errorDetail;
      if (retry) {
        actions.push({ label: 'Retry', action: retry });
      }
    }
  } else if (error) {
    errorDetail = error.message || errorDetail;
    if (retry) {
      actions.push({ label: 'Retry', action: retry });
    }
  } else {
    if (retry) {
      actions.push({ label: 'Retry', action: retry });
    }
  }

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'var(--ds-bg-primary)',
      fontFamily: "'Inter', sans-serif",
      padding: '2rem',
    }}>
      <div style={{
        maxWidth: '500px',
        background: 'var(--ds-card-bg)',
        border: '1px solid var(--ds-card-border)',
        borderRadius: '1rem',
        padding: '2rem',
        boxShadow: 'var(--ds-card-shadow)',
        textAlign: 'center',
      }}>
        {/* Error Icon */}
        <div style={{ marginBottom: '1rem' }}>
          {errorType === 'forbidden' ? (
            <div style={{ fontSize: '3rem' }}>🔒</div>
          ) : errorType === 'unauthorized' ? (
            <div style={{ fontSize: '3rem' }}>⏱️</div>
          ) : errorType === 'network' ? (
            <div style={{ fontSize: '3rem' }}>🌐</div>
          ) : (
            <AlertTriangle style={{ width: 48, height: 48, color: '#f87171', margin: '0 auto' }} />
          )}
        </div>

        {/* Error Title */}
        <h1 style={{
          fontSize: '1.25rem',
          fontWeight: 700,
          color: 'var(--ds-text-primary)',
          margin: '0 0 0.5rem',
        }}>
          {errorTitle}
        </h1>

        {/* Error Details */}
        <p style={{
          fontSize: '0.875rem',
          color: 'var(--ds-text-muted)',
          margin: '0 0 1.5rem',
          lineHeight: 1.6,
        }}>
          {errorDetail}
        </p>

        {/* Technical Details (if available) */}
        {error && 'status' in error && (
          <div style={{
            background: 'var(--ds-surface-2)',
            border: '1px solid var(--ds-border)',
            borderRadius: '0.5rem',
            padding: '0.75rem',
            marginBottom: '1.5rem',
            textAlign: 'left',
          }}>
            <div style={{
              fontSize: '0.625rem',
              fontWeight: 600,
              color: 'var(--ds-text-muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              marginBottom: '0.25rem',
            }}>
              Technical Details
            </div>
            <div style={{
              fontSize: '0.75rem',
              color: 'var(--ds-text-muted)',
              fontFamily: 'monospace',
              wordBreak: 'break-word',
            }}>
              {(error as any).status && `Error ${(error as any).status}`}
              {(error as any).message && ` — ${(error as any).message}`}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{
          display: 'flex',
          gap: '0.75rem',
          justifyContent: 'center',
          flexWrap: 'wrap',
        }}>
          {actions.map((action, idx) => (
            <button
              key={idx}
              onClick={action.action}
              style={{
                padding: '0.75rem 1.5rem',
                fontSize: '0.875rem',
                fontWeight: 600,
                borderRadius: '0.5rem',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: action.variant === 'primary' ? '#3b82f6' : 'var(--ds-surface-2)',
                color: action.variant === 'primary' ? 'white' : 'var(--ds-text-primary)',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                if (action.variant === 'primary') {
                  e.currentTarget.style.background = '#2563eb';
                } else {
                  e.currentTarget.style.background = 'var(--ds-surface-3)';
                }
              }}
              onMouseLeave={(e) => {
                if (action.variant === 'primary') {
                  e.currentTarget.style.background = '#3b82f6';
                } else {
                  e.currentTarget.style.background = 'var(--ds-surface-2)';
                }
              }}
            >
              {action.label === 'Retry' && <RefreshCw style={{ width: 16, height: 16 }} />}
              {action.label === 'Sign Out' && <LogOut style={{ width: 16, height: 16 }} />}
              {action.label === 'Sign In Again' && <LogOut style={{ width: 16, height: 16 }} />}
              {action.label}
            </button>
          ))}
        </div>

        {/* Help Text */}
        {!actions.length && (
          <div style={{
            fontSize: '0.75rem',
            color: 'var(--ds-text-muted)',
            marginTop: '1rem',
            borderTop: '1px solid var(--ds-border)',
            paddingTop: '1rem',
          }}>
            Please contact support if this error persists.
          </div>
        )}
      </div>
    </div>
  );
};

export default ErrorFallback;
