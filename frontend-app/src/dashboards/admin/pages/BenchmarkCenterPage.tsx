/**
 * BenchmarkCenterPage.tsx — Benchmark Center (Coming Soon)
 * Backend endpoint (/api/v1/benchmark/run) does not exist yet
 * This page will be enabled once backend implements benchmark testing APIs
 */
import React from 'react';
import { Zap, AlertCircle } from 'lucide-react';

const BenchmarkCenterPage: React.FC = () => {
  return (
    <div style={{
      maxWidth: 1400,
      margin: '0 auto',
      display: 'flex',
      flexDirection: 'column',
      gap: '1.5rem',
      fontFamily: "'Inter', sans-serif",
      padding: '1.5rem',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
      }}>
        <div>
          <h1 style={{
            fontSize: '1.375rem',
            fontWeight: 800,
            color: 'var(--ds-text-primary)',
            margin: 0,
            letterSpacing: '-0.02em',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}>
            <Zap style={{ width: 24, height: 24, color: '#fbbf24' }} />
            Benchmark Center
          </h1>
          <p style={{
            fontSize: '0.8125rem',
            color: 'var(--ds-text-muted)',
            margin: '0.25rem 0 0',
          }}>
            Performance testing, load validation, ETL verification, and idempotency checks
          </p>
        </div>
      </div>

      {/* Coming Soon Alert */}
      <div style={{
        background: 'rgba(99, 102, 241, 0.10)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        borderRadius: '1rem',
        padding: '1.5rem',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '1rem',
      }}>
        <AlertCircle style={{
          width: 24,
          height: 24,
          color: '#6366f1',
          flexShrink: 0,
          marginTop: 2,
        }} />
        <div style={{ flex: 1 }}>
          <h2 style={{
            fontSize: '1rem',
            fontWeight: 700,
            color: 'var(--ds-text-primary)',
            margin: '0 0 0.5rem',
          }}>
            Coming Soon
          </h2>
          <p style={{
            fontSize: '0.8125rem',
            color: 'var(--ds-text-secondary)',
            margin: '0 0 1rem',
            lineHeight: 1.6,
          }}>
            Benchmark testing functionality is under development. The backend API endpoint
            (<code style={{ fontFamily: 'monospace', background: 'rgba(0,0,0,0.1)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>/api/v1/benchmark/run</code>) is not yet available.
          </p>
          <p style={{
            fontSize: '0.8125rem',
            color: 'var(--ds-text-muted)',
            margin: '0 0 1rem',
          }}>
            The benchmark feature will enable performance testing and load validation once the
            backend implementation is complete.
          </p>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.8125rem',
            color: 'var(--ds-text-secondary)',
          }}>
            <span style={{ color: '#fbbf24' }}>ℹ️</span>
            Check back later or contact your administrator for updates
          </div>
        </div>
      </div>

      {/* Feature Preview */}
      <div style={{
        background: 'var(--ds-card-bg)',
        border: '1px solid var(--ds-card-border)',
        borderRadius: '1rem',
        padding: '1.25rem',
        boxShadow: 'var(--ds-card-shadow)',
      }}>
        <h3 style={{
          fontSize: '0.875rem',
          fontWeight: 700,
          color: 'var(--ds-text-primary)',
          margin: '0 0 1rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}>
          <span style={{ fontSize: '1.25rem' }}>🎯</span>
          Planned Features
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '1rem',
        }}>
          {[
            {
              name: 'Full System Benchmark',
              desc: 'Comprehensive throughput and latency test across all adapters',
              duration: '~8 minutes',
            },
            {
              name: 'Multi-DB ETL Validation',
              desc: 'Verify end-to-end sync from PostgreSQL, MySQL, MongoDB to FHIR store',
              duration: '~5 minutes',
            },
            {
              name: '500-Row Load Test',
              desc: 'Quick sanity check: 500 rows per table through full ETL pipeline',
              duration: '~1 minute',
            },
            {
              name: 'Idempotency Verification',
              desc: 'Run sync 3× with same source data, verify no duplicates in FHIR store',
              duration: '~6 minutes',
            },
          ].map(test => (
            <div key={test.name} style={{
              background: 'rgba(99, 102, 241, 0.05)',
              border: '1px solid rgba(99, 102, 241, 0.15)',
              borderRadius: '0.75rem',
              padding: '1rem',
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
                marginBottom: '0.5rem',
              }}>
                <span style={{ fontSize: '1.25rem', marginTop: 2 }}>⚡</span>
                <h4 style={{
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  color: 'var(--ds-text-primary)',
                  margin: 0,
                }}>
                  {test.name}
                </h4>
              </div>
              <p style={{
                fontSize: '0.75rem',
                color: 'var(--ds-text-secondary)',
                margin: '0 0 0.5rem 2rem',
                lineHeight: 1.5,
              }}>
                {test.desc}
              </p>
              <div style={{
                fontSize: '0.7rem',
                color: 'var(--ds-text-muted)',
                margin: '0 0 0 2rem',
                fontWeight: 500,
              }}>
                ⏱️ {test.duration}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Status Box */}
      <div style={{
        background: 'var(--ds-card-bg)',
        border: '1px solid var(--ds-card-border)',
        borderRadius: '1rem',
        padding: '1.25rem',
        boxShadow: 'var(--ds-card-shadow)',
      }}>
        <h3 style={{
          fontSize: '0.875rem',
          fontWeight: 700,
          color: 'var(--ds-text-primary)',
          margin: '0 0 1rem',
        }}>
          Implementation Status
        </h3>

        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          fontSize: '0.8125rem',
          color: 'var(--ds-text-secondary)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: 'var(--ds-text-muted)' }}>⏳</span>
            <span>Frontend UI — <strong style={{ color: 'var(--ds-text-primary)' }}>Ready</strong> (awaiting backend)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: '#ef4444' }}>✗</span>
            <span>Backend API — <strong style={{ color: 'var(--ds-text-primary)' }}>Not Implemented</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ color: '#fbbf24' }}>○</span>
            <span>Integration — <strong style={{ color: 'var(--ds-text-primary)' }}>Blocked</strong></span>
          </div>
        </div>

        <div style={{
          marginTop: '1rem',
          padding: '1rem',
          background: 'rgba(99, 102, 241, 0.05)',
          borderRadius: '0.5rem',
          fontSize: '0.75rem',
          color: 'var(--ds-text-secondary)',
          lineHeight: 1.6,
        }}>
          <strong style={{ color: 'var(--ds-text-primary)', display: 'block', marginBottom: '0.5rem' }}>Next Steps:</strong>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
            <span style={{ marginTop: '0.125rem' }}>→</span>
            <span>Backend team needs to implement <code style={{ fontFamily: 'monospace', background: 'rgba(0,0,0,0.1)', padding: '0.125rem 0.375rem', borderRadius: '0.25rem' }}>/api/v1/benchmark/run</code> and related endpoints</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BenchmarkCenterPage;
