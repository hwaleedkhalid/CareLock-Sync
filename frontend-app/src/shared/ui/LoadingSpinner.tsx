import React from 'react';
import { Loader2 } from 'lucide-react';

interface Props { size?: 'sm' | 'md' | 'lg'; text?: string }

const SIZE = { sm: 16, md: 28, lg: 40 };

const LoadingSpinner: React.FC<Props> = ({ size = 'md', text = 'Loading…' }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', gap: '0.75rem' }}>
    <Loader2 style={{ width: SIZE[size], height: SIZE[size], color: '#818cf8', animation: 'spin 0.8s linear infinite' }} />
    {text && <p style={{ fontSize: '0.8125rem', color: 'var(--ds-text-muted)', margin: 0 }}>{text}</p>}
  </div>
);

export default LoadingSpinner;
