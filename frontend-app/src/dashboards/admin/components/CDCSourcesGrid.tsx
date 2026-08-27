/**
 * CDCSourcesGrid.tsx — 5-Database CDC Sources Overview
 *
 * CRITICAL: Always shows all 5 database sources regardless of connection state
 * - Shows connection status (Connected/Disconnected/Not Configured)
 * - Shows real latency or N/A
 * - Shows CDC status (Active/Inactive)
 * - Shows last sync time or N/A
 *
 * RULE: No fake data. Real backend values or N/A.
 */

import React from 'react';
import { Database } from 'lucide-react';
import type { CDCAdapter } from '../../../shared/types';

interface CDCSourcesGridProps {
  adapters: CDCAdapter[];
  isLoading?: boolean;
}

/**
 * All 5 CDC database sources always visible
 * Shows real status or "Not Configured"
 */
export const CDCSourcesGrid: React.FC<CDCSourcesGridProps> = ({ adapters = [], isLoading = false }) => {
  // Define all 5 expected database sources
  const expectedDatabases = [
    { name: 'PostgreSQL Hospital', type: 'postgresql', order: 0 },
    { name: 'MySQL Hospital', type: 'mysql', order: 1 },
    { name: 'Oracle Hospital', type: 'oracle', order: 2 },
    { name: 'SQL Server Hospital', type: 'sqlserver', order: 3 },
    { name: 'MongoDB Hospital', type: 'mongodb', order: 4 },
  ];

  // Create a map of configured adapters
  const adapterMap = new Map(adapters.map(a => [a.database_type, a]));

  // Build display list: show all expected DBs, using real data if available
  const displayAdapters = expectedDatabases.map(expected => {
    const adapter = adapterMap.get(expected.type as any);
    if (adapter) {
      return adapter;
    }
    // Database not configured in backend — show "Not Configured"
    return {
      id: `missing-${expected.type}`,
      name: expected.name,
      database_type: expected.type as any,
      status: 'error' as const,
      latency_ms: null,
      cdc_enabled: false,
      cdc_trigger_status: 'inactive' as const,
      cdc_lag_seconds: null,
      error: 'Not Configured — env var missing',
    };
  });

  const getStatusColor = (adapter: any) => {
    if (adapter.error === 'Not Configured — env var missing') {
      return '#9ca3af'; // Gray — not configured
    }
    switch (adapter.status) {
      case 'connected':
        return '#34d399'; // Green
      case 'disconnected':
        return '#f87171'; // Red
      case 'error':
        return '#f87171'; // Red
      default:
        return '#9ca3af'; // Gray
    }
  };

  const getStatusLabel = (adapter: any) => {
    if (adapter.error === 'Not Configured — env var missing') {
      return 'Not Configured';
    }
    return adapter.status === 'connected' ? 'Connected' : 'Disconnected';
  };

  return (
    <div style={{ width: '100%' }}>
      {/* Section Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        marginBottom: '1.5rem',
        fontSize: '0.875rem',
        fontWeight: 700,
        color: 'var(--ds-text-primary)',
      }}>
        <Database style={{ width: 16, height: 16 }} />
        CDC Data Sources (All 5 Database Platforms)
      </div>

      {/* 5-Database Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem',
        marginBottom: '2rem',
      }}>
        {displayAdapters.map((adapter) => {
          const statusColor = getStatusColor(adapter);
          const statusLabel = getStatusLabel(adapter);
          const isConfigured = adapter.error !== 'Not Configured — env var missing';
          const isConnected = adapter.status === 'connected' && isConfigured;

          return (
            <div
              key={adapter.id}
              style={{
                background: 'var(--ds-card-bg)',
                border: `2px solid ${statusColor}`,
                borderRadius: '0.75rem',
                padding: '1rem',
                opacity: isLoading ? 0.6 : 1,
                transition: 'all 0.2s ease',
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              {/* Status Indicator */}
              <div style={{
                position: 'absolute',
                top: 0,
                right: 0,
                width: '4px',
                height: '100%',
                background: statusColor,
              }} />

              {/* Database Name & Type */}
              <div style={{ marginBottom: '0.75rem' }}>
                <div style={{
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  color: 'var(--ds-text-muted)',
                  letterSpacing: '0.05em',
                  marginBottom: '0.25rem',
                }}>
                  {adapter.database_type.toUpperCase()}
                </div>
                <div style={{
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  color: 'var(--ds-text-primary)',
                }}>
                  {adapter.name}
                </div>
              </div>

              {/* Status Badge */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                marginBottom: '0.75rem',
                fontSize: '0.75rem',
              }}>
                <div style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: statusColor,
                  boxShadow: `0 0 6px ${statusColor}80`,
                }} />
                <span style={{ color: statusColor, fontWeight: 600 }}>
                  {statusLabel}
                </span>
              </div>

              {/* Connection Details */}
              <div style={{
                fontSize: '0.6875rem',
                color: 'var(--ds-text-muted)',
                lineHeight: 1.6,
                borderTop: '1px solid var(--ds-border)',
                paddingTop: '0.75rem',
              }}>
                {/* Latency */}
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, color: 'var(--ds-text-primary)' }}>
                    Latency:
                  </span>
                  {' '}
                  {adapter.latency_ms !== null ? `${adapter.latency_ms}ms` : 'N/A'}
                </div>

                {/* CDC Status */}
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, color: 'var(--ds-text-primary)' }}>
                    CDC:
                  </span>
                  {' '}
                  {isConnected
                    ? '✓ Active'
                    : '✗ Inactive'
                  }
                </div>

                {/* CDC Lag */}
                <div style={{ marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: 600, color: 'var(--ds-text-primary)' }}>
                    Lag:
                  </span>
                  {' '}
                  {adapter.cdc_lag_seconds !== null ? `${adapter.cdc_lag_seconds}s` : 'N/A'}
                </div>

                {/* Error Message (if applicable) */}
                {adapter.error && adapter.error !== 'Not Configured — env var missing' && (
                  <div style={{
                    color: '#f87171',
                    marginTop: '0.5rem',
                    fontSize: '0.625rem',
                    fontStyle: 'italic',
                  }}>
                    ⚠️ {adapter.error}
                  </div>
                )}

                {/* Not Configured Message */}
                {adapter.error === 'Not Configured — env var missing' && (
                  <div style={{
                    color: '#9ca3af',
                    marginTop: '0.5rem',
                    fontSize: '0.625rem',
                  }}>
                    Configure in .env to enable
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div style={{
        fontSize: '0.75rem',
        color: 'var(--ds-text-muted)',
        padding: '0.75rem',
        background: 'var(--ds-surface-2)',
        borderRadius: '0.5rem',
        display: 'flex',
        gap: '1.5rem',
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#34d399',
          }} />
          <span>Connected</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#f87171',
          }} />
          <span>Disconnected / Error</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: '#9ca3af',
          }} />
          <span>Not Configured</span>
        </div>
      </div>
    </div>
  );
};

export default CDCSourcesGrid;
