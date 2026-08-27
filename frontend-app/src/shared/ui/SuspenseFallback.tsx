/** SuspenseFallback — theme-aware loading boundary for React.lazy chunks. */
import React from 'react';
import { Loader2 } from 'lucide-react';

interface Props { variant?: 'page' | 'panel'; label?: string }

const SuspenseFallback: React.FC<Props> = ({ variant = 'page', label }) => {
  if (variant === 'panel') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '3rem', background: 'var(--ds-card-bg)', border: '1px solid var(--ds-card-border)', borderRadius: '1rem' }}>
        <Loader2 style={{ width: 20, height: 20, color: '#818cf8', animation: 'spin 0.8s linear infinite' }} />
        {label && <span style={{ marginLeft: '0.5rem', fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>{label}</span>}
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '16rem', gap: '0.75rem' }}>
      <Loader2 style={{ width: 32, height: 32, color: '#818cf8', animation: 'spin 0.8s linear infinite' }} />
      <span style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)' }}>{label ?? 'Loading…'}</span>
    </div>
  );
};

export default SuspenseFallback;
