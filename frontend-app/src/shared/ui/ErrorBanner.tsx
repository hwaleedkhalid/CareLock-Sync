import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props { message: string; detail?: string; onRetry?: () => void; retrying?: boolean }

const ErrorBanner: React.FC<Props> = ({ message, detail, onRetry, retrying }) => (
  <div role="alert" style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', border: '1px solid var(--ds-status-error-bg)', borderRadius: '0.75rem', padding: '0.75rem 1rem', background: 'var(--ds-status-error-bg)', fontSize: '0.8125rem', color: 'var(--ds-status-error-text)' }}>
    <AlertTriangle style={{ width: 15, height: 15, flexShrink: 0, marginTop: 2 }} />
    <div style={{ flex: 1, minWidth: 0 }}>
      <p style={{ margin: 0, fontWeight: 600 }}>{message}</p>
      {detail && <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', opacity: 0.8, wordBreak: 'break-word' }}>{detail}</p>}
    </div>
    {onRetry && (
      <button onClick={onRetry} disabled={retrying} style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', fontSize: '0.75rem', fontWeight: 600, padding: '0.25rem 0.625rem', borderRadius: '0.5rem', border: '1px solid var(--ds-status-error-text)', background: 'transparent', color: 'var(--ds-status-error-text)', cursor: 'pointer', opacity: retrying ? 0.5 : 1, transition: 'opacity 0.2s' }}>
        <RefreshCw style={{ width: 12, height: 12, ...(retrying ? { animation: 'spin 0.8s linear infinite' } : {}) }} />
        {retrying ? 'Retrying…' : 'Retry'}
      </button>
    )}
  </div>
);

export default ErrorBanner;
