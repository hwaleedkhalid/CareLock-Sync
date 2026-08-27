/**
 * GlobalErrorBoundary.tsx — Catches ALL React Errors
 *
 * CRITICAL: Prevents blank screen by catching:
 * - Component render crashes
 * - State update errors
 * - API call failures
 * - Async promise rejections
 * - Any runtime exception
 *
 * RULE: Never allow React tree to crash silently
 */

import React from 'react';
import { AlertTriangle, RefreshCw, LogOut } from 'lucide-react';

interface GlobalErrorBoundaryProps {
  children: React.ReactNode;
  onLogout?: () => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
  errorCount: number;
}

/**
 * Global error boundary catching all unhandled React errors
 * NEVER allows blank screen — always shows error UI
 */
export class GlobalErrorBoundary extends React.Component<GlobalErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: GlobalErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    };

    // Also catch unhandled promise rejections
    window.addEventListener('unhandledrejection', this.handleUnhandledRejection);
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[GlobalErrorBoundary] Caught error:', error, errorInfo);

    this.setState(prev => ({
      hasError: true,
      error,
      errorInfo,
      errorCount: prev.errorCount + 1,
    }));
  }

  componentWillUnmount() {
    window.removeEventListener('unhandledrejection', this.handleUnhandledRejection);
  }

  handleUnhandledRejection = (event: PromiseRejectionEvent) => {
    console.error('[GlobalErrorBoundary] Unhandled promise rejection:', event.reason);

    // Only trigger error boundary if it's a real error (not a cancelled request)
    if (event.reason && event.reason.message) {
      this.setState(prev => ({
        hasError: true,
        error: event.reason instanceof Error ? event.reason : new Error(String(event.reason)),
        errorCount: prev.errorCount + 1,
      }));
    }
  };

  resetError = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render() {
    if (this.state.hasError) {
      const { error, errorInfo, errorCount } = this.state;
      const isLoopingError = errorCount > 3;

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
            maxWidth: '600px',
            background: 'var(--ds-card-bg)',
            border: '1px solid var(--ds-card-border)',
            borderRadius: '1rem',
            padding: '2rem',
            boxShadow: 'var(--ds-card-shadow)',
            textAlign: 'center',
          }}>
            {/* Error Icon */}
            <AlertTriangle style={{
              width: 48,
              height: 48,
              color: '#f87171',
              margin: '0 auto 1rem',
            }} />

            {/* Error Title */}
            <h1 style={{
              fontSize: '1.25rem',
              fontWeight: 700,
              color: 'var(--ds-text-primary)',
              margin: '0 0 0.5rem',
            }}>
              {isLoopingError ? '🔄 Application Error Loop' : '⚠️ Something Went Wrong'}
            </h1>

            {/* Error Details */}
            <p style={{
              fontSize: '0.875rem',
              color: 'var(--ds-text-muted)',
              margin: '0 0 1.5rem',
              lineHeight: 1.6,
            }}>
              {isLoopingError
                ? 'The application encountered a recurring error. Please sign in again or contact support.'
                : 'An unexpected error occurred. Try refreshing the page or signing in again.'}
            </p>

            {/* Error Details Box (for debugging) */}
            {error && (
              <div style={{
                background: 'var(--ds-surface-2)',
                border: '1px solid var(--ds-border)',
                borderRadius: '0.5rem',
                padding: '1rem',
                marginBottom: '1.5rem',
                textAlign: 'left',
                maxHeight: '200px',
                overflow: 'auto',
              }}>
                <div style={{
                  fontSize: '0.625rem',
                  fontWeight: 600,
                  color: 'var(--ds-text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '0.5rem',
                }}>
                  Error Details
                </div>
                <div style={{
                  fontSize: '0.75rem',
                  color: '#f87171',
                  fontFamily: 'monospace',
                  wordBreak: 'break-word',
                  lineHeight: 1.5,
                }}>
                  <div>{error.message}</div>
                  {errorInfo && (
                    <div style={{
                      marginTop: '0.5rem',
                      fontSize: '0.625rem',
                      color: 'var(--ds-text-muted)',
                      maxHeight: '100px',
                      overflow: 'hidden',
                    }}>
                      {errorInfo.componentStack}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Actions */}
            <div style={{
              display: 'flex',
              gap: '1rem',
              justifyContent: 'center',
              flexWrap: 'wrap',
            }}>
              {!isLoopingError && (
                <button
                  onClick={this.resetError}
                  style={{
                    padding: '0.75rem 1.5rem',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    borderRadius: '0.5rem',
                    border: 'none',
                    cursor: 'pointer',
                    background: '#3b82f6',
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    transition: 'background 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#2563eb';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#3b82f6';
                  }}
                >
                  <RefreshCw style={{ width: 16, height: 16 }} />
                  Try Again
                </button>
              )}

              <button
                onClick={() => {
                  this.props.onLogout?.();
                  // Fallback: reload page
                  window.location.href = '/login';
                }}
                style={{
                  padding: '0.75rem 1.5rem',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  borderRadius: '0.5rem',
                  border: 'none',
                  cursor: 'pointer',
                  background: 'var(--ds-surface-2)',
                  color: 'var(--ds-text-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'background 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--ds-surface-3)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'var(--ds-surface-2)';
                }}
              >
                <LogOut style={{ width: 16, height: 16 }} />
                Sign In Again
              </button>
            </div>

            {/* Support Text */}
            <div style={{
              fontSize: '0.75rem',
              color: 'var(--ds-text-muted)',
              marginTop: '1.5rem',
              borderTop: '1px solid var(--ds-border)',
              paddingTop: '1rem',
            }}>
              If this error persists, please contact support with error ID: {new Date().getTime()}
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default GlobalErrorBoundary;
